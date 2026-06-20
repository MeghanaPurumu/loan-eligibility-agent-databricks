import sqlite3
import pandas as pd
import streamlit as st
import ui.components as ui
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "loan_assessment_logs.db"

def render_dashboard():
    """
    Renders analytics visualization dashboard summarizing application decisions,
    latency levels, and guardrail violations.
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
        # Create mock data
        df = pd.DataFrame([
            {"decision": "Eligible", "guardrail_status": "Compliant", "latency": 1.2},
            {"decision": "Eligible", "guardrail_status": "Compliant", "latency": 1.5},
            {"decision": "Conditionally Eligible", "guardrail_status": "Compliant", "latency": 1.9},
            {"decision": "Not Eligible", "guardrail_status": "Compliant", "latency": 0.8},
            {"decision": "Not Eligible", "guardrail_status": "Blocked (Input Guardrail)", "latency": 0.2},
            {"decision": "Eligible", "guardrail_status": "Compliant", "latency": 2.1},
            {"decision": "Not Eligible", "guardrail_status": "Compliant", "latency": 1.1},
        ])

    total_apps = len(df)
    eligible_count = len(df[df["decision"] == "Eligible"])
    eligible_pct = round((eligible_count / total_apps * 100), 1) if total_apps else 0.0
    
    violations_count = len(df[df["guardrail_status"].str.contains("Blocked|Violation|Sanitized", case=False, na=False)])
    avg_latency = round(df["latency"].mean(), 2) if total_apps else 0.0

    # Layout Metrics Row
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        ui.start_card()
        st.metric("Total Applications", total_apps)
        ui.end_card()
    with m2:
        ui.start_card()
        st.metric("Eligible Approval Rate", f"{eligible_pct}%")
        ui.end_card()
    with m3:
        ui.start_card()
        st.metric("Guardrail Violations", violations_count, delta=None)
        ui.end_card()
    with m4:
        ui.start_card()
        st.metric("Avg Latency", f"{avg_latency}s")
        ui.end_card()

    col_left, col_right = st.columns([1, 1], gap="large")
    
    with col_left:
        ui.start_card()
        st.subheader("Decision Distribution")
        decision_counts = df["decision"].value_counts()
        st.bar_chart(decision_counts)
        ui.end_card()
        
    with col_right:
        ui.start_card()
        st.subheader("Recent System Log Transactions")
        st.dataframe(
            df[["decision", "guardrail_status", "latency"]].tail(10),
            use_container_width=True,
            hide_index=True
        )
        ui.end_card()
