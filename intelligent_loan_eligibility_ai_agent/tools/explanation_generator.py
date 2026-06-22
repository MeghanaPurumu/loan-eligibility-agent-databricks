import logging
from typing import Any, Dict, List
from config import settings
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)

# System Prompt for Loan Explanation
SYSTEM_PROMPT = """
You are a senior banking underwriter AI agent for an Intelligent Loan Eligibility System.
Provide a clear, detailed, and professional explanation of the loan eligibility decision.

Rules:
- State whether the applicant is Eligible, Conditionally Eligible, or Not Eligible.
- Explain the key factors (Income, Credit Score, DTI, Employment).
- NEVER give guaranteed approval. Use terms like "Preliminary eligibility assessment" or "Subject to verification".
- If the applicant is Not Eligible due to low income, suggest they improve their income.
- Write 3-4 bullet points in professional banking terminology.
- Include a standard regulatory disclaimer.
"""

def generate_explanation(
    customer_data: Dict[str, Any],
    verdict: str,
    score: int,
    factors: Dict[str, Any],
    reasons: List[str],
    retrieved_policy: str
) -> str:
    """
    Generates natural language reasoning report using Langchain LLM abstractions.
    Falls back to a deterministic generator if model invocation fails.
    """
    user_prompt = f"""
    Evaluate the following application:
    Customer: {customer_data.get('name', 'Applicant')}
    Requested Amount: INR {customer_data.get('loan_amount_requested', 0):,}
    Verdict: {verdict}
    Score: {score}/100
    Rule engine factors: {factors}
    Rule engine flags: {reasons}
    Policy Context: {retrieved_policy}

    Please write a clean credit underwriter evaluation report.
    """

    try:
        if settings.MODEL_PROVIDER.lower() == "databricks":
            from langchain_community.chat_models.databricks import ChatDatabricks
            llm = ChatDatabricks(
                endpoint=settings.DATABRICKS_SERVING_ENDPOINT,
                temperature=0.2,
                max_tokens=512
            )
        else:
            from langchain_ollama import ChatOllama
            llm = ChatOllama(
                model=settings.OLLAMA_MODEL,
                base_url=settings.OLLAMA_BASE_URL,
                temperature=0.2
            )
            
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_prompt)
        ]
        response_msg = llm.invoke(messages)
        explanation = response_msg.content.strip()
    except Exception as e:
        logger.error(f"LLM Reasoning Generation failed: {e}")
        explanation = ""

    if not explanation:
        logger.warning("LLM generation failed or returned empty. Using deterministic fallback report.")
        explanation = build_deterministic_report(customer_data, verdict, score, factors, reasons, retrieved_policy)

    return explanation

def build_deterministic_report(
    customer_data: Dict[str, Any],
    verdict: str,
    score: int,
    factors: Dict[str, Any],
    reasons: List[str],
    retrieved_policy: str
) -> str:
    """Deterministic fallback in case LLM endpoints are unreachable."""
    name = customer_data.get("name", "Applicant")
    income = customer_data.get("monthly_income", 0)
    credit = customer_data.get("credit_score", 0)
    requested = customer_data.get("loan_amount_requested", 0)
    
    reasons_str = "\n".join([f"- {r}" for r in reasons]) if reasons else "- Profile complies with baseline standards."

    report = f"""### 1. Underwriting Decision Summary
- **Verdict:** {verdict}
- **Credit Score Assessment:** {score}/100
- **Process Mode:** Local Rule Engine Policy Evaluation

### 2. Underwriter Assessment
- **Applicant Name:** {name}
- **Monthly Verified Income:** INR {income:,}
- **Credit Bureau Score:** {credit}
- **Requested Capital:** INR {requested:,}

### 3. Key Policy Rule Violations/Flags
{reasons_str}

### 4. Supporting Policy Document Findings
{retrieved_policy}
"""
    return report
