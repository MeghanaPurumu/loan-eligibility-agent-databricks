import json
import logging
import sqlite3
import time
from datetime import datetime
from typing import Any, Dict, List
from config import settings

logger = logging.getLogger(__name__)

# SQLite DB Path (local development)
DB_PATH = settings.BASE_DIR / "loan_assessment_logs.db"

def init_sqlite_db():
    """Initializes the SQLite database schema if running locally."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS loan_assessment_logs (
                application_id TEXT PRIMARY KEY,
                session_id TEXT,
                timestamp TEXT,
                customer_input TEXT,
                decision TEXT,
                guardrail_status TEXT,
                latency REAL,
                retrieved_documents TEXT,
                model_name TEXT
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to initialize SQLite database: {e}")

# Initialize SQLite database immediately on import when in local mode
if settings.MODE == "local":
    init_sqlite_db()

def log_assessment(
    application_id: str,
    session_id: str,
    customer_input: Dict[str, Any],
    decision: str,
    guardrail_status: str,
    latency: float,
    retrieved_documents: List[str],
    model_name: str
) -> bool:
    """
    Logs assessment details into the database.
    Dynamically switches backend based on config.settings.MODE.
    """
    if not settings.ENABLE_AUDIT:
        return False

    timestamp = datetime.utcnow().isoformat()
    customer_input_json = json.dumps(customer_input)
    retrieved_docs_json = json.dumps(retrieved_documents)

    if settings.MODE == "prod":
        return log_to_delta(
            application_id,
            session_id,
            timestamp,
            customer_input_json,
            decision,
            guardrail_status,
            latency,
            retrieved_docs_json,
            model_name
        )
    else:
        return log_to_sqlite(
            application_id,
            session_id,
            timestamp,
            customer_input_json,
            decision,
            guardrail_status,
            latency,
            retrieved_docs_json,
            model_name
        )

def log_to_sqlite(
    application_id: str,
    session_id: str,
    timestamp: str,
    customer_input: str,
    decision: str,
    guardrail_status: str,
    latency: float,
    retrieved_documents: str,
    model_name: str
) -> bool:
    """Writes log entry to local SQLite table."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO loan_assessment_logs (
                application_id, session_id, timestamp, customer_input, 
                decision, guardrail_status, latency, retrieved_documents, model_name
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            application_id, session_id, timestamp, customer_input, 
            decision, guardrail_status, latency, retrieved_documents, model_name
        ))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Failed to log to SQLite: {e}")
        return False

def log_to_delta(
    application_id: str,
    session_id: str,
    timestamp: str,
    customer_input: str,
    decision: str,
    guardrail_status: str,
    latency: float,
    retrieved_documents: str,
    model_name: str
) -> bool:
    """Writes log entry to Databricks Unity Catalog Delta Table using Spark."""
    try:
        from pyspark.sql import SparkSession
        from pyspark.sql.types import StructType, StructField, StringType, DoubleType

        spark = SparkSession.builder.getOrCreate()
        
        # Define Schema matching Unity Catalog table
        schema = StructType([
            StructField("application_id", StringType(), False),
            StructField("session_id", StringType(), True),
            StructField("timestamp", StringType(), True),
            StructField("customer_input", StringType(), True),
            StructField("decision", StringType(), True),
            StructField("guardrail_status", StringType(), True),
            StructField("latency", DoubleType(), True),
            StructField("retrieved_documents", StringType(), True),
            StructField("model_name", StringType(), True)
        ])
        
        row_data = [(
            application_id, session_id, timestamp, customer_input, 
            decision, guardrail_status, latency, retrieved_documents, model_name
        )]
        
        df = spark.createDataFrame(row_data, schema=schema)
        table_name = settings.DATABASE_URL
        
        # Append to Delta table
        df.write.format("delta").mode("append").saveAsTable(table_name)
        return True
    except Exception as e:
        logger.error(f"Failed to log to Delta table: {e}")
        # Fallback to local SQLite in case of failure
        return log_to_sqlite(
            application_id,
            session_id,
            timestamp,
            customer_input,
            decision,
            guardrail_status,
            latency,
            retrieved_documents,
            model_name
        )
