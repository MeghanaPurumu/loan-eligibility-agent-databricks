# Databricks Notebook: 04_guardrails
# MLflow Wrapper deployment for Input and Output Guardrail checks

import mlflow
import os
import sys

# Append project path to imports
sys.path.append(os.path.abspath(".."))

from guardrails.input_guard import check_input
from guardrails.output_guard import sanitize_and_check_output

# DBTITLE 1,Define MLflow PythonModel for Guardrails
class GuardrailsModelWrapper(mlflow.pyfunc.PythonModel):
    def load_context(self, context):
        pass

    def predict(self, context, model_input):
        """
        Accepts DataFrame inputs and evaluates security guardrails.
        Input format: [{"customer_data": json_string, "user_message": string}]
        """
        import json
        import pandas as pd
        
        results = []
        for idx, row in model_input.iterrows():
            customer_str = row.get("customer_data", "{}")
            msg = row.get("user_message", "")
            
            try:
                customer_data = json.loads(customer_str)
            except Exception:
                customer_data = {}
                
            # Execute input guardrail
            guard_res = check_input(customer_data, msg)
            results.append(guard_res)
            
        return pd.DataFrame(results)

# DBTITLE 2,Register Model to MLflow Registry
# Start MLflow Run and log the guardrail model wrapper
with mlflow.start_run(run_name="loan_guardrails_run") as run:
    model_info = mlflow.pyfunc.log_model(
        artifact_path="guardrails_model",
        python_model=GuardrailsModelWrapper()
    )
    
    # Register the model to Unity Catalog
    model_name = "main.loan_eligibility.loan_guardrails_model"
    print(f"Registering Guardrails model wrapper to UC: {model_name}")
    mlflow.register_model(model_uri=model_info.model_uri, name=model_name)
    
print("Guardrails registry pipeline ready!")
