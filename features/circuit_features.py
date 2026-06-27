"""Circuit features."""

import pandas as pd
from data.db import query_df

# Hardcoded circuit families based on standard classifications
CIRCUIT_FAMILIES = {
    # Street Circuits
    'monaco': 'street',
    'baku': 'street',
    'marina_bay': 'street',
    'jeddah': 'street',
    'miami': 'street',
    'vegas': 'street',
    'albert_park': 'street', # semi-street
    'gilles_villeneuve': 'street', # semi-street
    
    # High-Speed / Low-Downforce
    'monza': 'high_speed',
    'spa': 'high_speed',
    'silverstone': 'high_speed',
    'suzuka': 'high_speed',
    'red_bull_ring': 'high_speed',
    'interlagos': 'high_speed',
    
    # Permanent Road (Default)
    'bahrain': 'permanent',
    'catalunya': 'permanent',
    'hungaroring': 'permanent',
    'zandvoort': 'permanent',
    'cota': 'permanent',
    'losail': 'permanent',
    'yas_marina': 'permanent',
    'shanghai': 'permanent',
    'imola': 'permanent',
    'mexico': 'permanent',
}

def compute_circuit_features(driver_id: str, constructor_id: str, circuit_info: dict, standings: pd.DataFrame, race_id: str = None) -> dict:
    """Compute circuit and championship context features."""
    features = {}
    
    circuit_id = circuit_info.get("id", "")
    features["drs_zones"] = circuit_info.get("drs_zones", 1)
    features["avg_pit_delta_s"] = circuit_info.get("avg_pit_delta_s", 22.0)
    
    # Track Family Form
    current_family = CIRCUIT_FAMILIES.get(circuit_id, 'permanent')
    features["constructor_family_points_rolling"] = 0.0
    
    if race_id and constructor_id:
        family_query = """
            SELECT SUM(r.points) as team_points
            FROM results r
            JOIN races c ON r.race_id = c.race_id
            WHERE r.constructor_id = ? AND r.race_id < ?
            GROUP BY r.race_id, c.circuit_id
            ORDER BY r.race_id DESC
        """
        historical_races = query_df(family_query, (constructor_id, race_id))
        
        # We must filter by family in pandas because the family mapping is in python
        if not historical_races.empty:
            # Re-query to include circuit_id directly
            hist_query = """
                SELECT r.race_id, c.circuit_id, SUM(r.points) as team_points
                FROM results r
                JOIN races c ON r.race_id = c.race_id
                WHERE r.constructor_id = ? AND r.race_id < ?
                GROUP BY r.race_id, c.circuit_id
                ORDER BY r.race_id DESC
            """
            hist = query_df(hist_query, (constructor_id, race_id))
            
            hist['family'] = hist['circuit_id'].map(lambda x: CIRCUIT_FAMILIES.get(x, 'permanent'))
            family_hist = hist[hist['family'] == current_family].head(3)
            
            if not family_hist.empty:
                features["constructor_family_points_rolling"] = family_hist['team_points'].mean()

    # Championship Standings
    driver_standing = standings[standings["driver_id"] == driver_id]
    if not driver_standing.empty:
        s = driver_standing.iloc[0]
        features["driver_championship_pos"] = s["position"]
        features["driver_championship_pts"] = s["points"]
    else:
        features["driver_championship_pos"] = 20
        features["driver_championship_pts"] = 0

    if not standings.empty:
        leader_pts = standings["points"].max()
        features["championship_pressure_driver"] = leader_pts - features["driver_championship_pts"]
        features["championship_pressure_constructor"] = 100.0 # Placeholder
    else:
        features["championship_pressure_driver"] = 0.0
        features["championship_pressure_constructor"] = 0.0

    return features
