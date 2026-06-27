import streamlit as st
from utils.theme import apply_global_theme

apply_global_theme()

st.markdown('<h1 class="main-header">🛞 Tyre Strategy & Degradation</h1>', unsafe_allow_html=True)
st.markdown("Analyze expected tyre degradation curves and optimal pit windows.")
st.divider()

col1, col2 = st.columns(2)

with col1:
    st.subheader("Tyre Degradation Curves")
    st.info("Select a circuit and compounds to generate degradation curves from the Bayesian model.")
    st.line_chart({"Soft": [1.0, 1.2, 1.5, 2.0], "Medium": [1.0, 1.1, 1.3, 1.6], "Hard": [1.0, 1.05, 1.15, 1.3]})

with col2:
    st.subheader("Optimal Pit Windows")
    st.info("Estimated pit windows based on historical drop-offs and track evolution.")
    st.dataframe({"Strategy": ["S-M", "M-H", "S-H-S"], "Window 1": ["L14-20", "L22-28", "L10-15"], "Window 2": ["--", "--", "L35-42"]}, hide_index=True, width='stretch')
