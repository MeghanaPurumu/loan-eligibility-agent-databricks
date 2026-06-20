import streamlit as st
import pandas as pd
from pathlib import Path
import ui.components as ui

DATA_PATH = Path(__file__).parent.parent / "data" / "mock_customers.csv"

def render_customer_form(rules):
    """
    Renders the customer profile input form on the left pane.
    Returns:
        (bool, dict): submitted state and user payload.
    """
    ui.start_card()
    ui.render_section_header("Customer Profile", "👤")

    # --- Session State Defaults ---
    fields = [
        "name", "age", "credit_score", "monthly_income", "employment_type", 
        "existing_loan", "monthly_loan_payment", "loan_purpose", "loan_amount_requested"
    ]
    for f in fields:
        if f not in st.session_state:
            if "score" in f:
                st.session_state[f] = 300
            else:
                st.session_state[f] = "" if "name" in f or "purpose" in f else 0
    
    # Manual overrides for specific types
    if not st.session_state["employment_type"]: 
        st.session_state["employment_type"] = "Salaried"
    if not st.session_state["existing_loan"]: 
        st.session_state["existing_loan"] = "No"

    # Inputs linked to Session State
    name = st.text_input("Full Name", value=st.session_state["name"], placeholder="e.g. John Doe")
    c1, c2 = st.columns(2)
    with c1:
        age = st.number_input("Age", min_value=0, max_value=100, value=int(st.session_state["age"]))
    with c2:
        credit_score = st.number_input("Credit Score", min_value=300, max_value=900, value=int(st.session_state["credit_score"]))
    
    monthly_income = st.number_input("Monthly Income (INR)", min_value=0, value=int(st.session_state["monthly_income"]), step=1000)
    employment_type = st.selectbox(
        "Employment Type",
        ["Salaried", "Self-employed", "Business", "Student", "Unemployed", "Retired"],
        index=["Salaried", "Self-employed", "Business", "Student", "Unemployed", "Retired"].index(st.session_state["employment_type"])
    )
    
    # Liabilities
    existing_loan = st.selectbox(
        "Do you have an existing loan?", ["No", "Yes"],
        index=0 if st.session_state["existing_loan"] == "No" else 1
    )
    monthly_loan_payment = st.session_state["monthly_loan_payment"]
    if existing_loan == "Yes":
        monthly_loan_payment = st.number_input(
            "Monthly EMI/Payment Amount (INR)", min_value=0, value=int(st.session_state["monthly_loan_payment"]), step=500
        )
    else:
        monthly_loan_payment = 0
    
    loan_purpose = st.text_input("Purpose of the Loan", value=st.session_state["loan_purpose"], placeholder="e.g. Home Renovation, Education")
    loan_amount_requested = st.number_input(
        "Loan Amount Requested (INR)", min_value=0, value=int(st.session_state["loan_amount_requested"]), step=5000
    )

    st.markdown("<br>", unsafe_allow_html=True)
    submitted = st.button("Launch Assessment", type="primary", use_container_width=True)
    ui.end_card()

    # Renders the Bank Policy rules box inside the left pane
    ui.start_card()
    ui.render_section_header("Bank Underwriting Guidelines", "📋")
    m1, m2 = st.columns(2)
    with m1:
        st.metric("Min Age", f"{rules['thresholds']['min_age']} yrs")
    with m2:
        st.metric("Min Score", rules["thresholds"]["minimum_credit_score"])
    
    st.metric("Min Income Requirement", f'₹{rules["thresholds"]["conditional_min_income_monthly"]:,}')
    st.info("Direct guidelines synced from Unity Catalog.")
    ui.end_card()

    return submitted, {
        "name": name,
        "age": age,
        "monthly_income": monthly_income,
        "employment_type": employment_type,
        "credit_score": credit_score,
        "existing_loan": existing_loan,
        "monthly_loan_payment": monthly_loan_payment,
        "loan_purpose": loan_purpose,
        "loan_amount_requested": loan_amount_requested,
    }
