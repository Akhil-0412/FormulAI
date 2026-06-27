"""Safety car features — Computed from historical race data."""

import numpy as np

from data.db import query_df


def compute_safety_car_features(circuit_id: str, circuit_info: dict, rain_prob: float) -> dict:
    """Compute safety car related features from actual DB data."""
    features = {}

    features["circuit_sc_probability"] = circuit_info.get("sc_probability", 0.0)
    features["circuit_vsc_probability"] = circuit_info.get("vsc_probability", 0.0)
    features["is_street_circuit"] = circuit_info.get("is_street_circuit", 0)

    # Historical DNF rate at this circuit (from actual results)
    circuit_results = query_df(
        """SELECT res.status FROM results res
           JOIN races r ON res.race_id = r.race_id
           WHERE r.circuit_id = ?""",
        (circuit_id,),
    )
    if not circuit_results.empty:
        dnfs = circuit_results["status"].apply(
            lambda s: not (s == "Finished" or (s and str(s).startswith("+")))
        ).sum()
        features["historical_dnf_rate_circuit"] = dnfs / len(circuit_results)
    else:
        features["historical_dnf_rate_circuit"] = 0.1

    # Grid compactness: how close are the qualifying times at this circuit?
    # Computed from qualifying time spread (Q1 times)
    quali_times = query_df(
        """SELECT q.q1_sec FROM qualifying q
           JOIN races r ON q.race_id = r.race_id
           WHERE r.circuit_id = ? AND q.q1_sec IS NOT NULL""",
        (circuit_id,),
    )
    if not quali_times.empty and len(quali_times) > 5:
        times = quali_times["q1_sec"].values
        # Coefficient of variation: lower = more compact grid
        mean_time = np.mean(times)
        if mean_time > 0:
            features["grid_compactness"] = float(1.0 - np.std(times) / mean_time)
        else:
            features["grid_compactness"] = 0.5
    else:
        features["grid_compactness"] = 0.5

    features["wet_race_probability"] = rain_prob
    features["wet_race_sc_multiplier"] = 1.5 if rain_prob > 0.5 else 1.0

    return features
