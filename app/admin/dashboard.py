"""Streamlit Admin Dashboard for CLE Engine."""
import streamlit as st

st.set_page_config(
    page_title="CLE Engine Admin",
    page_icon="📚",
    layout="wide",
)

st.title("CLE Engine Admin Dashboard")

st.markdown("""
Welcome to the CLE Engine Admin Dashboard!

This dashboard provides an interface to manage:
- User vocabulary feeds
- Learning progress tracking
- System analytics
- Configuration management
""")

st.info("Dashboard is under development. More features coming soon!")

# Example metrics
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Active Users", "0", "0%")
with col2:
    st.metric("Words Learned", "0", "0%")
with col3:
    st.metric("API Health", "✓", "Operational")
