import time
import uuid
from typing import Any, Dict
from config import settings
from guardrails.input_guard import check_input
from guardrails.output_guard import sanitize_and_check_output, MANDATORY_DISCLAIMER
from tools.customer_validator import validate_customer_data
from tools.eligibility_engine import evaluate_eligibility
from tools.confidence_calculator import calculate_confidence
from tools.policy_retriever import retrieve
from tools.explanation_generator import generate_explanation
from tools.audit_logger import log_assessment

def orchestrate_loan_assessment(
    customer_data: Dict[str, Any], 
    session_id: str = None, 
    user_message: str = ""
) -> Dict[str, Any]:
    """
    Orchestrates the loan assessment flow in a strict sequence:
    1. Input Guardrails
    2. Customer Validation
    3. Eligibility Tool
    4. RAG Retrieval
    5. Deterministic Confidence Calculation
    6. LLM Reasoning Generation
    7. Output Guardrails
    8. Audit Logging
    9. Final Response Output
    """
    start_time = time.time()
    application_id = str(uuid.uuid4())
    if not session_id:
        session_id = str(uuid.uuid4())

    # 1. Input Guardrails
    guard_res = check_input(customer_data, user_message)
    if guard_res.get("blocked", False):
        latency = time.time() - start_time
        response = {
            "decision": "Not Eligible",
            "confidence": "LOW",
            "evaluation_factors": [],
            "reasoning": f"Application suspended: {guard_res.get('reason')}",
            "documents_required": [],
            "disclaimer": MANDATORY_DISCLAIMER
        }
        # Log immediately if audit is enabled
        log_assessment(
            application_id=application_id,
            session_id=session_id,
            customer_input=customer_data,
            decision="Blocked / Not Eligible",
            guardrail_status="Blocked (Input Guardrail)",
            latency=latency,
            retrieved_documents=[],
            model_name="N/A"
        )
        return response

    # 2. Customer Validation
    validator_res = validate_customer_data(customer_data)
    if not validator_res.get("valid", False):
        latency = time.time() - start_time
        missing_str = ", ".join(validator_res.get("missing_fields", []))
        err_str = ", ".join(validator_res.get("errors", []))
        
        reason_msg = "Please complete all profile details."
        if missing_str:
            reason_msg += f" Missing fields: {missing_str}."
        if err_str:
            reason_msg += f" Errors: {err_str}."

        response = {
            "decision": "Not Eligible",
            "confidence": "LOW",
            "evaluation_factors": [],
            "reasoning": reason_msg,
            "documents_required": [],
            "disclaimer": MANDATORY_DISCLAIMER
        }
        # Log validation failure
        log_assessment(
            application_id=application_id,
            session_id=session_id,
            customer_input=customer_data,
            decision="Not Eligible",
            guardrail_status="Passed (Input Guardrail) | Failed (Validation)",
            latency=latency,
            retrieved_documents=[],
            model_name="N/A"
        )
        return response

    # 3. Eligibility Tool (Rules Engine)
    eligibility_res = evaluate_eligibility(customer_data)
    verdict = eligibility_res.get("eligibility", "Not Eligible")
    score = eligibility_res.get("score", 0)
    factors = eligibility_res.get("key_factors", {})
    reasons = eligibility_res.get("reasons", [])

    # Determine required documents based on verdict
    if verdict == "Eligible":
        docs = ["Government Issued ID (PAN/Aadhaar)", "Proof of Address", "Last 3 Months Salary Slips", "Bank Statements (Last 6 Months)"]
    elif verdict == "Conditionally Eligible":
        docs = [
            "Government Issued ID (PAN/Aadhaar)", 
            "Proof of Address", 
            "Last 6 Months Salary Slips or Form 16", 
            "Bank Statements (Last 6 Months)",
            "Proof of Additional Assets or Guarantor Guarantee Details"
        ]
    else:
        docs = ["Government Issued ID (PAN/Aadhaar)", "Proof of Income", "Credit Score Rectification Statement"]

    # 4. RAG Retrieval
    query = f"loan eligibility criteria for {customer_data.get('employment_type')} age {customer_data.get('age')} credit score {customer_data.get('credit_score')}"
    retrieved_res = retrieve(query)
    policy_context = retrieved_res.get("policy", "")
    retrieved_docs = retrieved_res.get("documents", [])

    # 5. Deterministic Confidence Calculation
    confidence = calculate_confidence(eligibility_res, validator_res)

    # 6. LLM Reasoning Generation
    reasoning = generate_explanation(
        customer_data=customer_data,
        verdict=verdict,
        score=score,
        factors=factors,
        reasons=reasons,
        retrieved_policy=policy_context
    )

    # 7. Output Guardrails
    final_output = {
        "decision": verdict,
        "confidence": confidence,
        "evaluation_factors": [
            f"Income: {factors.get('monthly_income')}",
            f"Credit Score: {factors.get('credit_score')}",
            f"Existing Liabilities: {factors.get('existing_liabilities')}",
            f"Employment: {factors.get('employment_type')}"
        ],
        "reasoning": reasoning,
        "documents_required": docs,
        "disclaimer": MANDATORY_DISCLAIMER
    }
    final_output = sanitize_and_check_output(final_output)

    # 8. Audit Logging
    latency = time.time() - start_time
    model_name = settings.OLLAMA_MODEL if settings.MODEL_PROVIDER == "ollama" else settings.DATABRICKS_SERVING_ENDPOINT
    
    log_assessment(
        application_id=application_id,
        session_id=session_id,
        customer_input=customer_data,
        decision=final_output["decision"],
        guardrail_status="Compliant",
        latency=latency,
        retrieved_documents=retrieved_docs,
        model_name=model_name
    )

    return final_output
