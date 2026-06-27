"""CLI script — Backfill and evaluate all races sequentially."""

import argparse
import logging
import sys
import json
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.db import get_connection, init_db, query_df, upsert_prediction
from data.ingest import ingest_season
from data.jolpica_client import JolpicaClient
from config.settings import settings
from features.pre_race import build_pre_race_features
from features.feature_store import get_X_y
from models_v2.stage1_prerace import PreRacePredictor
from models_v2.stage3_ensemble import enforce_podium_constraints

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

def compute_score(predicted: list[str], actual: list[str]) -> float:
    score = 0.0
    for i in range(3):
        if i < len(predicted) and i < len(actual):
            if predicted[i] == actual[i]:
                score += 3.0  # Exact match
            elif predicted[i] in actual:
                score += 1.0  # Partial match
    return score / 9.0  # Max score is 9

def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate races sequentially and store predictions")
    args = parser.parse_args()

    init_db()

    # Step A: Fetch Race Data (latest)
    current_year = datetime.now().year
    logger.info("Fetching latest race data for %d...", current_year)
    client = JolpicaClient()
    try:
        ingest_season(current_year, client)
    except Exception as e:
        logger.error("Failed to ingest latest season: %s", e)
    finally:
        client.close()

    # Load Model
    model_path = settings.abs_model_dir / "stage1_prerace.joblib"
    if not model_path.exists():
        logger.error("Model not found at %s. Please train the model first.", model_path)
        return
    model = PreRacePredictor.load(model_path)
    if not model.is_fitted:
        logger.error("Model is not fitted.")
        return

    # Step B: Sequential Processing
    # Get all races ordered by year and round
    races_df = query_df("SELECT * FROM races ORDER BY year ASC, round ASC")
    
    for _, race in races_df.iterrows():
        race_id = race["race_id"]
        year = race["year"]
        round_number = race["round"]

        # Check if already processed
        pred_df = query_df("SELECT * FROM predictions WHERE race_id = ?", (race_id,))
        if not pred_df.empty:
            continue

        # Check if actual results exist (is completed)
        results_df = query_df(
            "SELECT driver_id FROM results WHERE race_id = ? AND position <= 3 ORDER BY position ASC",
            (race_id,)
        )
        if results_df.empty or len(results_df) < 3:
            # Race not completed or no podium data
            continue

        actual_podium = results_df["driver_id"].tolist()[:3]

        logger.info("Evaluating race %s (%d R%d)...", race_id, year, round_number)
        
        # Predict
        try:
            race_features_df = build_pre_race_features(year, round_number)
            if race_features_df.empty:
                logger.warning("No feature data for %s, skipping.", race_id)
                continue

            X, _ = get_X_y(race_features_df, "is_podium")
            driver_ids = race_features_df["driver_id"].tolist()
            
            podium_probs = model.predict_podium_proba(X)
            pos_preds = model.predict_position(X)
            
            prob_dict = dict(zip(driver_ids, podium_probs.tolist()))
            pos_dict = dict(zip(driver_ids, pos_preds.tolist()))
            
            result = enforce_podium_constraints(prob_dict, pos_dict)
            predicted_podium = [str(p.driver_id) for p in result.podium]
            
            # Compare and score
            accuracy = compute_score(predicted_podium, actual_podium)
            
            # Persist
            with get_connection() as conn:
                upsert_prediction(conn, {
                    "race_id": race_id,
                    "predicted_podium": json.dumps(predicted_podium),
                    "actual_podium": json.dumps(actual_podium),
                    "accuracy_score": accuracy,
                    "processed_at": datetime.utcnow().isoformat() + "Z"
                })
            logger.info("Successfully evaluated %s. Accuracy: %.2f", race_id, accuracy)
        except Exception as e:
            logger.error("Error evaluating race %s: %s", race_id, e)

    logger.info("Evaluation complete.")

if __name__ == "__main__":
    main()
