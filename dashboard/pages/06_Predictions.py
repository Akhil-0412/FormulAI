"""Streamlit Dashboard — F1 Podium Predictor live race view."""

from __future__ import annotations

import requests
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

from utils.theme import apply_global_theme

# ── Config ──────────────────────────────────────────────────────────────

API_BASE = "http://localhost:8000"

# Apply global theme
apply_global_theme()

# ── Header ──────────────────────────────────────────────────────────────

st.markdown('<h1 class="main-header">🏎️ F1 Podium Predictor</h1>', unsafe_allow_html=True)

# ── Sidebar ─────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("Navigation")
    app_mode = st.radio(
        "Select View",
        ["🔮 Live Predictor", "📈 Rolling Backtest", "🏆 Race Center"]
    )
    
if app_mode == "🔮 Live Predictor":
    with st.sidebar:
        st.divider()
        st.header("🏁 Race Selector")
        year = st.selectbox("Season", list(range(2025, 2017, -1)), index=0)
        round_number = st.number_input("Round", min_value=1, max_value=24, value=1)
        predict_btn = st.button("🔮 Predict Podium", type="primary", use_container_width=True)
        mc_btn = st.button("🎲 Monte Carlo Simulation", use_container_width=True)

        st.divider()
        st.header("📊 API Status")
        try:
            health = requests.get(f"{API_BASE}/health", timeout=3).json()
            st.success(f"API: {health['status']}")
            st.info(f"Model loaded: {'✅' if health['model_loaded'] else '❌'}")
            st.info(f"DB connected: {'✅' if health['db_connected'] else '❌'}")
        except Exception:
            st.error("API not reachable")

    # ── Main content ────────────────────────────────────────────────────────

    if predict_btn:
        with st.spinner("Generating prediction..."):
            try:
                resp = requests.get(
                    f"{API_BASE}/api/v1/predict/{year}/{round_number}",
                    timeout=30,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    race = data["race"]

                    st.subheader(f"🏁 {race.get('circuit_name', f'R{round_number}')} "
                                 f"— {race.get('country', year)}")

                    # Confidence badge
                    conf = data["confidence_level"]
                    conf_class = f"confidence-{conf}"
                    st.markdown(f'<p class="{conf_class}">Confidence: {conf.upper()}</p>',
                                unsafe_allow_html=True)

                    # ── Podium cards ────────────────────────────────────
                    cols = st.columns(3)
                    medals = ["🥇", "🥈", "🥉"]
                    for i, pred in enumerate(data["predictions"][:3]):
                        with cols[i]:
                            st.markdown(f"""
                            <div class="podium-card">
                                <h2>{medals[i]}</h2>
                                <h3>P{pred['predicted_position']}</h3>
                                <h4>{pred['driver_id'].replace('_', ' ').title()}</h4>
                                <p>Probability: {pred['probability']:.1%}</p>
                            </div>
                            """, unsafe_allow_html=True)

                    # ── Full grid probability chart ─────────────────────
                    st.subheader("📊 Full Grid Probabilities")
                    grid_df = pd.DataFrame(data["full_grid"])
                    grid_df["driver_label"] = grid_df["driver_id"].apply(
                        lambda x: x.replace("_", " ").title()
                    )
                    grid_df = grid_df.sort_values("podium_probability", ascending=True)

                    fig = go.Figure(go.Bar(
                        x=grid_df["podium_probability"],
                        y=grid_df["driver_label"],
                        orientation="h",
                        marker_color=[
                            "#e10600" if p > 0.5 else "#ff6b35" if p > 0.2 else "#555"
                            for p in grid_df["podium_probability"]
                        ],
                        text=[f"{p:.1%}" for p in grid_df["podium_probability"]],
                        textposition="outside",
                    ))
                    fig.update_layout(
                        xaxis_title="P(Podium)",
                        yaxis_title="",
                        height=500,
                        template="plotly_dark",
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        margin=dict(l=150),
                    )
                    st.plotly_chart(fig, use_container_width=True)

                else:
                    st.error(f"Prediction failed: {resp.json().get('detail', resp.status_code)}")
            except requests.ConnectionError:
                st.error("Cannot connect to API. Make sure the server is running.")

    if mc_btn:
        with st.spinner("Running Monte Carlo simulation (10,000 samples)..."):
            try:
                resp = requests.get(
                    f"{API_BASE}/api/v1/predict/{year}/{round_number}/monte-carlo",
                    timeout=60,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    race = data["race"]

                    st.subheader(f"🎲 Monte Carlo — {race.get('circuit_name', f'R{round_number}')}")
                    st.info(f"Most likely combo: {', '.join(data['most_likely_combo'])} "
                            f"({data['most_likely_combo_probability']:.1%})")

                    # Top drivers table
                    mc_df = pd.DataFrame(data["results"][:10])
                    mc_df["driver_label"] = mc_df["driver_id"].apply(
                        lambda x: x.replace("_", " ").title()
                    )
                    mc_df = mc_df[["driver_label", "podium_probability",
                                   "p1_probability", "p2_probability", "p3_probability"]]
                    mc_df.columns = ["Driver", "P(Podium)", "P(P1)", "P(P2)", "P(P3)"]

                    # Format as percentages
                    for col in mc_df.columns[1:]:
                        mc_df[col] = mc_df[col].apply(lambda x: f"{x:.1%}")

                    st.dataframe(mc_df, use_container_width=True, hide_index=True)

                    # Stacked bar chart of position probabilities
                    chart_df = pd.DataFrame(data["results"][:10])
                    chart_df["driver_label"] = chart_df["driver_id"].apply(
                        lambda x: x.replace("_", " ").title()
                    )

                    fig = go.Figure()
                    for pos, color, label in [
                        ("p1_probability", "#ffd700", "P1"),
                        ("p2_probability", "#c0c0c0", "P2"),
                        ("p3_probability", "#cd7f32", "P3"),
                    ]:
                        fig.add_trace(go.Bar(
                            name=label,
                            x=chart_df["driver_label"],
                            y=chart_df[pos],
                            marker_color=color,
                        ))

                    fig.update_layout(
                        barmode="stack",
                        yaxis_title="Probability",
                        height=400,
                        template="plotly_dark",
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        legend=dict(orientation="h", yanchor="bottom", y=1.02),
                    )
                    st.plotly_chart(fig, use_container_width=True)

                else:
                    st.error(f"Monte Carlo failed: {resp.json().get('detail', resp.status_code)}")
            except requests.ConnectionError:
                st.error("Cannot connect to API.")

elif app_mode == "📈 Rolling Backtest":
    import json
    from pathlib import Path
    
    st.markdown('<h2 style="text-align: center;">📈 Rolling Window Backtest (Online Learning)</h2>', unsafe_allow_html=True)
    st.markdown("This view shows the model's performance as it conceptually retrains itself **race-by-race** through a season.")
    
    with st.sidebar:
        st.divider()
        st.header("⚙️ Backtest Settings")
        bt_year = st.selectbox("Season", [2024, 2025], index=0)
        
    data_path = Path(__file__).resolve().parent.parent / "data" / f"rolling_backtest_{bt_year}.json"
    
    if not data_path.exists():
        st.warning(f"No backtest data found for {bt_year}. Run `python scripts/rolling_backtest.py --test-year {bt_year}` first.")
    else:
        with open(data_path, "r") as f:
            bt_results = json.load(f)
            
        if not bt_results:
            st.info("No results to display.")
        else:
            # Metrics Row
            total_races = len(bt_results)
            exact_3 = sum(1 for r in bt_results if r["correct"] == 3)
            exact_0 = sum(1 for r in bt_results if r["correct"] == 0)
            
            # Create a dataframe for visualization
            df = pd.DataFrame(bt_results)
            df['accuracy_pct'] = df['correct'] / 3.0
            df['cumulative_accuracy'] = df['accuracy_pct'].expanding().mean()
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Races Evaluated", f"{total_races}")
            c2.metric("Perfect Podiums (All 3)", f"{exact_3} ({exact_3/total_races:.1%})")
            c3.metric("At Least 1 Correct", f"{total_races - exact_0} ({(total_races - exact_0)/total_races:.1%})")
            c4.metric("Avg Exact Position Rate", f"{df['accuracy_pct'].mean():.1%}")

            st.divider()
            
            # Cumulative Accuracy Chart
            st.subheader("Model Learning Over Time (Cumulative Podiums Matched)")
            fig2 = px.line(df, x="race_name", y="cumulative_accuracy", 
                           title=f"Cumulative Match Rate Over {bt_year} Season",
                           labels={"race_name": "Race", "cumulative_accuracy": "Cumulative Correct Podiums / 3"},
                           template="plotly_dark",
                           color_discrete_sequence=["#e10600"])
            fig2.update_layout(yaxis=dict(tickformat=".0%"))
            st.plotly_chart(fig2, use_container_width=True)
            
            # Race by Race Table
            st.subheader("Race-by-Race Details")
            display_df = df.copy()
            display_df["Predicted"] = display_df["predicted"].apply(lambda x: ", ".join(x))
            display_df["Actual"] = display_df["actual"].apply(lambda x: ", ".join(x))
            display_df["Match"] = display_df["correct"].apply(
                lambda c: "✅✅✅" if c == 3 else "✅✅" if c == 2 else "✅" if c == 1 else "❌"
            )
            display_cols = ["round", "race_name", "Predicted", "Actual", "Match"]
            st.dataframe(display_df[display_cols], use_container_width=True, hide_index=True)

elif app_mode == "🏆 Race Center":
    st.markdown('<h2 style="text-align: center;">🏆 Race Center (2024-2026)</h2>', unsafe_allow_html=True)
    st.markdown("A unified view showing circuit details, starting grids, and predictions vs actual results.")
    
    with st.sidebar:
        st.divider()
        st.header("🏁 Race Selector")
        rc_year = st.selectbox("Season", [2026, 2025, 2024], index=0)
        rc_round = st.number_input("Round", min_value=1, max_value=24, value=1)
        load_btn = st.button("Load Race Data", type="primary", use_container_width=True)
        
    if load_btn:
        with st.spinner(f"Loading data for {rc_year} Round {rc_round}..."):
            try:
                resp = requests.get(f"{API_BASE}/api/v1/race_center/{rc_year}/{rc_round}", timeout=30)
                if resp.status_code == 200:
                    data = resp.json()
                    race = data["race"]
                    grid = data["grid"]
                    preds = data["predictions"]
                    actual = data["actual_podium"]
                    metrics = data["metrics"]
                    
                    # ── Header ──
                    st.divider()
                    st.subheader(f"🏁 {race.get('circuit_name', f'R{rc_round}')} — {race.get('country', rc_year)}")
                    st.caption(f"Date: {race.get('race_date', 'TBD')} | Season: {rc_year} | Round: {rc_round}")
                    
                    # ── Layout ──
                    col1, col2 = st.columns([1, 1.5])
                    
                    with col1:
                        st.markdown("### 🚦 Starting Grid")
                        if not grid:
                            st.info("Starting grid not yet available (qualifying pending).")
                        else:
                            grid_df = pd.DataFrame(grid)
                            grid_df = grid_df.dropna(subset=['position']).sort_values('position')
                            if not grid_df.empty:
                                grid_df["Driver"] = grid_df["driver_id"].apply(lambda x: x.replace("_", " ").title())
                                st.dataframe(grid_df[["position", "Driver"]].set_index("position"), use_container_width=True)
                            else:
                                st.info("Starting grid not yet available.")
                                
                    with col2:
                        st.markdown("### 🔮 Predicted Podium")
                        if not preds:
                            st.warning("Prediction models not ready or no data available for this race.")
                        else:
                            p_cols = st.columns(3)
                            medals = ["🥇 P1", "🥈 P2", "🥉 P3"]
                            for i, pred in enumerate(preds[:3]):
                                with p_cols[i]:
                                    st.markdown(f"""
                                    <div class="metric-card" style="border-top: 3px solid #e10600;">
                                        <h4>{medals[i]}</h4>
                                        <h3>{pred['driver_id'].replace('_', ' ').title()}</h3>
                                        <p style="color: #888; margin-bottom: 0;">Prob: {pred['probability']:.1%}</p>
                                    </div>
                                    """, unsafe_allow_html=True)
                                    
                        st.markdown("<br>", unsafe_allow_html=True)
                        st.markdown("### 🏆 Actual Podium")
                        if not metrics["is_completed"]:
                            st.info("Race has not occurred yet or results are pending.")
                        else:
                            a_cols = st.columns(3)
                            for i, drv in enumerate(actual[:3]):
                                is_match = any(p['driver_id'] == drv and p['predicted_position'] == i+1 for p in preds)
                                is_on_podium = any(p['driver_id'] == drv for p in preds)
                                
                                color = "#00ff88" if is_match else "#ffaa00" if is_on_podium else "#555"
                                indicator = "🎯 Exact" if is_match else "✅ Podium" if is_on_podium else "❌ Miss"
                                
                                with a_cols[i]:
                                    st.markdown(f"""
                                    <div class="metric-card" style="border-top: 3px solid {color};">
                                        <h4>{medals[i]}</h4>
                                        <h3>{drv.replace('_', ' ').title()}</h3>
                                        <p style="color: {color}; font-weight: bold; margin-bottom: 0;">{indicator}</p>
                                    </div>
                                    """, unsafe_allow_html=True)
                                    
                    # ── Metrics Footer ──
                    st.divider()
                    if metrics["is_completed"]:
                        correct = metrics["correct_podiums"]
                        st.markdown("### 📊 Evaluation")
                        emoji = "🤯" if correct == 3 else "🔥" if correct == 2 else "👍" if correct == 1 else "📉"
                        st.success(f"**Model Matched {correct} out of 3 Drivers** on the final podium! {emoji}")
                    else:
                        st.info("Awaiting race conclusion to evaluate model accuracy.")

                else:
                    st.error(f"Failed to fetch data: {resp.status_code}")
            except requests.ConnectionError:
                st.error("Cannot connect to API. Is the server running?")


# ── Footer ──────────────────────────────────────────────────────────────

st.divider()
st.caption("F1 Podium Predictor v0.1.0 — Data from FastF1 + Jolpica + OpenF1 + Open-Meteo")
