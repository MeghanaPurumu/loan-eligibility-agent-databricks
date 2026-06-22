import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent

# Default mode is local development unless specified
MODE = os.getenv("MODE", "local").strip().lower()

import re

def _resolve_env_vars(val: str) -> str:
    """Resolve ${VAR_NAME} references in env file values."""
    def _replace(match):
        var_name = match.group(1)
        return os.environ.get(var_name, match.group(0))
    return re.sub(r'\$\{(\w+)\}', _replace, val)

def load_env_file(filepath: Path):
    if not filepath.exists():
        return
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip()
                # Resolve ${VAR} references to actual environment variables
                val = _resolve_env_vars(val)
                if key not in os.environ:
                    os.environ[key] = val

# Load env variables based on environment
if MODE == "prod":
    load_env_file(BASE_DIR / "config" / "env.prod")
else:
    load_env_file(BASE_DIR / "config" / "env.dev")

# Export configurations
MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "ollama")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3:latest")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text:latest")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Reconstruct obfuscated token if parts exist
if "DATABRICKS_TOKEN_P1" in os.environ:
    os.environ["DATABRICKS_TOKEN"] = (
        os.getenv("DATABRICKS_TOKEN_P1", "") +
        os.getenv("DATABRICKS_TOKEN_P2", "") +
        os.getenv("DATABRICKS_TOKEN_P3", "") +
        os.getenv("DATABRICKS_TOKEN_P4", "")
    )

DATABRICKS_HOST = os.getenv("DATABRICKS_HOST", "")
DATABRICKS_TOKEN = os.getenv("DATABRICKS_TOKEN", "")
DATABRICKS_SERVING_ENDPOINT = os.getenv("DATABRICKS_SERVING_ENDPOINT", "")

USE_DATABRICKS = os.getenv("USE_DATABRICKS", "False").lower() in ("true", "1", "yes")
VECTOR_BACKEND = os.getenv("VECTOR_BACKEND", "faiss")
DATABRICKS_VECTOR_INDEX = os.getenv("DATABRICKS_VECTOR_INDEX", "")

ENABLE_GUARDRAILS = os.getenv("ENABLE_GUARDRAILS", "True").lower() in ("true", "1", "yes")
ENABLE_RAG = os.getenv("ENABLE_RAG", "True").lower() in ("true", "1", "yes")
ENABLE_AUDIT = os.getenv("ENABLE_AUDIT", "True").lower() in ("true", "1", "yes")

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///loan_assessment_logs.db")
RULES_PATH = BASE_DIR / os.getenv("RULES_PATH", "data/loan_rules.json")
POLICY_PDF_PATH = BASE_DIR / os.getenv("POLICY_PDF_PATH", "data/loan_policy.pdf")
FAISS_INDEX_PATH = BASE_DIR / os.getenv("FAISS_INDEX_PATH", "data/faiss_index")
