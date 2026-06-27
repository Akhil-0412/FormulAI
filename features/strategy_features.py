"""Strategy features — Computed from pit stop history and circuit characteristics."""

from data.db import query_df


def compute_strategy_features(driver_id: str, circuit_info: dict) -> dict:
    """Compute strategy-related features from actual DB data."""
    features = {}

    circuit_id = circuit_info.get("id", "")

    # 1. Undercut viability: based on pit delta and overtake difficulty
    pit_delta = circuit_info.get("avg_pit_delta_s", 22.0)
    overtake_diff = circuit_info.get("overtake_difficulty", 0.5)
    # Lower pit delta + higher overtake difficulty = more undercut viable
    features["undercut_viability"] = max(0.0, min(1.0,
        (1.0 - pit_delta / 30.0) * 0.5 + overtake_diff * 0.5
    ))

    # 2. Team strategy tendency: avg pit stops per race for this constructor (from DB)
    features["team_strategy_tendency"] = 1.5  # Will be overridden below if data exists

    # 3. Track evolution factor from circuit info
    features["track_evolution_factor"] = circuit_info.get("track_evolution_factor", 0.1)

    return features


def compute_strategy_features_with_db(
    driver_id: str, constructor_id: str, circuit_info: dict, race_id: str
) -> dict:
    """Extended strategy features using DB data."""
    features = compute_strategy_features(driver_id, circuit_info)

    # Team strategy tendency: avg pit stops for this constructor
    team_stops = query_df(
        """SELECT COUNT(*) as n_stops, p.race_id
           FROM pit_stops p
           JOIN results r ON p.race_id = r.race_id AND p.driver_id = r.driver_id
           WHERE r.constructor_id = ? AND p.race_id < ?
           GROUP BY p.race_id
           ORDER BY p.race_id DESC
           LIMIT 10""",
        (constructor_id, race_id),
    )
    if not team_stops.empty:
        features["team_strategy_tendency"] = team_stops["n_stops"].mean()

    # Circuit historical avg pit stops
    circuit_stops = query_df(
        """SELECT COUNT(*) as n_stops, p.race_id
           FROM pit_stops p
           JOIN races c ON p.race_id = c.race_id
           WHERE c.circuit_id = (
               SELECT circuit_id FROM races WHERE race_id = ?
           ) AND p.race_id < ?
           GROUP BY p.race_id""",
        (race_id, race_id),
    )
    if not circuit_stops.empty:
        features["circuit_avg_pit_stops"] = circuit_stops["n_stops"].mean()
    else:
        features["circuit_avg_pit_stops"] = 1.5

    return features
