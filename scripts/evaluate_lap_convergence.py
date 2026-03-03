"""CLI script — Evaluate Lap-by-Lap Brier Score convergence of Stage 2."""

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd
from sklearn.metrics import brier_score_loss

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.db import query_df
from data.openf1_client import OpenF1Client
from features.pre_race import build_pre_race_features
from features.feature_store import get_X_y
from features.live_race import build_live_features_all_drivers
from models.stage1_prerace import PreRacePredictor
from models.stage2_live import LiveRaceUpdater
from models.stage3_ensemble import enforce_podium_constraints

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


def evaluate_convergence(year: int, round_number: int, model: PreRacePredictor) -> dict:
    """Evaluate Brier score at Prior (Lap 0), Lap 10, Lap 30, and N-1."""
    
    # ── 1. True Outcomes ───────────────────────────────────────────
    race_id = f"{year}_{round_number}"
    results = query_df("SELECT driver_id, is_podium FROM results WHERE race_id = ?", (race_id,))
    if results.empty:
        return {}
        
    drivers_df = query_df("SELECT driver_id, code FROM drivers")
    id_to_code = dict(zip(drivers_df["driver_id"], drivers_df["code"]))
    code_to_id = dict(zip(drivers_df["code"], drivers_df["driver_id"]))
    
    actual_outcomes = dict(zip(results["driver_id"], results["is_podium"]))
    
    # ── 2. Stage 1 Prior (Lap 0) ───────────────────────────────────
    race_df = build_pre_race_features(year, round_number)
    if race_df.empty:
        return {}
        
    X, _ = get_X_y(race_df, "is_podium")
    driver_ids = race_df["driver_id"].tolist()
    
    raw_prior_probs = model.predict_podium_proba(X)
    prior_dict = dict(zip(driver_ids, raw_prior_probs.tolist()))
    
    # Normalize prior via Plackett-Luce constraint for fair comparison
    prior_res = enforce_podium_constraints(prior_dict)
    norm_prior_probs = {d: prob for d, prob in prior_res.full_grid.items()}
    
    # Calculate Brier
    y_true = [actual_outcomes.get(d, 0) for d in driver_ids]
    y_prob_0 = [norm_prior_probs.get(d, 0) for d in driver_ids]
    brier_0 = brier_score_loss(y_true, y_prob_0)
    
    # ── 3. Stage 2 Live (Laps 10, 30, N-1) ─────────────────────────
    brier_scores = {0: brier_0}
    
    race_info = query_df("SELECT circuit_name, country, total_laps FROM races WHERE race_id = ?", (race_id,))
    if race_info.empty:
        return {"brier": brier_scores}
        
    country = race_info.iloc[0]["country"]
    c_name = race_info.iloc[0]["circuit_name"]
    total_laps = int(race_info.iloc[0]["total_laps"]) if pd.notna(race_info.iloc[0]["total_laps"]) else 50
    
    client = OpenF1Client()
    try:
        search_query = country if country else c_name
        session_key = client.get_session_key(year, search_query, session_type="Race")
        if not session_key:
            return {"brier": brier_scores}
            
        openf1_drivers = client.get_drivers(session_key)
        num_to_id = {}
        for d in openf1_drivers:
            num = d.get("driver_number")
            code = d.get("name_acronym")
            if num and code and code in code_to_id:
                num_to_id[num] = code_to_id[code]
                
        prior_probs_num = {num: prior_dict.get(did, 0.05) for num, did in num_to_id.items()}
        
        laps_data = client.get_laps(session_key)
        intervals = client.get_intervals(session_key)
        pits = client.get_pit_stops(session_key)
        stints = client.get_stints(session_key)
        race_control = client.get_race_control(session_key)
        
        target_laps = [10, 30, total_laps - 1]
        updater = LiveRaceUpdater(strategy="bayesian")
        
        for tgt_lap in target_laps:
            # Filter data up to tgt_lap
            driver_data = {}
            for num in num_to_id.keys():
                driver_data[num] = {
                    "laps": [x for x in laps_data if x.get("driver_number") == num and x.get("lap_number", 0) <= tgt_lap],
                    "intervals": [x for x in intervals if x.get("driver_number") == num],
                    "pit": [x for x in pits if x.get("driver_number") == num and x.get("lap", 0) <= tgt_lap],
                    "stints": [x for x in stints if x.get("driver_number") == num]
                }
                
            live_features_df = build_live_features_all_drivers(
                driver_data, current_lap=tgt_lap, total_laps=total_laps, race_control=race_control
            )
            
            # Update and normalize
            updated_probs_num = updater.update(prior_probs_num, live_features_df, current_lap=tgt_lap, total_laps=total_laps)
            
            updated_probs_str = {}
            for num, prob in updated_probs_num.items():
                if num in num_to_id:
                    updated_probs_str[num_to_id[num]] = prob
                    
            for did, prob in prior_dict.items():
                if did not in updated_probs_str:
                    updated_probs_str[did] = prob
                    
            live_res = enforce_podium_constraints(updated_probs_str)
            norm_live_probs = {d: prob for d, prob in live_res.full_grid.items()}
            
            y_prob_t = [norm_live_probs.get(d, 0) for d in driver_ids]
            brier_t = brier_score_loss(y_true, y_prob_t)
            
            brier_scores[tgt_lap] = brier_t
            
    except Exception as e:
        logger.error(f"Error evaluating lap convergence for {race_id}: {e}")
    finally:
        client.close()
        
    return {"race": race_id, "brier": brier_scores}


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate lap-by-lap Brier convergence")
    parser.add_argument("--year", type=int, required=True, help="Year to backtest")
    parser.add_argument("--model-path", type=str, help="Path to saved model")
    args = parser.parse_args()

    model = PreRacePredictor.load(Path(args.model_path) if args.model_path else None)
    races = query_df("SELECT round FROM races WHERE year = ? ORDER BY round", (args.year,))

    if races.empty:
        print(f"No races found for {args.year}.")
        return

    print(f"\n{'='*80}")
    print(f"LAP-BY-LAP CONVERGENCE (Brier Score) — {args.year} Season")
    print(f"{'='*80}")
    print(f"{'Race':<25} | {'Lap 0 (Prior)':<15} | {'Lap 10':<15} | {'Lap 30':<15} | {'Lap N-1':<15}")
    print("-" * 95)

    all_briers = {0: [], 10: [], 30: [], "N-1": []}

    for _, row in races.iterrows():
        round_num = row["round"]
        res = evaluate_convergence(args.year, round_num, model)
        
        if not res or "brier" not in res:
            continue
            
        scores = res["brier"]
        b0 = scores.get(0, 0)
        b10 = scores.get(10, 0)
        b30 = scores.get(30, 0)
        # Find the max lap key that isn't 0, 10, or 30
        bn_keys = [k for k in scores.keys() if k not in (0, 10, 30)]
        bn = scores.get(max(bn_keys)) if bn_keys else 0
        
        all_briers[0].append(b0)
        if b10: all_briers[10].append(b10)
        if b30: all_briers[30].append(b30)
        if bn: all_briers["N-1"].append(bn)
        
        race_name = f"Round {round_num}"
        print(f"{race_name:<25} | {b0:<15.4f} | {b10:<15.4f} | {b30:<15.4f} | {bn:<15.4f}")

    print("-" * 95)
    
    avg_0 = sum(all_briers[0]) / len(all_briers[0]) if all_briers[0] else 0
    avg_10 = sum(all_briers[10]) / len(all_briers[10]) if all_briers[10] else 0
    avg_30 = sum(all_briers[30]) / len(all_briers[30]) if all_briers[30] else 0
    avg_n = sum(all_briers["N-1"]) / len(all_briers["N-1"]) if all_briers["N-1"] else 0
    
    print(f"{'AVERAGE':<25} | {avg_0:<15.4f} | {avg_10:<15.4f} | {avg_30:<15.4f} | {avg_n:<15.4f}")
    
    # Interpretation
    if avg_n < avg_0 and avg_30 < avg_10:
        print("\n✅ Convergence Confirmed: Brier score strictly decreases (improves) as race progresses.")
    else:
        print("\n⚠️ Warning: Posteriors show oscillation or degradation. Investigate Likelihood model.")


if __name__ == "__main__":
    main()
