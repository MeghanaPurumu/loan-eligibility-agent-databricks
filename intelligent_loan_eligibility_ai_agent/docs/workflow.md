# Agent Execution Workflow & Sequence Diagram

The **Loan Orchestrator** governs a sequential multi-stage evaluation pipeline to ensure safety, validation, deterministic rules execution, and compliance.

## Agent Sequence Flow

```mermaid
sequenceDiagram
    autonumber
    actor User as Customer / Loan Officer
    participant UI as Streamlit Web UI
    participant Orch as Loan Orchestrator
    participant IG as Input Guardrail
    participant Val as Customer Validator
    participant Eng as Eligibility Engine
    participant RAG as policy_retriever
    participant LLM as explanation_generator
    participant OG as Output Guardrail
    participant Audit as audit_logger

    User->>UI: Fill customer data & Launch Assessment
    UI->>Orch: Submit profile payload
    
    Note over Orch: Step 1: Input Guardrails Scan
    Orch->>IG: Check payload for injection & fraud
    alt Input Violation Blocked
        IG-->>Orch: Blocked! {"blocked": true, "reason": "policy violation"}
        Orch->>Audit: Log Blocked Status
        Orch-->>UI: Render Suspended assessment warning
    else Input Guardrail Passed
        IG-->>Orch: Clean! {"blocked": false}
        
        Note over Orch: Step 2: Validate Fields
        Orch->>Val: Run validator check (age, income, credit)
        alt Validation Fails
            Val-->>Orch: Invalid! {"valid": false, "missing_fields": [...]}
            Orch->>Audit: Log Validation Failure Status
            Orch-->>UI: Render incomplete profile warning
        else Validation Passes
            Val-->>Orch: Valid! {"valid": true}

            Note over Orch: Step 3: Eligibility Rule Engine
            Orch->>Eng: Evaluate loan rules
            Eng-->>Orch: Eligibility Verdict & Score

            Note over Orch: Step 4: Policy RAG Retrieval
            Orch->>RAG: Retrieve policy context
            RAG-->>Orch: Policy Chunks & Retrieval Confidence

            Note over Orch: Step 5: Deterministic Confidence
            Note over Orch: Compute confidence level (HIGH/MODERATE/LOW) without LLM

            Note over Orch: Step 6: Generate AI Explanation
            Orch->>LLM: Generate report (Ollama / Databricks Serving)
            LLM-->>Orch: natural language report markdown

            Note over Orch: Step 7: Output Guardrail Compliance
            Orch->>OG: Sanitize response & check disclaimers
            OG-->>Orch: Sanity-checked Compliant Report

            Note over Orch: Step 8: Log Audit Trail
            Orch->>Audit: Save details (SQLite / Delta Lake)
            Audit-->>Orch: Confirm Save

            Orch-->>UI: Output structured results
            UI-->>User: Display Verdict & Enable Follow-up Chat
        end
    end
```

## Description of Stages

1. **Input Guardrail**: Scans the input text for SQL/Prompt injection terms (e.g. `ignore policy`, `approve anyway`) and fake credential requests.
2. **Customer Validator**: Ensures type correctness and boundary limits for data items (e.g., credit scores between 300 and 900).
3. **Eligibility Engine**: A pure Python deterministic rules check loading thresholds from `loan_rules.json`. No LLM hallucination is permitted here.
4. **Policy Retriever**: Queries vector store database. Supports local FAISS or synchronized Databricks Vector Search index.
5. **Confidence Engine**: Evaluates decision outcome parameters deterministically. Returns HIGH for approval, MODERATE for conditional approval, and LOW for rejections.
6. **Explanation Generator**: Invokes the language model to synthesize context details, rules output, and retrieved policy into a readable markdown report.
7. **Output Guardrail**: Validates the reasoning text, sanitizes over-promising sentences, and injects mandatory disclaimer boxes.
8. **Audit Logging**: Persists transactional metrics (application ID, session, timestamp, inputs, verdict, latency) for dashboard analytics.
