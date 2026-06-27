import streamlit as st
import requests
from utils.theme import apply_global_theme

apply_global_theme()

st.markdown('<h1 class="main-header">🏎️ Live Race Tracker</h1>', unsafe_allow_html=True)
st.markdown("Monitor real-time telemetry, lap embeddings from LapGRU, and dynamically shifting podium probabilities.")
st.divider()

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("Live Standings & Predictions")
    st.info("The Live Tracker is currently waiting for a live session to begin. LapGRU embeddings will populate here.")
    st.dataframe({"Driver": ["VER", "NOR", "LEC"], "Lap": [0, 0, 0], "P(Podium)": ["--", "--", "--"]}, hide_index=True, width='stretch')

with col2:
    st.subheader("Session Status")
    try:
        response = requests.get("http://127.0.0.1:8000/live/status")
        if response.status_code == 200:
            st.json(response.json())
        else:
            st.error("Live API unavailable.")
    except:
        st.error("Could not connect to backend API.")

st.divider()
st.markdown("### Telemetry Stream")
st.line_chart({"Pace Delta": []})
