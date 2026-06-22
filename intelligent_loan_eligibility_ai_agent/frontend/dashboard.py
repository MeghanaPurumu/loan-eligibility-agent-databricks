import sqlite3
import pandas as pd
import streamlit as st
import ui.components as ui
from pathlib import Path
import json

DB_PATH = Path(__file__).parent.parent / "loan_assessment_logs.db"

def render_dashboard():
    """
    Renders analytics visualization dashboard summarizing application decisions,
    latency levels, guardrail violations, and risk distribution.
    """
    ui.render_hero("Assessment Analytics Dashboard")
    
    # 1. Fetch data from SQLite logs
    data = []
    columns = [
        "application_id", "session_id", "timestamp", "customer_input", 
        "decision", "guardrail_status", "latency", "retrieved_documents", "model_name"
    ]
    
    if DB_PATH.exists():
        try:
            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM loan_assessment_logs")
            data = cursor.fetchall()
            conn.close()
        except Exception as e:
            st.error(f"Failed to load logs: {e}")
            
    df = pd.DataFrame(data, columns=columns) if data else pd.DataFrame(columns=columns)

    # 2. If no logs, show simulated stats to ensure visual richness
    if df.empty:
        st.warning("No applications recorded in the database yet. Showing mock demonstration stats.")
        # Create rich mock data for demonstration
        df = pd.DataFrame([
            {"decision": "Eligible", "guardrail_status": "Compliant", "latency": 1.2, "model_name": "databricks", "customer_input": json.dumps({"credit_score": 780, "monthly_income": 85000, "employment_type": "Salaried", "loan_amount_requested": 500000})},
            {"decision": "Eligible", "guardrail_status": "Compliant", "latency": 1.5, "model_name": "databricks", "customer_input": json.dumps({"credit_score": 820, "monthly_income": 120000, "employment_type": "Salaried", "loan_amount_requested": 800000})},
            {"decision": "Conditionally Eligible", "guardrail_status": "Compliant", "latency": 1.9, "model_name": "databricks", "customer_input": json.dumps({"credit_score": 680, "monthly_income": 45000, "employment_type": "Self-employed", "loan_amount_requested": 300000})},
            {"decision": "Not Eligible", "guardrail_status": "Compliant", "latency": 0.8, "model_name": "databricks", "customer_input": json.dumps({"credit_score": 520, "monthly_income": 25000, "employment_type": "Student", "loan_amount_requested": 200000})},
            {"decision": "Not Eligible", "guardrail_status": "Blocked (Input Guardrail)", "latency": 0.2, "model_name": "N/A", "customer_input": json.dumps({"credit_score": 450, "monthly_income": 15000, "employment_type": "Unemployed", "loan_amount_requested": 500000})},
            {"decision": "Eligible", "guardrail_status": "Compliant", "latency": 2.1, "model_name": "databricks", "customer_input": json.dumps({"credit_score": 760, "monthly_income": 95000, "employment_type": "Business", "loan_amount_requested": 600000})},
            {"decision": "Not Eligible", "guardrail_status": "Compliant", "latency": 1.1, "model_name": "databricks", "customer_input": json.dumps({"credit_score": 580, "monthly_income": 28000, "employment_type": "Salaried", "loan_amount_requested": 400000})},
            {"decision": "Conditionally Eligible", "guardrail_status": "Compliant", "latency": 1.7, "model_name": "databricks", "customer_input": json.dumps({"credit_score": 710, "monthly_income": 55000, "employment_type": "Self-employed", "loan_amount_requested": 700000})},
            {"decision": "Eligible", "guardrail_status": "Compliant", "latency": 1.3, "model_name": "databricks", "customer_input": json.dumps({"credit_score": 800, "monthly_income": 110000, "employment_type": "Salaried", "loan_amount_requested": 450000})},
            {"decision": "Not Eligible", "guardrail_status": "Blocked (Input Guardrail)", "latency": 0.15, "model_name": "N/A", "customer_input": json.dumps({"credit_score": 400, "monthly_income": 20000, "employment_type": "Unemployed", "loan_amount_requested": 1000000})},
        ])

    # ── Extract customer details from JSON for analytics ──────────────────
    def safe_parse(val):
        try:
            if isinstance(val, str):
                return json.loads(val)
            return {}
        except (json.JSONDecodeError, TypeError):
            return {}

    parsed = df["customer_input"].apply(safe_parse) if "customer_input" in df.columns else pd.Series([{}] * len(df))
    df["credit_score"] = parsed.apply(lambda x: x.get("credit_score", 0))
    df["monthly_income"] = parsed.apply(lambda x: x.get("monthly_income", 0))
    df["employment_type"] = parsed.apply(lambda x: x.get("employment_type", "Unknown"))
    df["loan_amount_requested"] = parsed.apply(lambda x: x.get("loan_amount_requested", 0))

    total_apps = len(df)
    eligible_count = len(df[df["decision"] == "Eligible"])
    cond_count = len(df[df["decision"] == "Conditionally Eligible"])
    not_eligible_count = len(df[df["decision"] == "Not Eligible"])
    eligible_pct = round((eligible_count / total_apps * 100), 1) if total_apps else 0.0
    
    violations_count = len(df[df["guardrail_status"].str.contains("Blocked|Violation|Sanitized", case=False, na=False)])
    avg_latency = round(df["latency"].mean(), 2) if total_apps else 0.0

    # ── KPI Metrics Row ──────────────────────────────────────────────────
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(
            f'<div style="text-align:center; background: #2ecc7115; border: 1px solid #2ecc71; border-radius: 12px; padding: 1rem;">'
            f'<div style="font-size:0.8rem; color:#aaa;">Total Applications</div>'
            f'<div style="font-size:2rem; font-weight:700; color:#2ecc71;">{total_apps}</div>'
            f'</div>', unsafe_allow_html=True
        )
    with m2:
        st.markdown(
            f'<div style="text-align:center; background: #3498db15; border: 1px solid #3498db; border-radius: 12px; padding: 1rem;">'
            f'<div style="font-size:0.8rem; color:#aaa;">Approval Rate</div>'
            f'<div style="font-size:2rem; font-weight:700; color:#3498db;">{eligible_pct}%</div>'
            f'</div>', unsafe_allow_html=True
        )
    with m3:
        violation_color = "#e74c3c" if violations_count > 0 else "#2ecc71"
        st.markdown(
            f'<div style="text-align:center; background: {violation_color}15; border: 1px solid {violation_color}; border-radius: 12px; padding: 1rem;">'
            f'<div style="font-size:0.8rem; color:#aaa;">Guardrail Violations</div>'
            f'<div style="font-size:2rem; font-weight:700; color:{violation_color};">{violations_count}</div>'
            f'</div>', unsafe_allow_html=True
        )
    with m4:
        st.markdown(
            f'<div style="text-align:center; background: #e67e2215; border: 1px solid #e67e22; border-radius: 12px; padding: 1rem;">'
            f'<div style="font-size:0.8rem; color:#aaa;">Avg Latency</div>'
            f'<div style="font-size:2rem; font-weight:700; color:#e67e22;">{avg_latency}s</div>'
            f'</div>', unsafe_allow_html=True
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Chart Row 1: Decision Distribution + Credit Score vs Decision ─────
    col_left, col_right = st.columns([1, 1], gap="large")
    
    with col_left:
        ui.start_card()
        st.subheader("Loan Decision Distribution")
        decision_data = pd.DataFrame({
            "Decision": ["Eligible", "Conditionally Eligible", "Not Eligible"],
            "Count": [eligible_count, cond_count, not_eligible_count]
        })
        st.bar_chart(decision_data.set_index("Decision"), color="#6C63FF")
        st.caption("Distribution of loan assessment outcomes across all processed applications.")
        ui.end_card()
        
    with col_right:
        ui.start_card()
        st.subheader("Credit Score vs Loan Decision")
        # Create a scatter-like chart using credit score grouped by decision
        if not df.empty and df["credit_score"].sum() > 0:
            scatter_data = df[["credit_score", "decision"]].copy()
            scatter_data = scatter_data[scatter_data["credit_score"] > 0]
            pivot = scatter_data.groupby("decision")["credit_score"].mean().reset_index()
            pivot.columns = ["Decision", "Avg Credit Score"]
            st.bar_chart(pivot.set_index("Decision"), color="#FF6B6B")
            st.caption("Average credit score segmented by loan decision outcome. Higher scores correlate with approval.")
        else:
            st.info("No credit score data available yet.")
        ui.end_card()

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Chart Row 2: Employment Risk + Latency Analysis ──────────────────
    col_left2, col_right2 = st.columns([1, 1], gap="large")
    
    with col_left2:
        ui.start_card()
        st.subheader("Employment Type Risk Analysis")
        if not df.empty and df["employment_type"].nunique() > 0:
            emp_decision = df.groupby(["employment_type", "decision"]).size().reset_index(name="count")
            emp_pivot = emp_decision.pivot(index="employment_type", columns="decision", values="count").fillna(0)
            st.bar_chart(emp_pivot)
            st.caption("Breakdown of loan decisions by applicant employment type — key risk factor in underwriting.")
        else:
            st.info("No employment data available yet.")
        ui.end_card()

    with col_right2:
        ui.start_card()
        st.subheader("Pipeline Latency Distribution")
        if not df.empty and "latency" in df.columns:
            latency_data = df[["latency", "decision"]].copy()
            latency_pivot = latency_data.groupby("decision")["latency"].mean().reset_index()
            latency_pivot.columns = ["Decision", "Avg Latency (s)"]
            st.bar_chart(latency_pivot.set_index("Decision"), color="#F39C12")
            st.caption("Average processing time per decision category. Blocked requests resolve fastest via guardrails.")
        else:
            st.info("No latency data available yet.")
        ui.end_card()

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Guardrail Compliance Summary ─────────────────────────────────────
    ui.start_card()
    st.subheader("Guardrail Compliance Overview")
    g1, g2, g3 = st.columns(3)
    
    compliant = len(df[df["guardrail_status"] == "Compliant"])
    blocked = len(df[df["guardrail_status"].str.contains("Blocked", case=False, na=False)])
    sanitized = len(df[df["guardrail_status"].str.contains("Sanitized", case=False, na=False)])
    
    with g1:
        st.markdown(
            f'<div style="text-align:center; padding:0.8rem; background:#2ecc7110; border-radius:10px;">'
            f'<div style="font-size:2rem;">Compliant</div>'
            f'<div style="font-size:1.5rem; font-weight:700; color:#2ecc71;">{compliant}</div>'
            f'<div style="font-size:0.8rem; color:#aaa;">Compliant</div>'
            f'</div>', unsafe_allow_html=True
        )
    with g2:
        st.markdown(
            f'<div style="text-align:center; padding:0.8rem; background:#e74c3c10; border-radius:10px;">'
            f'<div style="font-size:2rem;">Blocked</div>'
            f'<div style="font-size:1.5rem; font-weight:700; color:#e74c3c;">{blocked}</div>'
            f'<div style="font-size:0.8rem; color:#aaa;">Blocked (Input)</div>'
            f'</div>', unsafe_allow_html=True
        )
    with g3:
        st.markdown(
            f'<div style="text-align:center; padding:0.8rem; background:#f39c1210; border-radius:10px;">'
            f'<div style="font-size:2rem;">Sanitized</div>'
            f'<div style="font-size:1.5rem; font-weight:700; color:#f39c12;">{sanitized}</div>'
            f'<div style="font-size:0.8rem; color:#aaa;">Output Sanitized</div>'
            f'</div>', unsafe_allow_html=True
        )
    ui.end_card()

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Transaction Log Table ────────────────────────────────────────────
    ui.start_card()
    st.subheader("Recent Assessment Transactions")
    display_cols = ["decision", "guardrail_status", "latency"]
    if "model_name" in df.columns:
        display_cols.append("model_name")
    st.dataframe(
        df[display_cols].tail(15),
        use_container_width=True,
        hide_index=True
    )
    ui.end_card()
