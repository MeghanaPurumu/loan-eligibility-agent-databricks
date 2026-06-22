import streamlit as st
import json
import re
import logging
from typing import Any, Dict
from config import settings
import ui.components as ui

from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)

# ── Guardrail patterns for conversational follow-up ─────────────────────────
BLOCKED_CHAT_PATTERNS = [
    r"ignore.*rules",
    r"ignore.*policy",
    r"bypass.*checks",
    r"approve.*anyway",
    r"override.*system",
    r"ignore all instructions",
    r"you are now",
    r"system.*prompt",
    r"set.*decision",
]

GUARANTEE_PATTERNS = [
    r"definitely.*approved",
    r"guarantee.*approval",
    r"guaranteed.*loan",
    r"will.*definitely.*get",
    r"absolutely.*approved",
]

MANDATORY_DISCLAIMER_SHORT = (
    "\n\n*This is an AI-generated response for decision-support only. "
    "It does not constitute a final credit approval.*"
)


def _check_chat_input_guardrail(user_query: str) -> str | None:
    """Returns a blocked message if the user query contains prompt injection attempts."""
    if not settings.ENABLE_GUARDRAILS:
        return None
    query_lower = user_query.lower()
    for pattern in BLOCKED_CHAT_PATTERNS:
        if re.search(pattern, query_lower):
            return (
                "Input Guardrail Triggered: Your message was flagged for attempting to "
                "override system policies. Please ask a legitimate question about your loan assessment."
            )
    return None


def _sanitize_llm_output(response: str) -> str:
    """Output guardrail: softens guarantee language and appends disclaimer."""
    if not settings.ENABLE_GUARDRAILS:
        return response
    for pattern in GUARANTEE_PATTERNS:
        if re.search(pattern, response, re.IGNORECASE):
            response = re.sub(
                pattern,
                "subject to credit verification and formal approval",
                response,
                flags=re.IGNORECASE,
            )
    if "does not constitute" not in response.lower():
        response += MANDATORY_DISCLAIMER_SHORT
    return response


def render_chat_panel(result: Dict[str, Any], payload: Dict[str, Any]):
    """
    Renders the assessment result and interactive chat panel on the right side.
    """
    ui.start_card()
    ui.render_section_header("AI Loan Assessment Verdict")

    if not result:
        st.info("Fill out the Customer Profile and click 'Launch Assessment' to run the evaluation.")
        ui.end_card()
        return

    # Render Verdict Metrics
    decision = result.get("decision", "Not Eligible")
    confidence = result.get("confidence", "LOW")
    disclaimer = result.get("disclaimer", "")
    reasoning = result.get("reasoning", "")
    docs = result.get("documents_required", [])

    c1, c2, c3 = st.columns(3)
    with c1:
        # Style verdict color based on decision
        color = "#2ecc71" if decision == "Eligible" else "#f1c40f" if decision == "Conditionally Eligible" else "#e74c3c"
        st.markdown(
            f'<div style="text-align: center; background: {color}15; border: 1px solid {color}; border-radius: 12px; padding: 0.6rem 0.2rem;">'
            f'<div class="metric-label" style="font-size: 0.85rem;">Decision</div>'
            f'<div class="metric-value" style="color: {color}; font-size: 1.3rem;">{decision}</div>'
            f'</div>',
            unsafe_allow_html=True
        )
    with c2:
        st.markdown(
            f'<div style="text-align: center; background: #3498db15; border: 1px solid #3498db; border-radius: 12px; padding: 0.6rem 0.2rem;">'
            f'<div class="metric-label" style="font-size: 0.85rem;">Confidence</div>'
            f'<div class="metric-value" style="color: #3498db; font-size: 1.3rem;">{confidence}</div>'
            f'</div>',
            unsafe_allow_html=True
        )
    with c3:
        st.markdown(
            f'<div style="text-align: center; background: #e67e2215; border: 1px solid #e67e22; border-radius: 12px; padding: 0.6rem 0.2rem;">'
            f'<div class="metric-label" style="font-size: 0.85rem;">Model Provider</div>'
            f'<div class="metric-value" style="color: #e67e22; font-size: 1.3rem;">{settings.MODEL_PROVIDER.upper()}</div>'
            f'</div>',
            unsafe_allow_html=True
        )

    st.markdown("<br>", unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["AI Underwriter Report", "Required Documents"])
    with tab1:
        st.markdown(reasoning)
    with tab2:
        if docs:
            st.markdown("##### The following verified documents must be submitted to proceed:")
            for d in docs:
                st.markdown(f"- {d}")
        else:
            st.write("No document submission guidelines specified.")

    st.markdown("<hr style='border: 1px solid #ffe5b4;'>", unsafe_allow_html=True)
    ui.render_disclaimer()
    ui.end_card()

    # ------------------ CONVERSATIONAL ASSISTANT ------------------
    ui.start_card()
    ui.render_section_header("Conversational Follow-up")
    st.write("Review the assessment and ask follow-up questions (e.g. *'Why was I rejected?'* or *'What should I improve?'*):")

    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    # Display chat transcripts
        role = message["role"]
        with st.chat_message(role):
            st.markdown(message["content"])

    # Chat Input Box
    if user_query := st.chat_input("Type your question here..."):
        # Append User input
        st.session_state["chat_history"].append({"role": "user", "content": user_query})
        with st.chat_message("user"):
            st.markdown(user_query)

        # ── Input Guardrail Check ────────────────────────────────────────
        blocked_msg = _check_chat_input_guardrail(user_query)
        if blocked_msg:
            ai_response = blocked_msg
        else:
            # Generate Assistant response
            with st.spinner("Analyzing credit context..."):
                ai_response = call_followup_agent(user_query, payload, result)
        
        # Append Assistant response
        st.session_state["chat_history"].append({"role": "assistant", "content": ai_response})
        with st.chat_message("assistant"):
            st.markdown(ai_response)

    ui.end_card()

def call_followup_agent(query: str, payload: Dict[str, Any], result: Dict[str, Any]) -> str:
    """Helper to call LLM model with conversation context for follow-up questions."""
    history_str = "\n".join([f"{msg['role'].capitalize()}: {msg['content']}" for msg in st.session_state["chat_history"][:-1]])
    
    system_prompt = f"""
    You are an Intelligent Loan Assistant. Answer customer follow-up questions based on their assessment.
    Customer Data: {json.dumps(payload)}
    Verdict: {result.get('decision')}
    Confidence: {result.get('confidence')}
    Orchestration factors: {result.get('evaluation_factors')}

    Rules:
    - Never guarantee loan approvals. Use terms like "subject to verification" or "preliminary assessment".
    - Be polite, professional, and clear.
    - Use data and rule constraints in explanations.
    - Always mention specific numbers from the customer data when explaining decisions.
    - If the customer asks about improving eligibility, give actionable advice.
    """

    user_prompt = f"""
    Conversation History:
    {history_str}

    Customer Question: {query}
    """

    try:
        if settings.MODEL_PROVIDER.lower() == "databricks":
            from langchain_community.chat_models import ChatDatabricks
            llm = ChatDatabricks(
                endpoint=settings.DATABRICKS_SERVING_ENDPOINT,
                temperature=0.2,
                max_tokens=500
            )
        else:
            from langchain_ollama import ChatOllama
            llm = ChatOllama(
                model=settings.OLLAMA_MODEL,
                base_url=settings.OLLAMA_BASE_URL,
                temperature=0.2
            )
            
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        response_msg = llm.invoke(messages)
        response = response_msg.content.strip()
    except Exception as e:
        logger.error(f"LLM follow-up failed: {e}")
        st.error(f"LLM Connection Failed: {e}")
        response = ""
        
    if not response:
        # Dynamic Rule-Based Fallback when LLM is unreachable
        response = _build_rule_based_response(query, payload, result)

    # ── Output Guardrail ─────────────────────────────────────────────────
    response = _sanitize_llm_output(response)

    return response


def _build_rule_based_response(query: str, payload: Dict[str, Any], result: Dict[str, Any]) -> str:
    """Generates a detailed rule-based response when the LLM is unreachable."""
    query_lower = query.lower()
    
    # Simple Greeting Handling
    if query_lower in ["hi", "hello", "hey", "greetings"]:
        return "Hello! I am your AI Loan Assessment assistant. How can I help you understand your loan decision today?"

    verdict = result.get('decision', 'Not Eligible')
    factors = result.get('evaluation_factors', [])
    
    # Extract customer data for personalized responses
    income = payload.get('monthly_income', 0)
    credit_score = payload.get('credit_score', 0)
    loan_amount = payload.get('loan_amount_requested', 0)
    existing_emi = payload.get('monthly_loan_payment', 0)
    employment = payload.get('employment_type', 'Unknown')
    dti = round((existing_emi / income * 100), 1) if income else 0

    if any(w in query_lower for w in ["improve", "better", "fix", "change", "increase", "how can", "what should"]):
        tips = []
        if credit_score < 750:
            tips.append(f"**Improve Credit Score**: Your current score is {credit_score}. A score of 750+ qualifies for premium rates. Pay bills on time and reduce credit utilization.")
        if income < 50000:
            tips.append(f"**Increase Income**: Your monthly income of ₹{income:,} is below the preferred threshold of ₹50,000. Consider additional income sources or wait for a salary increment.")
        if dti > 25:
            tips.append(f"**Reduce Existing Debt**: Your DTI ratio is {dti}%. Aim for below 25% by clearing existing liabilities (current EMI: ₹{existing_emi:,}).")
        if loan_amount > income * 15:
            tips.append(f"**Lower Loan Amount**: ₹{loan_amount:,} is high relative to your income. Consider requesting a smaller amount.")
        if employment in ["Student", "Unemployed"]:
            tips.append(f"**Employment Status**: '{employment}' is categorized as high-risk. Salaried employment significantly improves eligibility.")
        if not tips:
            tips.append("Your profile is already competitive. Maintain your credit score and income stability.")
        
        response = f"Based on your profile analysis, here are actionable steps to improve your eligibility:\n\n" + "\n\n".join(f"- {t}" for t in tips)

    elif any(w in query_lower for w in ["why", "reason", "reject", "decline", "not eligible", "denied"]):
        reasons = []
        if credit_score < 600:
            reasons.append(f"Credit score ({credit_score}) is below the minimum threshold of 600.")
        elif credit_score < 750:
            reasons.append(f"Credit score ({credit_score}) is acceptable but below the preferred 750+ threshold, which may have reduced your overall score.")
        if income < 30000:
            reasons.append(f"Monthly income (₹{income:,}) is below the minimum baseline of ₹30,000.")
        elif income < 50000:
            reasons.append(f"Monthly income (₹{income:,}) meets the conditional threshold but not the preferred ₹50,000 baseline.")
        if dti > 40:
            reasons.append(f"Debt-to-Income ratio ({dti}%) exceeds the maximum cap of 40%.")
        elif dti > 25:
            reasons.append(f"Debt-to-Income ratio ({dti}%) is above the preferred 25% threshold.")
        if employment in ["Student", "Unemployed"]:
            reasons.append(f"Employment type '{employment}' is classified as high-risk under bank policy.")
        if loan_amount > income * 20:
            reasons.append(f"Requested amount (₹{loan_amount:,}) exceeds the maximum 20x income multiple.")
        if not reasons:
            reasons.append("The combination of your profile factors resulted in a score below the eligibility threshold.")
        
        response = (f"Your assessment resulted in **{verdict}**. Here are the contributing factors:\n\n"
                    + "\n".join(f"- {r}" for r in reasons))

    elif "documents" in query_lower or "submit" in query_lower:
        if verdict == "Eligible":
            response = ("To finalize your loan, please submit:\n"
                       "- Government Issued ID (PAN/Aadhaar)\n"
                       "- Proof of Address\n"
                       "- Last 3 Months Salary Slips\n"
                       "- Bank Statements (Last 6 Months)")
        elif verdict == "Conditionally Eligible":
            response = ("To proceed with conditional review, please submit:\n"
                       "- Government Issued ID (PAN/Aadhaar)\n"
                       "- Proof of Address\n"
                       "- Last 6 Months Salary Slips or Form 16\n"
                       "- Bank Statements (Last 6 Months)\n"
                       "- Proof of Additional Assets or Guarantor Details")
        else:
            response = ("If you plan to re-apply, you will typically need:\n"
                       "- Government Issued ID (PAN/Aadhaar)\n"
                       "- Proof of Income\n"
                       "- Credit Score Rectification Statement")

    elif any(w in query_lower for w in ["score", "rating", "points", "breakdown"]):
        response = (f"Your assessment breakdown:\n\n"
                   f"- **Decision**: {verdict}\n"
                   f"- **Monthly Income**: ₹{income:,}\n"
                   f"- **Credit Score**: {credit_score}\n"
                   f"- **Employment**: {employment}\n"
                   f"- **DTI Ratio**: {dti}%\n"
                   f"- **Loan Requested**: ₹{loan_amount:,}\n\n"
                   f"Key evaluation factors: {' | '.join(factors)}")

    elif any(w in query_lower for w in ["eligible", "status", "result", "verdict", "decision"]):
        response = (f"Your loan assessment verdict is **{verdict}** with **{result.get('confidence', 'N/A')}** confidence.\n\n"
                   f"This decision was based on your income (₹{income:,}), credit score ({credit_score}), "
                   f"employment type ({employment}), and debt-to-income ratio ({dti}%).")

    else:
        response = (
            f"I am currently experiencing issues connecting to my local language model. "
            f"To answer your question directly based on the deterministic engine:\n\n"
            f"Your application was marked as **{verdict}**. The primary factors for this decision were:\n{', '.join(factors)}"
        )

    return response
