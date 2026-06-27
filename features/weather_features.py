"""Weather features."""

import pandas as pd
from data.db import query_df

def compute_weather_features(race_id: str) -> dict:
    """Compute weather-related features."""
    features = {}
    
    weather = query_df(
        "SELECT temperature, precipitation_prob, wind_speed, humidity FROM weather WHERE race_id = ?",
        (race_id,),
    )
    if not weather.empty:
        w = weather.iloc[0]
        features["track_temp_c"] = w.get("temperature", 20.0) * 1.25 # Placeholder correction
        features["wind_speed_ms"] = w.get("wind_speed", 0.0)
        features["humidity_pct"] = w.get("humidity", 50.0)
        features["temp_delta_fp2_to_race"] = 2.0 # Placeholder
        features["rain_prob"] = w.get("precipitation_prob", 0.0)
    else:
        features["track_temp_c"] = 25.0
        features["wind_speed_ms"] = 0.0
        features["humidity_pct"] = 50.0
        features["temp_delta_fp2_to_race"] = 0.0
        features["rain_prob"] = 0.0
        
    return features
