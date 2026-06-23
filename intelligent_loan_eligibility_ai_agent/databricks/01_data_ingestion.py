# Databricks Notebook: 01_data_ingestion
# Purpose: Load mock_customers.csv from a Databricks Volume into a managed Unity Catalog Delta Table.
# Run this notebook in a Databricks cluster before using the production pipeline.

# ─────────────────────────────────────────────────────────────────
# CELL 1: Configuration
# ─────────────────────────────────────────────────────────────────
catalog = "main"
schema  = "loan_eligibility"
table_name = "mock_customers"
full_table_path = f"{catalog}.{schema}.{table_name}"

# Path to the uploaded CSV inside a Databricks Volume
csv_path = "/Volumes/main/loan_eligibility/raw_data/mock_customers.csv"

print(f"Target Delta Table : {full_table_path}")
print(f"Source CSV path    : {csv_path}")

# ─────────────────────────────────────────────────────────────────
# CELL 2: Detect Spark Context (notebook vs local)
# ─────────────────────────────────────────────────────────────────
# NOTE: `spark` is pre-injected by the Databricks notebook runtime.
# The try/except below makes it importable locally too, so the IDE
# does not raise 'undefined name' (F821 / Pylance reportUndefinedVariable).
try:
    spark  # type: ignore[name-defined]  # noqa: F821
    IN_DATABRICKS = True
except NameError:
    from pyspark.sql import SparkSession
    spark = SparkSession.builder.appName("LoanIngestion").getOrCreate()
    IN_DATABRICKS = False

print(f"Running in Databricks: {IN_DATABRICKS}")

# ─────────────────────────────────────────────────────────────────
# CELL 3: Create Unity Catalog Schema (idempotent)
# ─────────────────────────────────────────────────────────────────
if IN_DATABRICKS:
    try:
        spark.sql(f"CREATE CATALOG IF NOT EXISTS {catalog}")
        spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}")
        spark.sql(f"CREATE VOLUME IF NOT EXISTS {catalog}.{schema}.raw_data")
        print(f"Unity Catalog structure '{catalog}.{schema}.raw_data' is ready.")

        # Check and copy files from repo if missing in Volume
        import shutil
        import os

        volume_dir = f"/Volumes/{catalog}/{schema}/raw_data"
        os.makedirs(volume_dir, exist_ok=True)

        for filename in ["mock_customers.csv", "loan_policy.pdf"]:
            dest_file = os.path.join(volume_dir, filename)
            if not os.path.exists(dest_file):
                # Try finding in current repo context
                for possible_src in [f"data/{filename}", f"intelligent_loan_eligibility_ai_agent/data/{filename}"]:
                    if os.path.exists(possible_src):
                        shutil.copy(possible_src, dest_file)
                        print(f"Copied {filename} from Repo ({possible_src}) to Volume ({dest_file})")
                        break
                else:
                    print(f"Warning: Could not locate source file {filename} in Repo directory to copy.")
            else:
                print(f"File '{filename}' already exists in Volume.")
    except Exception as e:
        print(f"Unity Catalog volume setup or copy warning: {e}")

# ─────────────────────────────────────────────────────────────────
# CELL 4: Read CSV and Write to Delta Table
# ─────────────────────────────────────────────────────────────────
try:
    print(f"Reading CSV from: {csv_path}")
    df = (
        spark.read
        .option("header", "true")
        .option("inferSchema", "true")
        .csv(csv_path)
    )

    row_count = df.count()
    print(f"Loaded {row_count} customer records.")

    if IN_DATABRICKS:
        display(df.limit(5))  # type: ignore[name-defined]  # noqa: F821 — Databricks built-in

    # Write to Delta Table
    print(f"Writing to Delta Table: {full_table_path}")
    (
        df.write
        .format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable(full_table_path)
    )
    print("Data ingestion completed successfully. Delta Table is synced.")

except Exception as e:
    print(f"Ingestion failed: {e}")
    print("Ensure the CSV file is uploaded to the Databricks Volume before running this notebook.")
    raise
