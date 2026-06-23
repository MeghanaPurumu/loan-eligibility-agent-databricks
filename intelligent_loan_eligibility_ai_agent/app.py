from __future__ import annotations
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from config import settings
from agents.loan_orchestrator import orchestrate_loan_assessment
from frontend.forms import render_customer_form
from frontend.chat_panel import render_chat_panel, render_conversational_chat
from frontend.dashboard import render_dashboard
import ui.components as ui

# Constants & Paths
APP_TITLE = "Intelligent Loan Eligibility AI Agent"
BASE_DIR = Path(__file__).parent
DATA_PATH = BASE_DIR / "data" / "mock_customers.csv"
STYLE_PATH = BASE_DIR / "styles.css"

# Configuration
st.set_page_config(page_title=APP_TITLE, layout="wide")

def load_styles():
    """Loads external CSS for the application."""
    if STYLE_PATH.exists():
        with open(STYLE_PATH) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    else:
        st.error("Stylesheet missing!")

def main():
    load_styles()

    # Load rules for banking policy parameters Display on Left sidebar/Form
    rules_path = settings.RULES_PATH
    if rules_path.exists():
        rules = json.loads(rules_path.read_text(encoding="utf-8"))
    else:
        st.error("Rules configuration not found!")
        st.stop()

    # --- Session State Initialization ---
    if "assessment_result" not in st.session_state:
        st.session_state["assessment_result"] = None
    if "has_assessed" not in st.session_state:
        st.session_state["has_assessed"] = False
    if "active_payload" not in st.session_state:
        st.session_state["active_payload"] = {}

    # --- Sidebar Controls ---
    with st.sidebar:
        st.title("Settings")
        st.info("Banking Agent Control Panel")

        # Page Selection Switch
        page = st.radio(
            "Go to Page:",
            ["Assessment Workspace", "Conversational Follow-up", "Analytics Dashboard"],
            index=0
        )
        
        st.divider()
        
        # --- Existing User Lookup ---
        st.subheader("Customer Directory")
        if DATA_PATH.exists():
            df = pd.read_csv(DATA_PATH)
            customer_names = df["name"].tolist()
            selected_customer = st.selectbox("Select Existing Applicant", ["-- New Applicant --"] + customer_names)
            
            if selected_customer != "-- New Applicant --":
                if st.button("Load Profile"):
                    row = df[df["name"] == selected_customer].iloc[0]
                    # Update Session State
                    st.session_state["name"] = row["name"]
                    st.session_state["age"] = int(row["age"])
                    st.session_state["monthly_income"] = int(row["monthly_income"])
                    st.session_state["employment_type"] = row["employment_type"]
                    st.session_state["credit_score"] = int(row["credit_score"])
                    st.session_state["monthly_loan_payment"] = int(row["existing_liabilities"])
                    st.session_state["existing_loan"] = "Yes" if int(row["existing_liabilities"]) > 0 else "No"
                    st.session_state["loan_amount_requested"] = int(row["loan_amount_requested"])
                    st.session_state["loan_purpose"] = "General Purchase" # Default for mock data
                    
                    st.session_state["assessment_result"] = None
                    st.session_state["has_assessed"] = False
                    st.session_state["chat_history"] = []
                    st.rerun()
        
        st.divider()
        if st.button("Reset Assessment Session"):
            # Clear all
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
        
        st.divider()
        st.caption(f"v2.0 | Mode: {settings.MODE.upper()} | Provider: {settings.MODEL_PROVIDER.upper()}")

    # Render Active Page
    if page == "Analytics Dashboard":
        render_dashboard()
    elif page == "Conversational Follow-up":
        ui.render_hero(f"{APP_TITLE} - Chat")
        render_conversational_chat(
            st.session_state.get("assessment_result"),
            st.session_state.get("active_payload")
        )
    else:
        # Assessment Workspace layout
        ui.render_hero(APP_TITLE)
        
        col_form, col_chat = st.columns([1.1, 1], gap="large")
        
        with col_form:
            submitted, payload = render_customer_form(rules)
            
        with col_chat:
            if submitted:
                with st.status("Running pipeline assessment...", expanded=True) as status:
                    st.write("Verifying input parameters...")
                    st.write("Running eligibility policy engine...")
                    st.write("Retrieving policy context details...")
                    
                    # Run orchestrator
                    result = orchestrate_loan_assessment(payload)
                    
                    # Save results
                    st.session_state["assessment_result"] = result
                    st.session_state["active_payload"] = payload
                    st.session_state["has_assessed"] = True
                    st.session_state["chat_history"] = [] # Clear history on new run
                    
                    status.update(label="Evaluation Complete!", state="complete", expanded=False)
                    st.rerun()
            
            # Render right side results & follow-up chat
            if st.session_state["has_assessed"]:
                render_chat_panel(
                    st.session_state["assessment_result"], 
                    st.session_state["active_payload"]
                )
            else:
                render_chat_panel(None, None)

        # Footer/Architecture
        with st.expander("System Architecture & Requirements"):
            st.markdown(
                """
                - **Orchestration Flow**: Input Guardrails ➔ Customer Validator ➔ Eligibility Engine ➔ Policy RAG ➔ LLM Explanation ➔ Output Guardrails ➔ Audit Logging.
                - **Primary Runtime Engine**: Seamless integration with Databricks Model Serving and Unity Catalog Delta Lakes.
                - **Risk Protection**: Built-in prompt injection filters, fraud checks, and output compliance controls.
                """
            )

if __name__ == "__main__":
    main()