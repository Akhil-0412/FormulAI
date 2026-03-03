"""Training orchestrator — temporal cross-validation and model persistence."""

from __future__ import annotations

import logging

import pandas as pd

from config.settings import settings
from features.feature_store import get_training_features, get_X_y
from models.stage1_prerace import PreRacePredictor

logger = logging.getLogger(__name__)


def train_with_temporal_cv(
    train_start: int = 2018,
    train_end: int = 2023,
    val_year: int = 2024,
    optimize: bool = True,
) -> dict:
    """Train the Stage 1 model using temporal cross-validation.

    Folds:
      Fold 1: Train 2018–2020 → Validate 2021
      Fold 2: Train 2018–2021 → Validate 2022
      Fold 3: Train 2018–2022 → Validate 2023
      Final:  Train 2018–2023 → Test on val_year

    Returns:
        Dict with fold metrics and final model.
    """
    logger.info("Building feature set for %d–%d...", train_start, val_year)
    full_df = get_training_features(train_start, val_year)

    if full_df.empty:
        raise RuntimeError("No training data available. Run ingestion first.")

    fold_results = []

    # ── Temporal CV folds ───────────────────────────────────────────
    for val_yr in range(train_end - 2, train_end + 1):
        # Explicit temporal split for Train, Calibrate, Validate
        # Example: Train 18-21, Calibrate 22, Validate 23
        calib_yr = val_yr - 1
        
        train_df = full_df[full_df["race_id"].apply(lambda x: int(x.split("_")[0]) < calib_yr)]
        calib_df = full_df[full_df["race_id"].apply(lambda x: int(x.split("_")[0]) == calib_yr)]
        val_df = full_df[full_df["race_id"].apply(lambda x: int(x.split("_")[0]) == val_yr)]

        if train_df.empty or calib_df.empty or val_df.empty:
            logger.warning("Skipping fold for val_year=%d (insufficient data)", val_yr)
            continue

        X_train, y_train_podium = get_X_y(train_df, "is_podium")
        y_train_pos = train_df["finish_position"]
        
        X_calib, y_calib_podium = get_X_y(calib_df, "is_podium")
        
        X_val, y_val_podium = get_X_y(val_df, "is_podium")
        y_val_pos = val_df["finish_position"]

        model = PreRacePredictor()
        
        # Train with calibration
        model.fit(
            X_train, y_train_podium, y_train_pos, 
            X_calib=X_calib, y_calib_podium=y_calib_podium, 
            optimize=False
        )

        # Evaluate on validation
        val_metrics = model._compute_metrics(X_val, y_val_podium, y_val_pos)
        val_metrics["fold_val_year"] = val_yr
        val_metrics["train_size"] = len(X_train)
        val_metrics["calib_size"] = len(X_calib)
        val_metrics["val_size"] = len(X_val)
        fold_results.append(val_metrics)

        logger.info("Fold val_year=%d: AUC=%.4f, F1=%.4f (train=%d, calib=%d, val=%d)",
                     val_yr, val_metrics["classifier_auc"],
                     val_metrics["classifier_f1"],
                     len(X_train), len(X_calib), len(X_val))

    # ── Final model ─────────────────────────────────────────────────
    calib_end_yr = train_end
    train_end_yr = train_end - 1
    logger.info("Training final model (Train: %d–%d, Calibrate: %d)...", train_start, train_end_yr, calib_end_yr)
    
    train_df = full_df[full_df["race_id"].apply(lambda x: int(x.split("_")[0]) <= train_end_yr)]
    calib_df = full_df[full_df["race_id"].apply(lambda x: int(x.split("_")[0]) == calib_end_yr)]
    test_df = full_df[full_df["race_id"].apply(lambda x: int(x.split("_")[0]) == val_year)]

    X_train, y_train_podium = get_X_y(train_df, "is_podium")
    y_train_pos = train_df["finish_position"]
    
    X_calib, y_calib_podium = get_X_y(calib_df, "is_podium")

    final_model = PreRacePredictor()
    train_metrics = final_model.fit(
        X_train, y_train_podium, y_train_pos, 
        X_calib=X_calib, y_calib_podium=y_calib_podium, 
        optimize=optimize
    )

    # Test set evaluation
    test_metrics: dict = {}
    if not test_df.empty:
        X_test, y_test_podium = get_X_y(test_df, "is_podium")
        y_test_pos = test_df["finish_position"]
        test_metrics = final_model._compute_metrics(X_test, y_test_podium, y_test_pos)
        logger.info("Test metrics (%d): %s", val_year, test_metrics)

    # Save model
    model_path = final_model.save()

    return {
        "fold_results": fold_results,
        "train_metrics": train_metrics,
        "test_metrics": test_metrics,
        "model_path": str(model_path),
        "feature_importance": final_model.get_feature_importance().to_dict("records"),
    }
