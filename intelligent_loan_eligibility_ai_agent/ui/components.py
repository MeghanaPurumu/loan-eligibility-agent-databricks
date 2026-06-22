import streamlit as st

def render_hero(title):
    """Renders the premium animated hero section."""
    st.markdown(
        f"""
        <div class="hero-container">
            <h1>{title}</h1>
            <p>Smart, Transparent, and Instant Loan Eligibility Assessment</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

def render_section_header(title):
    """Renders a styled section title."""
    st.markdown(
        f'<div class="section-title">{title}</div>', 
        unsafe_allow_html=True
    )

def render_metric(label, value):
    """Renders a custom styled metric."""
    st.markdown(
        f"""
        <div style="margin-bottom: 1rem;">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

def render_disclaimer():
    """Renders the bank disclaimer box."""
    st.markdown(
        """
        <div class="disclaimer-box">
            <b>Disclaimer:</b> This result is for demonstration and training purposes only. 
            Official bank approval requires manual verification and physical documentation.
        </div>
        """, 
        unsafe_allow_html=True
    )

def start_card():
    """Starts a glassmorphic card container."""
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)

def end_card():
    """Ends a glassmorphic card container."""
    st.markdown('</div>', unsafe_allow_html=True)
