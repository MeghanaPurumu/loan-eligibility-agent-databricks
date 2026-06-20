# System Architecture Diagram & Technical Description

The **Intelligent Loan Eligibility Assessment App** is an Agentic AI solution deployed as a WebApp. Below is the architecture mapping local development runtime and Databricks production environments.

## Technical Architecture

```mermaid
graph TD
    %% User Tier
    User((Customer/Underwriter)) -->|Interact| UI[Streamlit App]

    %% WebApp / Execution Environment
    subgraph Streamlit WebApp Environment
        UI -->|Left Pane| Form[Customer Profile Form]
        UI -->|Right Pane| Chat[AI Underwriting Assistant]
        UI -->|Dashboard Panel| Dash[Analytics Dashboard]
    end

    %% Orchestrator Tier
    subgraph Agent Core
        Form -->|Trigger| Orch[Loan Orchestrator]
        Orch -->|1. Scan| IG[Input Guardrails]
        Orch -->|2. Verify| Val[Customer Validator]
        Orch -->|3. Evaluate| Eng[Eligibility Engine]
        Orch -->|4. Retrieve| RAG[Policy Retrieval Layer]
        Orch -->|5. Check| Conf[Deterministic Confidence Calculator]
        Orch -->|6. Reason| LLM[LLM Explanations Generator]
        Orch -->|7. Compliant| OG[Output Guardrails]
        Orch -->|8. Record| Audit[Audit Logger]
    end

    %% Infrastructure & Data Tier
    subgraph Local Development
        IG -->|Regex Checks| LocalRegex[Local Keywords Database]
        RAG -->|Similarity Search| FAISS[(FAISS Index)]
        LLM -->|REST API| Ollama[Local Ollama: Llama3.2]
        Audit -->|SQL Commands| SQLite[(SQLite Database)]
        Eng -->|Load Rules| RulesLocal[data/loan_rules.json]
    end

    subgraph Databricks Production
        RAG -->|Vector Search API| DBVS[(Databricks Vector Search)]
        LLM -->|Model Serving| DBMS[Databricks Model Serving Endpoint]
        Audit -->|PySpark Append| Delta[(Unity Catalog Delta Tables)]
    end

    %% Flow connections
    Delta -->|Aggregate Logs| Dash
    SQLite -->|Aggregate Logs| Dash
```

## Core Infrastructure Mapping

1. **Streamlit Tier**:
   - Deployed on **Databricks Apps** in production for secure workspace hosting.
   - Hosted locally on Python dev server.

2. **Database & Storage**:
   - **Local Mode**: Logs stored in local `loan_assessment_logs.db` SQLite table.
   - **Prod Mode**: Appends logs to a registered UC Delta table `main.loan_eligibility.loan_assessment_logs`.

3. **Language Models (LLM)**:
   - **Local Mode**: Integrates with offline Ollama endpoints (`llama3.2`).
   - **Prod Mode**: Calls high-throughput Databricks Foundation model endpoints (e.g. `meta-llama-3-1-70b-instruct`).

4. **Policy Vector Search**:
   - **Local Mode**: Loads a serialized FAISS vector store generated from PDF policy chunks.
   - **Prod Mode**: Connects directly to a synchronized Delta-Sync Vector Search index in Unity Catalog.
