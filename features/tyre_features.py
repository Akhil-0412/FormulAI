"""Tyre features — Computed from pit stop history and circuit characteristics."""

from data.db import query_df, race_seq, race_seq_sql


def compute_tyre_features(
    driver_id: str, circuit_id: str, circuit_info: dict, race_id: str | None = None
) -> dict:
    """Compute tyre-related features from actual DB data."""
    features = {}

    features["circuit_tyre_stress_index"] = circuit_info.get("tyre_stress_index", 0.5)

    before = race_seq(race_id) if race_id else 999999

    # Expected pit stops: historical average for this circuit
    circuit_stops = query_df(
        f"""SELECT COUNT(*) as n_stops, p.race_id
           FROM pit_stops p
           JOIN races c ON p.race_id = c.race_id
           WHERE c.circuit_id = ? AND {race_seq_sql("p.race_id")} < ?
           GROUP BY p.race_id, p.driver_id""",
        (circuit_id, before),
    )
    if not circuit_stops.empty:
        features["expected_pit_stops"] = circuit_stops["n_stops"].mean()
    else:
        features["expected_pit_stops"] = 1.5

    # Degradation proxy: variance in pit stop lap numbers for this circuit
    # High variance = more strategy flexibility = lower deg pressure
    pit_laps = query_df(
        f"""SELECT p.lap FROM pit_stops p
           JOIN races c ON p.race_id = c.race_id
           WHERE c.circuit_id = ? AND p.stop_number = 1
             AND {race_seq_sql("p.race_id")} < ?""",
        (circuit_id, before),
    )
    if not pit_laps.empty and len(pit_laps) > 2:
        features["pit_window_spread"] = float(pit_laps["lap"].std())
    else:
        features["pit_window_spread"] = 5.0

    return features
