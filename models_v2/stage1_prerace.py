"""Stage 1 — Pre-race baseline predictor using XGBoost + LightGBM (+ optional CatBoost).

Improvements over original:
- Early stopping with eval_set monitoring
- CatBoost as optional third model
- Ensemble mode (soft-voting across classifiers)
- Config-driven hyperparameters (config/training_config.yaml)
- Model versioning with metadata
- SHAP explanations
- Batch prediction support
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import TimeSeriesSplit

try:
    import lightgbm as lgb
except ImportError:
    lgb = None  # type: ignore

try:
    import xgboost as xgb
except ImportError:
    xgb = None  # type: ignore

try:
    import catboost as cb
except ImportError:
    cb = None  # type: ignore

try:
    import optuna
except ImportError:
    optuna = None  # type: ignore

try:
    import shap
except ImportError:
    shap = None  # type: ignore

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

from config.settings import settings

logger = logging.getLogger(__name__)


def _load_training_config() -> dict:
    """Load training configuration from YAML file."""
    config_path = settings.project_root / "config" / "training_config.yaml"
    if yaml is not None and config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f)
    return {}


from models_v2.heads.dnf_head import DNFHead
from models_v2.heads.pitstop_head import PitStopHead
from models_v2.heads.pace_head import PaceHead

class PreRacePredictor:
    """Three-headed pre-race model orchestrator:
    - Head A (Classifier): P(DNF)
    - Head B (Regressor): Pit Stop strategy/count
    - Head C (Regressor): Race pace delta
    """

    def __init__(self, config: dict | None = None) -> None:
        self.config = config or _load_training_config()
        self.dnf_head = DNFHead()
        self.pitstop_head = PitStopHead()
        self.pace_head = PaceHead()
        self.feature_columns: list[str] = []
        self.is_fitted = False
        self.metadata: dict[str, Any] = {}
        self._train_start_time: float | None = None

    def fit(
        self,
        X: pd.DataFrame,
        y_dnf: pd.Series,
        y_stops: pd.Series,
        y_pace: pd.Series,
        optimize: bool = False,
    ) -> dict[str, float]:
        self._train_start_time = time.time()
        self.feature_columns = list(X.columns)

        # Handle NaN values safely
        numeric_cols = X.select_dtypes(include=["number"]).columns
        categorical_cols = X.select_dtypes(exclude=["number"]).columns
        
        X_clean = X.copy()
        if len(numeric_cols) > 0:
            X_clean[numeric_cols] = X_clean[numeric_cols].fillna(X_clean[numeric_cols].median())
        if len(categorical_cols) > 0:
            X_clean[categorical_cols] = X_clean[categorical_cols].fillna("Unknown").astype("category")
        logger.info("Training DNF Head...")
        self.dnf_head.fit(X_clean, y_dnf)
        
        logger.info("Training Pit Stop Head...")
        mask_stops = y_stops.notna()
        self.pitstop_head.fit(X_clean[mask_stops], y_stops[mask_stops])
        
        logger.info("Training Pace Head...")
        mask_pace = y_pace.notna()
        self.pace_head.fit(X_clean[mask_pace], y_pace[mask_pace])

        self.is_fitted = True

        train_duration = time.time() - self._train_start_time
        self.metadata = {
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "train_duration_sec": round(train_duration, 2),
            "train_size": len(X),
            "n_features": len(self.feature_columns),
            "optimized": optimize,
            "feature_columns": self.feature_columns,
        }

        logger.info("Training completed in %.1fs", train_duration)
        return {}

    def predict_batch(
        self, X: pd.DataFrame,
    ) -> dict[str, np.ndarray]:
        """Batch prediction returning all three heads."""
        assert self.is_fitted, "Model not fitted"
        X_subset = X[self.feature_columns].copy()
        numeric_cols = X_subset.select_dtypes(include=["number"]).columns
        categorical_cols = X_subset.select_dtypes(exclude=["number"]).columns
        
        if len(numeric_cols) > 0:
            X_subset[numeric_cols] = X_subset[numeric_cols].fillna(X_subset[numeric_cols].median())
        if len(categorical_cols) > 0:
            X_subset[categorical_cols] = X_subset[categorical_cols].fillna("Unknown").astype("category")
        X_clean = X_subset
        return {
            "p_dnf": self.dnf_head.predict_proba(X_clean).values,
            "expected_stops": self.pitstop_head.predict_expected_stops(X_clean).values,
            "pace_delta": self.pace_head.predict_pace_delta(X_clean).values,
        }

    def save(self, path: Path | None = None, versioned: bool = True) -> Path:
        if path is None:
            path = settings.abs_model_dir / "stage1_prerace.joblib"

        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)
        logger.info("Saved PreRacePredictor to %s", path)
        return path

    @classmethod
    def load(cls, path: Path | None = None) -> "PreRacePredictor":
        if path is None:
            path = settings.abs_model_dir / "stage1_prerace.joblib"
        model = joblib.load(path)
        logger.info("Loaded PreRacePredictor from %s", path)
        return model
