"""Production inference script for continuous rolling walk-forward modeling."""

import logging
import sys
from pathlib import Path

import pandas as pd
from config.settings import settings
from data.db import query_df
from data.jolpica_client import JolpicaClient
from features.feature_store import get_training_features, get_X_y
from features.pre_race import build_pre_race_features
from models_v2.stage1_prerace import PreRacePredictor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

def main() -> None:
    # 1. Identify completed races vs upcoming races
    # A race is "completed" if it has results in the database
    completed_races_query = """
        SELECT DISTINCT r.year, r.round 
        FROM results res
        JOIN races r ON res.race_id = r.race_id
        ORDER BY r.year DESC, r.round DESC 
        LIMIT 1
    """
    latest_completed = query_df(completed_races_query)
    
    if latest_completed.empty:
        logger.error("No completed races found in database. Run ingestion first.")
        return
        
    last_year = int(latest_completed.iloc[0]["year"])
    last_round = int(latest_completed.iloc[0]["round"])
    logger.info("Latest completed race is %d R%d", last_year, last_round)
    
    # The DB only contains races with results. We need to query the API to get the full schedule.
    client = JolpicaClient()
    schedule = client.get_schedule(last_year)
    
    upcoming_year = None
    upcoming_round = None
    upcoming_name = None
    
    upcoming_circuit_id = None
    upcoming_country = ""
    upcoming_date = ""
    for race in schedule:
        r_round = int(race["round"])
        if r_round > last_round:
            upcoming_year = last_year
            upcoming_round = r_round
            upcoming_name = race.get("Circuit", {}).get("circuitName", "Unknown")
            upcoming_circuit_id = race.get("Circuit", {}).get("circuitId", "")
            upcoming_country = race.get("Circuit", {}).get("Location", {}).get("country", "")
            upcoming_date = race.get("date", "")
            break
            
    if upcoming_year is None:
        logger.error("No upcoming races found in schedule for %d.", last_year)
        return
        
    logger.info("Upcoming race to predict: %d R%d (%s)", upcoming_year, upcoming_round, upcoming_name)
    
    # Insert the upcoming race into the DB so features/pre_race.py can find it
    race_id = f"{upcoming_year}_{upcoming_round}"
    from data.db import upsert_race, get_connection
    from data.ingest import _circuit_key
    with get_connection() as conn:
        upsert_race(conn, {
            "race_id": race_id,
            "year": upcoming_year,
            "round": upcoming_round,
            "circuit_id": _circuit_key(upcoming_circuit_id),
            "circuit_name": upcoming_name,
            "country": upcoming_country,
            "race_date": upcoming_date,
            "total_laps": None,
        })
    
    # 2. Rebuild/load features for all completed history
    # The get_training_features function joins results, so it only returns completed races
    logger.info("Loading training data up to %d R%d...", last_year, last_round)
    # Set end_year to upcoming_year to ensure we get all completed races up to this point
    train_df = get_training_features(start_year=2018, end_year=upcoming_year, force_rebuild=False)
    
    if train_df.empty:
        logger.error("No training data generated.")
        return
        
    logger.info("Loaded %d rows of training data.", len(train_df))
    
    # 3. Train model on all history
    logger.info("Training LightGBM model on all historical data...")
    X_train, y_train_podium = get_X_y(train_df, "is_podium")
    _, y_train_position = get_X_y(train_df, "finish_position")
    
    model = PreRacePredictor()
    model.fit(X_train, y_train_podium, y_train_position, optimize=False)
    
    # 4. Save model to the global path expected by the API
    model_dir = settings.abs_model_dir
    model_dir.mkdir(exist_ok=True, parents=True)
    model_path = model_dir / "stage1_prerace.joblib"
    model.save(model_path)
    logger.info("Saved production model to %s", model_path)
    
    # 5. Build features for the upcoming race and predict
    # build_pre_race_features fetches data for a specific race even if it lacks results
    logger.info("Building features for upcoming race %s...", upcoming_name)
    try:
        race_df = build_pre_race_features(upcoming_year, upcoming_round)
        
        if race_df.empty:
            logger.warning("Could not build features for %s (data might not be available yet).", upcoming_name)
            return
            
        X_test, _ = get_X_y(race_df, "is_podium")
        driver_ids = race_df["driver_id"].tolist()
        
        podium_probs = model.predict_podium_proba(X_test)
        
        # Sort drivers by podium probability
        predictions = sorted(zip(driver_ids, podium_probs), key=lambda x: x[1], reverse=True)
        
        logger.info("--- PREDICTIONS FOR %s ---", upcoming_name)
        for i, (driver, prob) in enumerate(predictions[:10]):
            logger.info("%d. %s: %.1f%%", i+1, driver, prob * 100)
            
    except Exception as e:
        logger.error("Failed to predict upcoming race: %s", e)

if __name__ == "__main__":
    main()
