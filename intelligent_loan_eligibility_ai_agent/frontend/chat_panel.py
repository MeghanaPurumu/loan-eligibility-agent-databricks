import streamlit as st
import requests
import json
import logging
from typing import Any, Dict
from config import settings
import ui.components as ui

logger = logging.getLogger(__name__)

def render_chat_panel(result: Dict[str, Any], payload: Dict[str, Any]):
    """
    Renders the assessment result and interactive chat panel on the right side.
    """
    ui.start_card()
    ui.render_section_header("AI Loan Assessment Verdict", "🤖")

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
                st.markdown(f"- 📄 {d}")
        else:
            st.write("No document submission guidelines specified.")

    st.markdown("<hr style='border: 1px solid #ffe5b4;'>", unsafe_allow_html=True)
    ui.render_disclaimer()
    ui.end_card()

    # ------------------ CONVERSATIONAL ASSISTANT ------------------
    ui.start_card()
    ui.render_section_header("Conversational Follow-up", "💬")
    st.write("Review the assessment and ask follow-up questions (e.g. *'Why was I rejected?'* or *'What should I improve?'*):")

    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    # Display chat transcripts
    for message in st.session_state["chat_history"]:
        role = message["role"]
        avatar = "👤" if role == "user" else "🤖"
        with st.chat_message(role, avatar=avatar):
            st.markdown(message["content"])

    # Chat Input Box
    if user_query := st.chat_input("Type your question here..."):
        # Append User input
        st.session_state["chat_history"].append({"role": "user", "content": user_query})
        with st.chat_message("user", avatar="👤"):
            st.markdown(user_query)

        # Generate Assistant response
        with st.spinner("Analyzing credit context..."):
            ai_response = call_followup_agent(user_query, payload, result)
        
        # Append Assistant response
        st.session_state["chat_history"].append({"role": "assistant", "content": ai_response})
        with st.chat_message("assistant", avatar="🤖"):
            st.markdown(ai_response)
        st.rerun()

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
    - Never guarantee loan approvals.
    - Be polite, professional, and clear.
    - Use data and rule constraints in explanations.
    """

    user_prompt = f"""
    Conversation History:
    {history_str}

    Customer Question: {query}
    """

    if settings.MODEL_PROVIDER.lower() == "databricks":
        response = call_databricks(system_prompt, user_prompt)
    else:
        response = call_ollama(system_prompt, user_prompt)
        
    if not response:
        # Dynamic Rule-Based Fallback when LLM is unreachable
        query_lower = query.lower()
        verdict = result.get('decision', 'Not Eligible')
        factors = result.get('evaluation_factors', [])
        
        if any(w in query_lower for w in ["improve", "better", "fix", "change"]):
            response = (f"**[Rule-Based Fallback]** To improve your eligibility, please focus on optimizing your key parameters: "
                        f"{' | '.join(factors)}. Consider increasing your income, improving your credit score, or reducing existing liabilities to lower your Debt-To-Income (DTI) ratio.")
        elif any(w in query_lower for w in ["why", "reason", "reject", "decline"]):
            response = (f"**[Rule-Based Fallback]** Your assessment resulted in '{verdict}'. The decision was primarily influenced by your parameters: "
                        f"{' | '.join(factors)}. Please review the AI Underwriter Report tab for the detailed scoring breakdown.")
        else:
            response = (f"**[Rule-Based Fallback]** Your assessment verdict is {verdict}. "
                        f"I am currently operating offline. Please review the AI Underwriter Report tab for detailed policy flags.")

    return response

def call_ollama(system: str, prompt: str) -> str:
    url = f"{settings.OLLAMA_BASE_URL}/api/chat"
    payload = {
        "model": settings.OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt}
        ],
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_predict": 250,
            "num_ctx": 2048
        }
    }
    try:
        response = requests.post(url, json=payload, timeout=90)
        response.raise_for_status()
        return response.json().get("message", {}).get("content", "").strip()
    except Exception as e:
        logger.warning(f"Ollama follow-up failed: {e}")
        return ""

def call_databricks(system: str, prompt: str) -> str:
    host = settings.DATABRICKS_HOST
    token = settings.DATABRICKS_TOKEN
    endpoint = settings.DATABRICKS_SERVING_ENDPOINT

    if not host or not token or not endpoint:
        logger.warning("Databricks Model Serving is unconfigured.")
        return ""

    url = f"{host.rstrip('/')}/serving-endpoints/{endpoint}/invocations"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2,
        "max_tokens": 300
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=12)
        response.raise_for_status()
        choices = response.json().get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "").strip()
        return "No serving response received."
    except Exception as e:
        logger.error(f"Databricks follow-up failed: {e}")
        return ""
