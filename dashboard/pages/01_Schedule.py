"""F1 Schedule View."""

import streamlit as st
import pandas as pd
import requests
from data.db import query_df
from utils.theme import apply_global_theme

apply_global_theme()
st.markdown('<h1 class="main-header">📅 Schedule</h1>', unsafe_allow_html=True)
st.markdown("Upcoming and past races for the selected season.")
st.divider()

year = st.selectbox("Select Season", [2026, 2025, 2024], index=0)

df_races = query_df("SELECT round, circuit_name, country, race_date FROM races WHERE year = ? ORDER BY round", (year,))

if df_races.empty:
    st.info(f"No schedule data found for {year}.")
else:
    df_races.columns = ["Round", "Circuit", "Country", "Date"]
    st.dataframe(df_races, hide_index=True, use_container_width=True)
