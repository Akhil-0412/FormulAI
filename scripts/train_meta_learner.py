"""Train Meta Learner (Stage 2 TabNet)."""

import argparse
import logging
import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

from pathlib import Path
import pandas as pd
import numpy as np

from config.settings import settings
from features.feature_store import get_training_features, get_X_y
from models_v2.stage1_prerace import PreRacePredictor
from models_v2.stage2_xgb import Stage2XGB

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=2018, help="Train start year")
    parser.add_argument("--end", type=int, default=2024, help="Train end year")
    args = parser.parse_args()

    logger.info("Loading Stage 1 PreRace model...")
    try:
        stage1 = PreRacePredictor.load()
    except Exception as e:
        logger.error(f"Failed to load Stage 1 model. Make sure to train it first! Error: {e}")
        return

    logger.info(f"Loading features from {args.start} to {args.end}...")
    df = get_training_features(start_year=args.start, end_year=args.end, force_rebuild=True)
    if df.empty:
        logger.error("No training data found.")
        return

    X, y_position = get_X_y(df, "finish_position")
    y_position = y_position.fillna(20)

    logger.info("Generating Stage 1 Out-Of-Fold predictions (using full set for now)...")
    stage1_preds = stage1.predict_batch(X)
    
    # Enrich X with Stage 1 predictions
    X_enriched = X.copy()
    X_enriched["pred_dnf"] = np.asarray(stage1_preds["p_dnf"])
    X_enriched["pred_stops"] = np.asarray(stage1_preds["expected_stops"])
    X_enriched["pred_pace"] = np.asarray(stage1_preds["pace_delta"])

    # Drop columns that shouldn't be used for training (like race_id) if any
    if "race_id" in X_enriched.columns:
        X_enriched = X_enriched.drop(columns=["race_id"])

    logger.info(f"Initializing Stage 2 XGBoost with {len(X_enriched.columns)} features...")
    model = Stage2XGB()

    logger.info("Training XGBoost (this will be fast)...")
    model.fit(X_enriched, y_position)

    save_path = settings.abs_model_dir / "stage2_xgb.joblib"
    model.save(save_path)
    logger.info(f"Training complete. Meta-Learner saved to {save_path}")

if __name__ == "__main__":
    main()
