import logging
import requests
from typing import Any, Dict, List
from config import settings

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
    Generates natural language reasoning report using Ollama or Databricks Model Serving.
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

    if settings.MODEL_PROVIDER.lower() == "databricks":
        explanation = call_databricks_serving(user_prompt)
    else:
        explanation = call_ollama(user_prompt)

    if not explanation:
        logger.warning("LLM generation failed or returned empty. Using deterministic fallback report.")
        explanation = build_deterministic_report(customer_data, verdict, score, factors, reasons, retrieved_policy)

    return explanation

def call_ollama(prompt: str) -> str:
    """Invokes local Ollama chat API."""
    url = f"{settings.OLLAMA_BASE_URL}/api/chat"
    payload = {
        "model": settings.OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_predict": 350,
            "num_ctx": 2048
        }
    }
    try:
        response = requests.post(url, json=payload, timeout=90)
        response.raise_for_status()
        return response.json().get("message", {}).get("content", "").strip()
    except Exception as e:
        logger.warning(f"Ollama call failed: {e}")
        return ""

def call_databricks_serving(prompt: str) -> str:
    """Invokes Databricks Model Serving REST API endpoint."""
    host = settings.DATABRICKS_HOST
    token = settings.DATABRICKS_TOKEN
    endpoint = settings.DATABRICKS_SERVING_ENDPOINT

    if not host or not token or not endpoint:
        logger.warning("Databricks Model Serving is not fully configured.")
        return ""

    url = f"{host.rstrip('/')}/serving-endpoints/{endpoint}/invocations"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 512
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=12)
        response.raise_for_status()
        # Databricks endpoint response parses choices[0].message.content
        choices = response.json().get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "").strip()
        return ""
    except Exception as e:
        logger.error(f"Databricks Model Serving failed: {e}")
        return ""

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
