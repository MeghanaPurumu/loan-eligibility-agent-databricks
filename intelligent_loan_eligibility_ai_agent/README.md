# Intelligent Loan Eligibility AI Agent — Databricks Production Extension

A production-style Agentic AI application for loan eligibility assessment, optimized for local development and seamless deployment to the **Databricks** platform.

This decision-support application combines deterministic rule-based verification with RAG (Retrieval-Augmented Generation) policy lookups and security guardrails to generate compliant underwriting reports.

---

## 1. System Architecture

```text
User / Underwriter
  │
  ▼
Streamlit UI (Databricks App / Local)
  │
  ▼
Loan Orchestrator (agents/loan_orchestrator.py)
  ├── 1. Input Guardrails (guardrails/input_guard.py)
  ├── 2. Customer Validator (tools/customer_validator.py)
  ├── 3. Eligibility Engine (tools/eligibility_engine.py)
  ├── 4. Policy RAG Retrieval (tools/policy_retriever.py ➔ FAISS / Databricks Vector Search)
  ├── 5. Deterministic Confidence (tools/confidence_calculator.py)
  ├── 6. LLM Explanations (tools/explanation_generator.py ➔ Ollama / Databricks Model Serving)
  ├── 7. Output Guardrails (guardrails/output_guard.py)
  └── 8. Transaction Auditing (tools/audit_logger.py ➔ SQLite / Delta Lake)
```

---

## 2. Folder Structure

```text
project/
├── app.py                      # Streamlit router (Workspace, Analytics Dashboard)
├── requirements.txt            # Python dependencies (FAISS, PyPDF, pyspark, etc.)
├── databricks.yml              # Bundle configuration for Databricks Apps
├── config/
│   ├── settings.py             # Active settings loader
│   ├── env.dev                 # Local development variables
│   └── env.prod                # Databricks production variables
├── frontend/
│   ├── forms.py                # Left-side Customer profile form
│   ├── chat_panel.py           # Right-side AI Verdict & conversational chat
│   └── dashboard.py            # Analytics performance dashboard
├── agents/
│   └── loan_orchestrator.py    # Main pipeline orchestrator coordinator
├── tools/
│   ├── customer_validator.py   # Boundary checks (age, income, credit, amount)
│   ├── eligibility_engine.py   # Rules engine using loan_rules.json thresholds
│   ├── confidence_calculator.py# Deterministic confidence (HIGH, MODERATE, LOW)
│   ├── policy_retriever.py     # Database-agnostic policy RAG retriever
│   ├── explanation_generator.py# Invokes LLM reasoning to explain results
│   └── audit_logger.py         # Logs transaction records to SQLite / Delta Table
├── guardrails/
│   ├── input_guard.py          # Detects prompt injection & fraud attempts
│   └── output_guard.py         # Ensures disclaimers & compliance checks
├── rag/
│   ├── ingest.py               # Document indexing pipeline
│   └── vector_store.py         # Local FAISS constructor
├── databricks/
│   ├── 01_data_ingestion.py    # PySpark CSV -> UC Delta Table sync
│   ├── 02_vector_index.py      # Delta sync Vector Search index creator
│   ├── 03_agent_pipeline.py    # Run pipeline inside Databricks Jobs
│   ├── 04_guardrails.py        # Log guardrails wrappers with MLflow
│   ├── 05_model_serving.py     # Create Foundation Model Serving Endpoint
│   └── 06_deployment.py        # Streamlit app bundle deploy CLI guide
├── docs/
│   ├── architecture.md         # Architecture diagrams
│   ├── workflow.md             # Sequence diagram
│   └── demo.md                 # Testing script & presenter notes
└── data/
    ├── mock_customers.csv      # Test customer dataset
    ├── loan_rules.json         # Bank parameters rules configuration
    └── loan_policy.pdf         # Raw policy guidelines
```

---

## 3. Local Setup & Ingest

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Local Environment**:
   Verify settings inside `config/env.dev`. Ensure `MODE=local`.

3. **Start local Ollama instance**:
   ```bash
   ollama serve
   ollama pull llama3.2
   ```

4. **Trigger Ingestion Pipeline**:
   Build the FAISS database index:
   ```bash
   python rag/ingest.py
   ```

5. **Run Streamlit WebApp**:
   ```bash
   streamlit run app.py
   ```

---

## 4. Production Databricks Deployment

1. **Upload Dataset and Policies**:
   Upload `mock_customers.csv` and `loan_policy.pdf` to your Unity Catalog Volume storage.

2. **Run Configuration Notebooks**:
   Execute the scripts in the `databricks/` directory:
   - `01_data_ingestion.py`: Builds the managed Delta Table.
   - `02_vector_index.py`: Instantiates Vector Search index.
   - `05_model_serving.py`: Initiates Databricks Foundation model serving.

3. **Deploy Streamlit as a Databricks App**:
   Run the following CLI commands from the project directory:
   ```bash
   databricks configure
   databricks bundle validate
   databricks bundle deploy
   ```

---

## 5. Security & Verification Features

- **Prompt Injection Defense**: Filters out adversarial commands ("ignore policies") before they call the LLM model.
- **Output Softening**: Output guardrails prevent claims of "guaranteed approval" or "definite loans".
- **Resilient Fallback**: If LLM connections or DB writes fail, the app falls back to a deterministic text generator and local SQLite logging.
