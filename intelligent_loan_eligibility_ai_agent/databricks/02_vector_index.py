# Databricks Notebook: 02_vector_index
# Purpose: Create a Databricks Vector Search endpoint and sync index from the
#          policy_chunks Delta Table in Unity Catalog.
# Run AFTER 01_data_ingestion.py and after uploading loan_policy.pdf chunks.

# ─────────────────────────────────────────────────────────────────
# CELL 1: Install SDK if needed (run once per cluster)
# ─────────────────────────────────────────────────────────────────
# Uncomment and run this cell if databricks-vectorsearch is not installed:
# %pip install databricks-vectorsearch --quiet

# ─────────────────────────────────────────────────────────────────
# CELL 2: Configuration
# ─────────────────────────────────────────────────────────────────
import time

catalog        = "main"
schema         = "loan_eligibility"
endpoint_name  = "loan-policy-search-endpoint"
source_table   = f"{catalog}.{schema}.policy_chunks"
index_name     = f"{catalog}.{schema}.loan_policy_index"
primary_key    = "chunk_id"
embedding_col  = "text"
embedding_model = "databricks-bge-large-en"   # Built-in Databricks embedding endpoint

print(f"Endpoint      : {endpoint_name}")
print(f"Source Table  : {source_table}")
print(f"Index Name    : {index_name}")

# ─────────────────────────────────────────────────────────────────
# CELL 3: (One-time) Create policy_chunks Delta Table from PDF text
# ─────────────────────────────────────────────────────────────────
# This cell is only needed if the policy_chunks table does not exist yet.
# It reads the embedded fallback policy text and writes it as chunks.

# NOTE: `spark` is a Databricks-injected global. We assign it to None locally
# so that Pylance / Pylint do not flag every subsequent usage as 'undefined name'.
# All real spark calls are guarded by `if IN_DATABRICKS:` so this is safe.
try:
    spark  # type: ignore[name-defined]  # noqa: F821
    IN_DATABRICKS = True
except NameError:
    spark = None  # type: ignore[assignment]  # local stub – never called outside Databricks
    IN_DATABRICKS = False

if IN_DATABRICKS:
    # Check if source table already exists
    table_exists = spark.catalog.tableExists(source_table)  # type: ignore[union-attr]
    if not table_exists:
        print(f"Table '{source_table}' not found. Creating from fallback policy text...")

        POLICY_TEXT = """
        Section 1.5: Applicants must be between 21 and 60 years old at application date.
        Section 2.1: Minimum monthly income is INR 30,000. Preferred threshold is INR 50,000.
        Section 3.2: Credit score must be >= 600. Scores >= 750 receive premium pricing benefits.
        Section 4.4: Debt-to-income ratio must not exceed 40% including the requested EMI.
        Section 5.1: Maximum loan amount cannot exceed 20 times the verified monthly net income.
        Section 2.5: Unemployed applicants and students are categorized as high-risk.
        Section 4.2: DTI ratio below 25% is preferred. Between 25% and 40% is conditionally accepted.
        Section 3.1: Credit bureau scores range from 300 to 900. Scores below 600 result in rejection.
        Section 6.1: All documents must be verified by an authorized banking officer before approval.
        """

        rows = []
        for i, line in enumerate(POLICY_TEXT.strip().split("\n")):
            line = line.strip()
            if line:
                rows.append((str(i), line))

        from pyspark.sql.types import StructType, StructField, StringType
        schema_def = StructType([
            StructField("chunk_id", StringType(), False),
            StructField("text", StringType(), True)
        ])
        df_chunks = spark.createDataFrame(rows, schema=schema_def)  # type: ignore[union-attr]
        df_chunks.write.format("delta").mode("overwrite").saveAsTable(source_table)
        spark.sql(f"ALTER TABLE {source_table} SET TBLPROPERTIES (delta.enableChangeDataFeed = true)")  # type: ignore[union-attr]
        print(f"✅ Created '{source_table}' with {df_chunks.count()} chunks.")
    else:
        print(f"✅ Source table '{source_table}' already exists.")
        # Ensure CDC is enabled for vector sync
        try:
            spark.sql(f"ALTER TABLE {source_table} SET TBLPROPERTIES (delta.enableChangeDataFeed = true)")  # type: ignore[union-attr]
        except Exception:
            pass

# ─────────────────────────────────────────────────────────────────
# CELL 4: Initialize Vector Search Client
# ─────────────────────────────────────────────────────────────────
# NOTE: databricks-vectorsearch is only available on a Databricks cluster.
# The try/except below prevents an ImportError when the file is opened
# locally (e.g. in VS Code), so the IDE no longer shows a red import.
try:
    from databricks.vector_search.client import VectorSearchClient
    _VS_AVAILABLE = True
except ImportError:
    VectorSearchClient = None  # type: ignore[assignment,misc]  # local stub
    _VS_AVAILABLE = False

if not _VS_AVAILABLE and IN_DATABRICKS:
    raise ImportError(
        "databricks-vectorsearch SDK not found. "
        "Run: %pip install databricks-vectorsearch --quiet"
    )

vsc = VectorSearchClient(disable_notice=True)

# ─────────────────────────────────────────────────────────────────
# CELL 5: Create Vector Search Endpoint (idempotent)
# ─────────────────────────────────────────────────────────────────
existing = [e.get("name") for e in vsc.list_endpoints().get("endpoints", [])]

if endpoint_name not in existing:
    print(f"Creating Vector Search Endpoint '{endpoint_name}'...")
    vsc.create_endpoint(name=endpoint_name, endpoint_type="STANDARD")

    # Poll until endpoint is ONLINE
    for _ in range(30):
        state = (
            vsc.get_endpoint(endpoint_name)
            .get("endpoint_status", {})
            .get("state", "UNKNOWN")
        )
        if state == "ONLINE":
            print(f"✅ Endpoint '{endpoint_name}' is ONLINE.")
            break
        print(f"  Endpoint state: {state} — waiting 15s...")
        time.sleep(15)
    else:
        print("⚠️  Endpoint did not reach ONLINE state within 7.5 minutes. Check Databricks UI.")
else:
    print(f"✅ Endpoint '{endpoint_name}' already exists.")

# ─────────────────────────────────────────────────────────────────
# CELL 6: Create Delta Sync Vector Search Index (idempotent)
# ─────────────────────────────────────────────────────────────────
existing_indexes = [
    idx.get("name")
    for idx in vsc.list_indexes(endpoint_name).get("vector_indexes", [])
]

if index_name not in existing_indexes:
    print(f"Creating Vector Index '{index_name}'...")
    try:
        vsc.create_delta_sync_index(
            endpoint_name=endpoint_name,
            source_table_name=source_table,
            index_name=index_name,
            pipeline_type="TRIGGERED",       # TRIGGERED or CONTINUOUS
            primary_key=primary_key,
            embedding_source_column=embedding_col,
            embedding_model_endpoint_name=embedding_model
        )
        print(f"✅ Vector Index '{index_name}' created successfully.")
        print("   Run vsc.get_index(endpoint_name, index_name).sync() to trigger initial sync.")
    except Exception as e:
        print(f"❌ Failed to create Vector Index: {e}")
        print("   Check that the source table exists and CDC is enabled.")
else:
    print(f"✅ Index '{index_name}' already exists. Triggering sync...")
    try:
        idx = vsc.get_index(endpoint_name, index_name)
        idx.sync()
        print("   Sync triggered.")
    except Exception as e:
        print(f"   Sync warning: {e}")
