# Databricks Notebook: 03_agent_pipeline
# Purpose: Production entrypoint for the Loan Eligibility Orchestrator.
#          Can be run as a Databricks Job with widget parameters, or called
#          from another notebook via dbutils.notebook.run().

# ─────────────────────────────────────────────────────────────────
# CELL 1: Set MODE before any project imports (critical ordering fix)
# ─────────────────────────────────────────────────────────────────
import os
import sys
import json

# Set production mode FIRST — before importing config.settings or orchestrator,
# because settings.py reads MODE at import time.
os.environ["MODE"] = "prod"

# Add project root to path so all modules are importable
# In Databricks, the project is typically mounted or cloned via Repos.
# Adjust this path to match your Databricks Repos path if needed.
repo_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.abspath(repo_root))

# ─────────────────────────────────────────────────────────────────
# CELL 2: Detect Databricks context (notebook vs local CI test)
# ─────────────────────────────────────────────────────────────────
# NOTE: `dbutils` is a Databricks-injected utility object. We assign a None
# stub locally so that Pylance / Pylint do not flag every guarded usage as
# 'undefined name'. All real calls are inside `if IN_DATABRICKS:` blocks.
try:
    dbutils  # type: ignore[name-defined]  # noqa: F821 — pre-injected in Databricks notebooks
    IN_DATABRICKS = True
except NameError:
    dbutils = None  # type: ignore[assignment]  # local stub – never used outside Databricks
    IN_DATABRICKS = False

print(f"Running in Databricks: {IN_DATABRICKS}")

# ─────────────────────────────────────────────────────────────────
# CELL 3: Define Widget Parameters
# ─────────────────────────────────────────────────────────────────
if IN_DATABRICKS:
    # Register notebook widgets for Databricks Jobs UI / workflow parameters
    dbutils.widgets.text("name", "John Doe", "Applicant Full Name")  # type: ignore[union-attr]
    dbutils.widgets.text("age", "30", "Age (18–60)")  # type: ignore[union-attr]
    dbutils.widgets.text("monthly_income", "65000", "Monthly Income (INR)")  # type: ignore[union-attr]
    dbutils.widgets.dropdown(  # type: ignore[union-attr]
        "employment_type", "Salaried",
        ["Salaried", "Self-employed", "Business", "Student", "Unemployed", "Retired"],
        "Employment Type"
    )
    dbutils.widgets.text("credit_score", "720", "Credit Score (300–900)")  # type: ignore[union-attr]
    dbutils.widgets.dropdown("existing_loan", "No", ["No", "Yes"], "Has Existing Loan")  # type: ignore[union-attr]
    dbutils.widgets.text("monthly_loan_payment", "0", "Monthly EMI (INR, 0 if none)")  # type: ignore[union-attr]
    dbutils.widgets.text("loan_amount_requested", "200000", "Requested Loan Amount (INR)")  # type: ignore[union-attr]
    dbutils.widgets.text("loan_purpose", "Home Renovation", "Purpose of Loan")  # type: ignore[union-attr]

    def get_widget(name):
        return dbutils.widgets.get(name)  # type: ignore[union-attr]
else:
    # Local fallback defaults for testing outside Databricks
    _defaults = {
        "name": "John Doe",
        "age": "30",
        "monthly_income": "65000",
        "employment_type": "Salaried",
        "credit_score": "720",
        "existing_loan": "No",
        "monthly_loan_payment": "0",
        "loan_amount_requested": "200000",
        "loan_purpose": "Home Renovation",
    }
    def get_widget(name):
        return _defaults.get(name, "")

# ─────────────────────────────────────────────────────────────────
# CELL 4: Build and Validate Customer Payload
# ─────────────────────────────────────────────────────────────────
def safe_int(val, default=0):
    try:
        return int(val)
    except (ValueError, TypeError):
        return default

def safe_float(val, default=0.0):
    try:
        return float(val)
    except (ValueError, TypeError):
        return default

customer_payload = {
    "name":                 get_widget("name").strip(),
    "age":                  safe_int(get_widget("age")),
    "monthly_income":       safe_float(get_widget("monthly_income")),
    "employment_type":      get_widget("employment_type").strip(),
    "credit_score":         safe_int(get_widget("credit_score")),
    "existing_loan":        get_widget("existing_loan").strip(),
    "monthly_loan_payment": safe_float(get_widget("monthly_loan_payment")),
    "loan_amount_requested":safe_float(get_widget("loan_amount_requested")),
    "loan_purpose":         get_widget("loan_purpose").strip(),
}

print("Customer Payload:")
print(json.dumps(customer_payload, indent=2))

# Fail fast if name is empty (common misconfiguration)
if not customer_payload["name"]:
    raise ValueError("Widget 'name' is empty. Please set Applicant Full Name before running.")

# ─────────────────────────────────────────────────────────────────
# CELL 5: Import and Run Orchestrator
# ─────────────────────────────────────────────────────────────────
# Import AFTER setting os.environ["MODE"] = "prod" to ensure settings
# reads the correct provider/backend configuration.
from agents.loan_orchestrator import orchestrate_loan_assessment  # noqa: E402

print("\nRunning Loan Eligibility Orchestrator (prod mode)...")
result = orchestrate_loan_assessment(customer_payload)

# ─────────────────────────────────────────────────────────────────
# CELL 6: Display and Return Results
# ─────────────────────────────────────────────────────────────────
print("\n✅ Assessment Complete:")
print(json.dumps(result, indent=2))

# Log key metrics to notebook output
print(f"\n  Decision   : {result.get('decision', 'N/A')}")
print(f"  Confidence : {result.get('confidence', 'N/A')}")
print(f"  Disclaimer : {result.get('disclaimer', '')[:80]}...")

# Return structured result for downstream Databricks Job tasks
if IN_DATABRICKS:
    dbutils.notebook.exit(json.dumps(result))  # type: ignore[union-attr]  # noqa: F821
