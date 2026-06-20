# Databricks Notebook: 05_model_serving
# Script to create and configure Databricks Model Serving Endpoints

import requests
import json

# DBTITLE 1,Define Parameters
# Databricks Environment Host and Token (injected automatically in notebook)
host = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get() # Token
api_url = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiUrl().get() # API URL

endpoint_name = "databricks-meta-llama-3-1-70b-instruct-endpoint"
served_model_name = "system.serving.meta-llama-3-1-70b-instruct" # Standard UC model path

# DBTITLE 2,Create Serving Endpoint payload
payload = {
    "name": endpoint_name,
    "config": {
        "served_models": [
            {
                "model_name": served_model_name,
                "model_version": "1",
                "workload_size": "Small", # Small, Medium, Large
                "scale_to_zero_enabled": True
            }
        ]
    }
}

headers = {
    "Authorization": f"Bearer {host}",
    "Content-Type": "application/json"
}

# DBTITLE 3,Deploy endpoint via Databricks REST API
url = f"{api_url}/api/2.0/serving-endpoints"

print(f"Deploying model serving endpoint: {endpoint_name}...")
response = requests.post(url, json=payload, headers=headers)

if response.status_code in (200, 201):
    print("Model Serving Endpoint deployment initiated successfully!")
    print(json.dumps(response.json(), indent=2))
else:
    print(f"Failed to deploy Model Serving: {response.status_code} - {response.text}")
