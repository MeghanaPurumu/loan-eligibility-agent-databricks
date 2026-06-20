# Databricks Script: 06_deployment
# Instructions and configuration files for deploying Streamlit as a Databricks App

# DBTITLE 1,Deployment Configurations
# Create the databricks.yml configuration file for Databricks Apps:
DATABRICKS_YML_CONTENT = """
# databricks.yml
# Configuration to bundle and deploy Streamlit WebApp on Databricks Apps

bundle:
  name: intelligent-loan-eligibility-app

app:
  name: intelligent-loan-assessment-agent
  entry_point: app.py
  language: python
  dependencies:
    - requirements.txt
  env:
    - name: MODE
      value: prod
    - name: MODEL_PROVIDER
      value: databricks
    - name: VECTOR_BACKEND
      value: databricks
    - name: ENABLE_GUARDRAILS
      value: "True"
    - name: ENABLE_RAG
      value: "True"
    - name: ENABLE_AUDIT
      value: "True"
"""

print("Deploying Streamlit to Databricks Apps requires the Databricks CLI:")
print("------------------------------------------------------------------")
print("1. Install Databricks CLI: 'brew install databricks-cli' or download executable.")
print("2. Configure authentications: 'databricks configure'")
print("3. Write databricks.yml configuration to project root directory.")
print("4. Validate configurations: 'databricks bundle validate'")
print("5. Deploy application: 'databricks bundle deploy'")
print("6. Run application online: 'databricks bundle run'")
print("------------------------------------------------------------------")

# Write databricks.yml content to config file in current directory
import os
yml_path = os.path.join(os.path.abspath(".."), "databricks.yml")
try:
    with open(yml_path, "w") as f:
        f.write(DATABRICKS_YML_CONTENT.strip())
    print(f"Successfully generated databricks.yml config at: {yml_path}")
except Exception as e:
    print(f"Failed to write databricks.yml config: {e}")
