"""Training orchestrator — temporal cross-validation for LTR model.

FormulAI v3: Uses Learning-to-Rank with group-aware temporal splits.
Trains XGBoost LambdaMART + LightGBM ranker ensemble.
Optionally trains DNF/Pace auxiliary heads and injects as features.
"""

from __future__ import annotations

import json
import logging
import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

try:
    import mlflow
except ImportError:
    mlflow = None

try:
    import yaml
except ImportError:
    yaml = None

from config.settings import settings
from features.feature_store import get_training_features, get_X_y, get_X_y_grouped
from models_v2.ltr_ranker import F1LTRRanker

logger = logging.getLogger(__name__)


def _load_config(config_path: str | Path | None = None) -> dict:
    """Load training config from YAML."""
    if config_path is None:
        config_path = settings.project_root / "config" / "training_config.yaml"
    else:
        config_path = Path(config_path)

    if yaml is not None and config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f)
    return {}


def _train_auxiliary_heads(
    train_df: pd.DataFrame,
    feature_columns: list[str],
) -> tuple:
    """Train DNF and Pace auxiliary heads for feature injection.

    Returns:
        (dnf_head, pace_head) — fitted model objects or (None, None) on failure.
    """
    from models_v2.heads.dnf_head import DNFHead
    from models_v2.heads.pace_head import PaceHead

    X_train = train_df[feature_columns].copy()
    # Drop non-numeric
    for col in X_train.columns:
        if X_train[col].dtype == object:
            X_train = X_train.drop(columns=[col])

    numeric_cols = X_train.select_dtypes(include=["number"]).columns
    X_train[numeric_cols] = X_train[numeric_cols].fillna(X_train[numeric_cols].median()).fillna(0)

    dnf_head = None
    pace_head = None

    # DNF Head
    y_dnf = train_df.get("is_dnf", pd.Series([0] * len(train_df)))
    if y_dnf.sum() > 5:  # Need some positive examples
        try:
            dnf_head = DNFHead(params={
                "max_depth": 4, "learning_rate": 0.05, "n_estimators": 200,
                "objective": "binary:logistic", "eval_metric": "logloss",
                "enable_categorical": False, "device": "cpu",
            })
            dnf_head.fit(X_train, y_dnf)
            logger.info("DNF head trained (DNFs: %d/%d)", int(y_dnf.sum()), len(y_dnf))
        except Exception as e:
            logger.warning("DNF head training failed: %s", e)
            dnf_head = None

    # Pace Head (predict finish position as a pace proxy)
    y_pos = train_df.get("finish_position", pd.Series([10.0] * len(train_df)))
    mask_pos = y_pos.notna() & (y_pos > 0)
    if mask_pos.sum() > 10:
        try:
            pace_head = PaceHead(params={
                "max_depth": 6, "learning_rate": 0.05, "n_estimators": 250,
                "objective": "reg:squarederror",
                "enable_categorical": False, "device": "cpu",
            })
            pace_head.fit(X_train[mask_pos], y_pos[mask_pos])
            logger.info("Pace head trained on %d samples", int(mask_pos.sum()))
        except Exception as e:
            logger.warning("Pace head training failed: %s", e)
            pace_head = None

    return dnf_head, pace_head


def _inject_auxiliary_features(
    df: pd.DataFrame,
    feature_columns: list[str],
    dnf_head,
    pace_head,
) -> pd.DataFrame:
    """Inject P(DNF) and predicted_pace as new features into the DataFrame."""
    X = df[feature_columns].copy()
    for col in X.columns:
        if X[col].dtype == object:
            X = X.drop(columns=[col])
    numeric_cols = X.select_dtypes(include=["number"]).columns
    X[numeric_cols] = X[numeric_cols].fillna(X[numeric_cols].median()).fillna(0)

    df_out = df.copy()

    if dnf_head is not None and dnf_head.is_fitted:
        try:
            # Align columns
            shared_cols = [c for c in dnf_head.feature_columns if c in X.columns]
            p_dnf = dnf_head.predict_proba(X[shared_cols])
            df_out["aux_p_dnf"] = p_dnf.values
        except Exception as e:
            logger.warning("DNF feature injection failed: %s", e)
            df_out["aux_p_dnf"] = 0.0
    else:
        df_out["aux_p_dnf"] = 0.0

    if pace_head is not None and pace_head.is_fitted:
        try:
            shared_cols = [c for c in pace_head.feature_columns if c in X.columns]
            pace = pace_head.predict_pace_delta(X[shared_cols])
            df_out["aux_predicted_pace"] = pace.values
        except Exception as e:
            logger.warning("Pace feature injection failed: %s", e)
            df_out["aux_predicted_pace"] = 10.0
    else:
        df_out["aux_predicted_pace"] = 10.0

    return df_out


def train_ltr_model(
    train_start: int = 2014,
    train_end: int = 2024,
    val_year: int = 2025,
    optimize: bool = True,
    config_path: str | Path | None = None,
) -> dict:
    """Train the FormulAI v3 LTR model.

    Steps:
    1. Build full feature set
    2. Train auxiliary DNF/Pace heads on training data
    3. Inject P(DNF) and pace_delta as features
    4. Split into temporal train/val
    5. Train LTR ensemble (XGBoost + LightGBM rankers)
    6. Save model

    Returns:
        Dict with training results and model path.
    """
    config = _load_config(config_path)
    experiment_name = config.get("experiment", {}).get("name", "ltr_v3")
    start_time = time.time()

    logger.info("=== FormulAI v3 LTR Training ===")
    logger.info("Train: %d–%d | Val: %d", train_start, train_end, val_year)

    # 1. Build features
    full_df = get_training_features(train_start, val_year, force_rebuild=True)
    if full_df.empty:
        raise RuntimeError("No training data. Run ingestion first.")

    logger.info("Full dataset: %d rows, %d columns", len(full_df), len(full_df.columns))

    # 2. Temporal split
    train_df = full_df[
        full_df["race_id"].apply(lambda x: int(x.split("_")[0]) <= train_end)
    ].copy()
    val_df = full_df[
        full_df["race_id"].apply(lambda x: int(x.split("_")[0]) == val_year)
    ].copy()

    if train_df.empty:
        raise RuntimeError(f"No training data for {train_start}-{train_end}")

    logger.info("Train: %d rows (%d races) | Val: %d rows (%d races)",
                len(train_df), train_df["race_id"].nunique(),
                len(val_df), val_df["race_id"].nunique())

    # 3. Get initial feature columns (before auxiliary injection)
    from features.feature_store import get_feature_columns
    base_feature_cols = get_feature_columns(train_df)
    # Filter to numeric only
    base_feature_cols = [
        c for c in base_feature_cols
        if c in train_df.columns and train_df[c].dtype != object
    ]

    # 4. Train auxiliary heads
    logger.info("Training auxiliary heads...")
    dnf_head, pace_head = _train_auxiliary_heads(train_df, base_feature_cols)

    # 5. Inject auxiliary features
    train_df = _inject_auxiliary_features(train_df, base_feature_cols, dnf_head, pace_head)
    if not val_df.empty:
        val_df = _inject_auxiliary_features(val_df, base_feature_cols, dnf_head, pace_head)

    # 6. Get LTR-format data
    X_train, y_train, group_train, train_race_ids = get_X_y_grouped(train_df, target="relevance")

    X_val, y_val, group_val = None, None, None
    if not val_df.empty:
        X_val, y_val, group_val, val_race_ids = get_X_y_grouped(val_df, target="relevance")

    logger.info("Features: %d | Train groups: %d | Val groups: %s",
                len(X_train.columns), len(group_train),
                len(group_val) if group_val is not None else "N/A")

    # 7. Train LTR model
    best_params = config.get("models", {}).get("ltr_ranker", {}).get("best_params", None)
    if best_params:
        logger.info("Using optimized hyperparameters from config.")
        blend_weight = best_params.pop("blend_weight_xgb", 0.5)
        model = F1LTRRanker(xgb_params=best_params, lgb_params=best_params, blend_weight_xgb=blend_weight)
    else:
        model = F1LTRRanker()
    train_metrics = model.fit(
        X_train, y_train, group_train,
        X_val, y_val, group_val,
        optimize=optimize,
        n_trials=config.get("optimization", {}).get("n_trials", 30),
    )

    # 8. Save
    model_path = model.save()

    # Also save auxiliary heads
    if dnf_head is not None:
        import joblib
        joblib.dump(dnf_head, settings.abs_model_dir / "aux_dnf_head.joblib")
    if pace_head is not None:
        import joblib
        joblib.dump(pace_head, settings.abs_model_dir / "aux_pace_head.joblib")

    # 9. MLflow tracking
    if mlflow is not None:
        try:
            mlflow.set_experiment(experiment_name)
            with mlflow.start_run():
                mlflow.log_params({
                    "train_start": train_start,
                    "train_end": train_end,
                    "val_year": val_year,
                    "model_type": "LTR_ensemble",
                    "optimize": optimize,
                    "blend_weight_xgb": model.blend_weight_xgb,
                    "softmax_temperature": model.softmax_temperature,
                })
                mlflow.log_metrics(train_metrics)
                mlflow.log_artifact(str(model_path))
        except Exception as e:
            logger.warning("MLflow logging failed: %s", e)

    duration = time.time() - start_time
    logger.info("=== Training complete in %.1fs ===", duration)

    return {
        "status": "success",
        "model_path": str(model_path),
        "train_size": len(X_train),
        "val_size": len(X_val) if X_val is not None else 0,
        "n_features": len(X_train.columns),
        "duration": duration,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Train FormulAI v3 LTR Model")
    parser.add_argument("--start", type=int, default=2014, help="Train start year")
    parser.add_argument("--end", type=int, default=2024, help="Train end year")
    parser.add_argument("--val", type=int, default=2025, help="Validation year")
    parser.add_argument("--optimize", action="store_true", help="Run hyperparameter optimization")
    parser.add_argument("--no-optimize", action="store_true", help="Skip optimization")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    optimize = args.optimize and not args.no_optimize

    result = train_ltr_model(
        train_start=args.start,
        train_end=args.end,
        val_year=args.val,
        optimize=optimize,
    )
    logger.info("Training result: %s", result)
