"""F1 Historical Results View."""

import streamlit as st
from data.db import query_df
from utils.theme import apply_global_theme

apply_global_theme()
st.markdown('<h1 class="main-header">🏁 Race Results</h1>', unsafe_allow_html=True)
st.markdown("Explore historical race data and outcomes.")
st.divider()

col1, col2 = st.columns(2)
with col1:
    year = st.selectbox("Season", [2025, 2024, 2023])
with col2:
    round_no = st.number_input("Round", min_value=1, max_value=24, step=1)

query = (
    "SELECT res.position_text, drv.full_name as Driver, res.points, res.status "
    "FROM results res "
    "JOIN races r ON res.race_id = r.race_id "
    "JOIN drivers drv ON res.driver_id = drv.driver_id "
    "WHERE r.year = ? AND r.round = ? "
    "ORDER BY CASE WHEN res.position IS NULL THEN 999 ELSE res.position END ASC"
)

df_results = query_df(query, (year, round_no))

if df_results.empty:
    st.info("No results found for this race yet.")
else:
    df_results.columns = ["Pos", "Driver", "Points", "Status"]
    st.dataframe(df_results, hide_index=True, use_container_width=True)
