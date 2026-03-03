"""F1 Championship Standings View."""

import streamlit as st
from data.db import query_df
from utils.theme import apply_global_theme

apply_global_theme()
st.markdown('<h1 class="main-header">🏆 Championship Standings</h1>', unsafe_allow_html=True)
st.markdown("Current driver and constructor points.")
st.divider()

year = st.selectbox("Season", [2025, 2024, 2023])
tab1, tab2 = st.tabs(["Drivers", "Constructors"])

with tab1:
    query_drv = (
        "SELECT drv.full_name as Driver, drv.code as Code, SUM(res.points) as Points "
        "FROM results res "
        "JOIN races r ON res.race_id = r.race_id "
        "JOIN drivers drv ON res.driver_id = drv.driver_id "
        "WHERE r.year = ? "
        "GROUP BY drv.driver_id "
        "ORDER BY Points DESC"
    )
    df_driver = query_df(query_drv, (year,))
    if not df_driver.empty:
        st.dataframe(df_driver, hide_index=True, use_container_width=True)
    else:
        st.info("No driver points found for this season.")

with tab2:
    query_ctor = (
        "SELECT c.name as Constructor, SUM(res.points) as Points "
        "FROM results res "
        "JOIN races r ON res.race_id = r.race_id "
        "JOIN constructors c ON res.constructor_id = c.constructor_id "
        "WHERE r.year = ? "
        "GROUP BY c.constructor_id "
        "ORDER BY Points DESC"
    )
    df_ctor = query_df(query_ctor, (year,))
    if not df_ctor.empty:
        st.dataframe(df_ctor, hide_index=True, use_container_width=True)
    else:
        st.info("No constructor points found for this season.")
