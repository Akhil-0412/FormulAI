"""Form features — Recent performance, circuit history, and teammate comparisons."""

import pandas as pd
import numpy as np
from data.db import query_df


def compute_form_features(driver_id: str, circuit_id: str, race_id: str, constructor_id: str = None) -> dict:
    """Compute recent form features for driver, including rolling positions gained and teammate deltas."""
    features = {}

    # 1. Standard Form (Last 5 races)
    recent = query_df(
        """SELECT position, is_podium, status, grid, points FROM results
           WHERE driver_id = ? AND race_id < ? AND position IS NOT NULL
           ORDER BY race_id DESC LIMIT 5""",
        (driver_id, race_id),
    )
    if not recent.empty:
        features["driver_last3_avg_pos"] = recent.head(3)["position"].mean()
        features["last3_podium_rate"] = recent.head(3)["is_podium"].mean()

        # Positions Gained Rolling (actual race data)
        completed = recent[recent["status"].isin(["Finished"]) | recent["status"].str.startswith("+")]
        if not completed.empty and completed["grid"].notna().any():
            gained = completed["grid"] - completed["position"]  # Positive = gained
            features["driver_positions_gained_rolling"] = gained.mean()
        else:
            features["driver_positions_gained_rolling"] = 0.0

        # Actual overtake rate proxy: avg positions gained per race (only races where they gained)
        if not completed.empty:
            deltas = completed["grid"] - completed["position"]
            features["overtake_rate"] = float(deltas.clip(lower=0).mean())
        else:
            features["overtake_rate"] = 0.0
    else:
        features["driver_last3_avg_pos"] = 15.0
        features["last3_podium_rate"] = 0.0
        features["driver_positions_gained_rolling"] = 0.0
        features["overtake_rate"] = 0.0

    # 2. Circuit History
    circuit_hist = query_df(
        """SELECT position, is_podium FROM results
           JOIN races ON results.race_id = races.race_id
           WHERE results.driver_id = ? AND races.circuit_id = ?
             AND results.race_id < ? AND results.position IS NOT NULL""",
        (driver_id, circuit_id, race_id),
    )
    if not circuit_hist.empty:
        features["circuit_history_podium_rate"] = circuit_hist["is_podium"].mean()
        features["circuit_history_avg_pos"] = circuit_hist["position"].mean()
        features["circuit_history_best_pos"] = circuit_hist["position"].min()
        features["circuit_history_n_races"] = len(circuit_hist)
    else:
        features["circuit_history_podium_rate"] = 0.0
        features["circuit_history_avg_pos"] = 15.0
        features["circuit_history_best_pos"] = 20
        features["circuit_history_n_races"] = 0

    # 3. Wet Race Performance (from actual wet races in DB)
    wet_results = query_df(
        """SELECT res.position FROM results res
           JOIN weather w ON res.race_id = w.race_id
           WHERE res.driver_id = ? AND res.race_id < ?
             AND w.precipitation_prob > 0.5 AND res.position IS NOT NULL""",
        (driver_id, race_id),
    )
    if not wet_results.empty:
        features["wet_race_avg_finish"] = wet_results["position"].mean()
    else:
        features["wet_race_avg_finish"] = features.get("driver_last3_avg_pos", 15.0)

    # 4. Teammate Comparisons
    features["teammate_quali_delta_pct_rolling"] = 0.0
    features["teammate_finish_gap_rolling"] = 0.0

    if constructor_id:
        teammate_gap_query = """
            SELECT
                r1.position AS driver_pos,
                r2.position AS teammate_pos,
                r1.status AS driver_status,
                r2.status AS teammate_status,
                q1.q3_sec AS d_q3, q1.q2_sec AS d_q2, q1.q1_sec AS d_q1,
                q2.q3_sec AS t_q3, q2.q2_sec AS t_q2, q2.q1_sec AS t_q1
            FROM results r1
            JOIN results r2 ON r1.race_id = r2.race_id AND r1.constructor_id = r2.constructor_id AND r1.driver_id != r2.driver_id
            LEFT JOIN qualifying q1 ON r1.race_id = q1.race_id AND r1.driver_id = q1.driver_id
            LEFT JOIN qualifying q2 ON r2.race_id = q2.race_id AND r2.driver_id = q2.driver_id
            WHERE r1.driver_id = ? AND r1.race_id < ?
            ORDER BY r1.race_id DESC LIMIT 5
        """
        gaps = query_df(teammate_gap_query, (driver_id, race_id))

        if not gaps.empty:
            # Calculate Finish Gap (Teammate - Driver, so positive means Driver was better)
            finished_both = gaps[
                (gaps["driver_status"].isin(["Finished"]) | gaps["driver_status"].str.startswith("+")) &
                (gaps["teammate_status"].isin(["Finished"]) | gaps["teammate_status"].str.startswith("+"))
            ]
            if not finished_both.empty:
                features["teammate_finish_gap_rolling"] = (finished_both["teammate_pos"] - finished_both["driver_pos"]).mean()

            # Calculate Quali Delta Pct
            quali_deltas = []
            for _, row in gaps.iterrows():
                d_q = row["d_q3"] or row["d_q2"] or row["d_q1"]
                t_q = row["t_q3"] or row["t_q2"] or row["t_q1"]
                if pd.notna(d_q) and pd.notna(t_q) and t_q > 0:
                    quali_deltas.append((d_q - t_q) / t_q)

            if quali_deltas:
                features["teammate_quali_delta_pct_rolling"] = sum(quali_deltas) / len(quali_deltas)

    return features
