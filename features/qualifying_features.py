"""Qualifying features."""

import numpy as np
import pandas as pd
from data.db import query_df

def compute_qualifying_features(
    driver_id: str,
    qualifying: pd.DataFrame,
    race_id: str = None
) -> dict:
    """Compute qualifying and FP2 pace features, including penalty flags."""
    features = {}

    driver_quali = qualifying[qualifying["driver_id"] == driver_id]
    
    # Check actual starting grid from results table if available
    actual_grid = None
    if race_id:
        res = query_df("SELECT grid FROM results WHERE race_id = ? AND driver_id = ?", (race_id, driver_id))
        if not res.empty:
            actual_grid = res.iloc[0]["grid"]

    if not driver_quali.empty:
        q = driver_quali.iloc[0]
        q_pos = q["position"]
        
        # Use actual grid if we have it, else fallback to quali position
        features["grid_position"] = actual_grid if actual_grid is not None and actual_grid > 0 else q_pos
        
        # Penalty flag: if actual starting grid is significantly worse than qualifying position
        # (e.g. 3 or more spots, typical for engine/gearbox or impeding penalties)
        if actual_grid is not None and actual_grid >= q_pos + 3:
            features["is_penalty_grid"] = 1
        else:
            features["is_penalty_grid"] = 0

        # Gap to pole
        pole_time = qualifying["q3_sec"].min()
        driver_q3 = q["q3_sec"]
        if pd.notna(driver_q3) and pd.notna(pole_time) and pole_time > 0:
            features["quali_gap_to_pole"] = driver_q3 - pole_time
        else:
            features["quali_gap_to_pole"] = np.nan

        features["quali_q3_reached"] = 1 if pd.notna(q["q3_sec"]) else 0

        # Sector consistency (approx from Q1/Q2/Q3 times)
        q_times = [q[c] for c in ["q1_sec", "q2_sec", "q3_sec"] if pd.notna(q[c])]
        features["quali_consistency"] = np.std(q_times) if len(q_times) >= 2 else np.nan
        
        # New features placeholders
        features["sector_1_delta"] = np.nan
        features["sector_2_delta"] = np.nan
        features["sector_3_delta"] = np.nan
        features["quali_compound"] = "Unknown"
        features["fp2_pace_rank"] = np.nan
        features["fp2_deg_rate"] = np.nan
        features["fp2_run_representative"] = 0
    else:
        features["grid_position"] = actual_grid if actual_grid is not None and actual_grid > 0 else 20
        features["is_penalty_grid"] = 0
        features["quali_gap_to_pole"] = np.nan
        features["quali_q3_reached"] = 0
        features["quali_consistency"] = np.nan
        features["sector_1_delta"] = np.nan
        features["sector_2_delta"] = np.nan
        features["sector_3_delta"] = np.nan
        features["quali_compound"] = "Unknown"
        features["fp2_pace_rank"] = np.nan
        features["fp2_deg_rate"] = np.nan
        features["fp2_run_representative"] = 0

    return features
