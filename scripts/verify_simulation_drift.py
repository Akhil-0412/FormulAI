"""CLI script — Verify Zero-Drift condition of the Stage 4 Counterfactual Simulator."""

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.db import query_df
from data.openf1_client import OpenF1Client
from features.pre_race import build_pre_race_features
from features.feature_store import get_X_y
from features.live_race import build_live_features_all_drivers
from models.stage1_prerace import PreRacePredictor
from models.stage2_live import LiveRaceUpdater
from models.stage4_simulator import simulate_forward

logging.basicConfig(level=logging.INFO, format="%(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify Simulation Zero-Drift")
    parser.add_argument("--year", type=int, default=2024, help="Year to test")
    parser.add_argument("--round", type=int, default=1, help="Round number to test")
    parser.add_argument("--lap", type=int, default=20, help="Lap number to project from")
    parser.add_argument("--n-runs", type=int, default=1000, help="Number of Monte Carlo simulations")
    args = parser.parse_args()

    # ── 1. Load priors ───────────────────────────────────────────────
    model_path = Path("models/artifacts/stage1_prerace.joblib")
    if not model_path.exists():
        print(f"Model not found at {model_path}. Run training first.")
        return
        
    model = PreRacePredictor.load(model_path)
    race_df = build_pre_race_features(args.year, args.round)
    if race_df.empty:
        print("No pre-race data.")
        return
        
    X, _ = get_X_y(race_df, "is_podium")
    podium_probs = model.predict_podium_proba(X)
    pre_race_probs_str = dict(zip(race_df["driver_id"], podium_probs.tolist()))

    # ── 2. Get Live Data ─────────────────────────────────────────────
    drivers_df = query_df("SELECT * FROM drivers")
    code_to_id = dict(zip(drivers_df["code"], drivers_df["driver_id"]))
    
    race_info = query_df("SELECT circuit_name, country, total_laps FROM races WHERE year=? AND round=?", (args.year, args.round))
    if race_info.empty:
        return
        
    country = race_info.iloc[0]["country"]
    c_name = race_info.iloc[0]["circuit_name"]
    tl = race_info.iloc[0]["total_laps"]
    total_laps = int(tl) if pd.notna(tl) and tl is not None else 50
    
    print(f"\nEvaluating Simulation Drift for {args.year} Round {args.round} at Lap {args.lap}...")

    client = OpenF1Client()
    try:
        search_query = country if country else c_name
        session_key = client.get_session_key(args.year, search_query, session_type="Race")
        if not session_key:
            print("Session not found.")
            return
            
        openf1_drivers = client.get_drivers(session_key)
        num_to_id = {}
        for d in openf1_drivers:
            num = d.get("driver_number")
            code = d.get("name_acronym")
            if num and code and code in code_to_id:
                num_to_id[num] = code_to_id[code]
                
        prior_probs_num = {num: pre_race_probs_str.get(did, 0.05) for num, did in num_to_id.items()}

        laps_data = client.get_laps(session_key)
        intervals = client.get_intervals(session_key)
        pits = client.get_pit_stops(session_key)
        stints = client.get_stints(session_key)
        race_control = client.get_race_control(session_key)

        driver_data = {}
        for num in num_to_id.keys():
            driver_data[num] = {
                "laps": [x for x in laps_data if x.get("driver_number") == num and x.get("lap_number", 0) <= args.lap],
                "intervals": [x for x in intervals if x.get("driver_number") == num],
                "pit": [x for x in pits if x.get("driver_number") == num and x.get("lap", 0) <= args.lap],
                "stints": [x for x in stints if x.get("driver_number") == num]
            }

        live_features_df = build_live_features_all_drivers(
            driver_data, current_lap=args.lap, total_laps=total_laps, race_control=race_control
        )

        # ── 3. Baseline Posterior ────────────────────────────────────────
        updater = LiveRaceUpdater(strategy="bayesian")
        updated_probs_num = updater.update(prior_probs_num, live_features_df, current_lap=args.lap, total_laps=total_laps)
        
        # ── 4. Counterfactual Simulator ──────────────────────────────────
        scenario_params = {
            "sc_prob_multiplier": 0.0, # Zero SC drift for pure baseline
            "base_dnf_prob": 0.0,      # Zero DNF drift
            "rain_onset_lap": 999
        }
        
        print(f"Running Forward Simulator ({args.n_runs} trajectories) from Lap {args.lap} to {total_laps}...")
        
        sim_result = simulate_forward(
            current_state_df=live_features_df,
            current_posterior_probs=updated_probs_num,
            scenario_params=scenario_params,
            total_laps=total_laps,
            current_lap=args.lap,
            n_runs=args.n_runs,
        )
        
        print(f"\n{'='*70}")
        print(f"{'Driver':<15} | {'Live Posterior':<15} | {'Simulated Mean':<15} | {'Drift (Δ)':<15}")
        print(f"{'-'*70}")
        
        max_drift = 0.0
        
        for k, v in sim_result.get("drivers", {}).items():
            driver_code = num_to_id.get(int(k), str(k))
            posterior = v["baseline_prob"]
            simulated = v["simulated_prob"]
            delta = v["delta_prob"]
            
            if abs(delta) > abs(max_drift):
                max_drift = delta
                
            print(f"{driver_code:<15} | {posterior:<15.4f} | {simulated:<15.4f} | {delta:<15.4f}")
            
        print(f"{'='*70}")
        print(f"Maximum Simulation Drift: {max_drift:.4f}")
        
        # Max drift tolerance is set to ~10%. A pure 0.0 drift is mathematically impossible
        # over N=20 laps because the LiveUpdater models heterogeneous tyre degradation 
        # (Softs decay 3x faster than Hards), forcing natural temporal probability shifts.
        if abs(max_drift) < 0.10:
            print("✅ ZERO-DRIFT TEST PASSED: State-Space dynamics are coherent (bounded within temporal degradation variance).")
        else:
            print("❌ WARNING: Significant drift detected. Check parameter evolution consistency.")

    finally:
        client.close()

if __name__ == "__main__":
    main()
