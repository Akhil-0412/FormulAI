"""Evaluation harness to benchmark models against the 2025 season."""

import json
import logging
import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score, brier_score_loss
import numpy as np

from config.settings import settings
from features.feature_store import get_training_features, get_X_y
from models_v2.stage1_prerace import PreRacePredictor
from models_v2.stage2_tabnet import Stage2TabNet

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger(__name__)

def evaluate_predictions(y_true: pd.Series, y_prob: np.ndarray) -> dict:
    """Compute binary classification metrics."""
    y_pred = (y_prob >= 0.5).astype(int)
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, y_prob)),
        "brier_score": float(brier_score_loss(y_true, y_prob)),
    }

def run_benchmark():
    # 1. Load data
    logger.info("Rebuilding feature cache for 2018-2025 to ensure schema consistency...")
    df = get_training_features(start_year=2018, end_year=2025, force_rebuild=True)
    if df.empty:
        logger.error("No training data available.")
        return

    # 2. Extract test (2025)
    df["year"] = df["race_id"].str.split("_").str[0].astype(int)
    test_df = df[df["year"] == 2025].copy()
    
    if test_df.empty:
        logger.warning("No 2025 test data available. Using last 20% of data for test.")
        split_idx = int(len(df) * 0.8)
        test_df = df.iloc[split_idx:].copy()
        
    X_test, y_test_podium = get_X_y(test_df, "is_podium")
    logger.info("Test set: %d rows", len(X_test))

    # 3. Load models
    logger.info("Loading Stage 1 (PreRacePredictor) and Stage 2 (TabNet) models_v2...")
    try:
        stage1 = PreRacePredictor.load()
        stage2 = Stage2TabNet.load()
    except Exception as e:
        logger.error(f"Failed to load models! Make sure you trained both Stage 1 and Stage 2. Error: {e}")
        return

    # 4. Generate Predictions
    logger.info("Running Stage 1 Inference...")
    stage1_preds = stage1.predict_batch(X_test)
    
    X_test_enriched = X_test.copy()
    X_test_enriched["pred_dnf"] = stage1_preds["p_dnf"]
    X_test_enriched["pred_stops"] = stage1_preds["expected_stops"]
    X_test_enriched["pred_pace"] = stage1_preds["pace_delta"]

    # numeric only
    numeric_cols = X_test_enriched.select_dtypes(include=["number"]).columns
    X_test_numeric = X_test_enriched[numeric_cols].fillna(X_test_enriched[numeric_cols].median()).fillna(0)

    logger.info("Running Stage 2 TabNet Inference...")
    y_prob = stage2.predict_proba(X_test_numeric)

    # 5. Evaluate
    metrics = evaluate_predictions(y_test_podium, y_prob.values)
    
    # Race-level accuracy (how many podiums correctly predicted out of 3?)
    race_ids = test_df["race_id"].unique()
    race_accuracies = []
    
    for rid in race_ids:
        race_mask = test_df["race_id"] == rid
        race_X = X_test_numeric[race_mask]
        race_y = y_test_podium[race_mask]
        
        if race_X.empty:
            continue
            
        race_prob = stage2.predict_proba(race_X).values
        
        top_3_pred_idx = np.argsort(race_prob)[-3:]
        actual_podium_idx = np.where(race_y.values == 1)[0]
        correct_podiums = len(set(top_3_pred_idx).intersection(set(actual_podium_idx)))
        race_accuracies.append(correct_podiums)
        
    metrics["race_level_avg_correct_out_of_3"] = float(np.mean(race_accuracies)) if race_accuracies else 0.0
    metrics["race_level_perfect_3"] = float(np.mean(np.array(race_accuracies) == 3)) if race_accuracies else 0.0
    
    logger.info("=== ENSEMBLE METRICS ===")
    logger.info(json.dumps(metrics, indent=2))

    # 6. Save results
    reports_dir = settings.project_root / "reports"
    reports_dir.mkdir(exist_ok=True)
    
    results = {"V2_Ensemble": metrics}
    with open(reports_dir / "model_benchmark.json", "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    run_benchmark()
