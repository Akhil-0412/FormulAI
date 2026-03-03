"""Stage 1 — Pre-race baseline predictor using XGBoost + LightGBM."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.calibration import CalibratedClassifierCV

try:
    import lightgbm as lgb
except ImportError:
    lgb = None  # type: ignore

try:
    import xgboost as xgb
except ImportError:
    xgb = None  # type: ignore

try:
    import optuna
    from optuna.integration import XGBoostPruningCallback
except ImportError:
    optuna = None  # type: ignore

from config.settings import settings

logger = logging.getLogger(__name__)


class PreRacePredictor:
    """Two-headed pre-race model:

    - Head A (classifier): P(podium | driver, race) via XGBoost
    - Head B (regressor): predicted finish position via LightGBM
    """

    def __init__(self) -> None:
        self.classifier = None  # XGBoost binary classifier
        self.regressor = None  # LightGBM regressor
        self.feature_columns: list[str] = []
        self.is_fitted = False

    # ── Training ────────────────────────────────────────────────────

    def fit(
        self,
        X: pd.DataFrame,
        y_podium: pd.Series,
        y_position: pd.Series,
        X_calib: pd.DataFrame | None = None,
        y_calib_podium: pd.Series | None = None,
        optimize: bool = True,
    ) -> dict[str, float]:
        """Train both heads and optionally calibrate the classifier.

        Args:
            X: Feature matrix for training.
            y_podium: Binary target (1 = podium, 0 = not).
            y_position: Ordinal target (finish position 1–20).
            X_calib: Feature matrix for isotonic calibration (validation set).
            y_calib_podium: Binary target for calibration.
            optimize: If True, run Optuna hyperparameter search.

        Returns:
            Dict of training metrics.
        """
        self.feature_columns = list(X.columns)

        # Handle NaN values
        X_clean = X.fillna(X.median())

        # Class imbalance ratio
        n_pos = y_podium.sum()
        n_neg = len(y_podium) - n_pos
        scale_pos_weight = n_neg / max(n_pos, 1)
        logger.info("Class balance: %d positive, %d negative (ratio: %.2f)",
                     n_pos, n_neg, scale_pos_weight)

        # ── Head A: XGBoost classifier ──────────────────────────────
        if optimize and optuna is not None:
            best_params_cls = self._optimize_classifier(X_clean, y_podium, scale_pos_weight)
        else:
            best_params_cls = {
                "max_depth": 6,
                "learning_rate": 0.05,
                "n_estimators": 300,
                "subsample": 0.8,
                "colsample_bytree": 0.8,
                "min_child_weight": 3,
                "reg_alpha": 0.1,
                "reg_lambda": 1.0,
            }

        self.classifier = xgb.XGBClassifier(
            **best_params_cls,
            scale_pos_weight=scale_pos_weight,
            objective="binary:logistic",
            eval_metric="logloss",
            random_state=settings.random_seed,
            use_label_encoder=False,
        )
        self.classifier.fit(X_clean, y_podium)
        
        # Apply Isotonic Calibration if a separate temporal dataset is passed
        if X_calib is not None and y_calib_podium is not None:
            logger.info("Applying Isotonic Calibration using separate temporal split...")
            X_c_clean = X_calib.fillna(X_calib.median())
            # Ensure calibrator uses exactly the same feature columns
            X_c_clean = X_c_clean[self.feature_columns]
            
            calibrator = CalibratedClassifierCV(
                estimator=self.classifier, 
                method="isotonic", 
                cv=None,
                ensemble=False
            )
            calibrator.fit(X_c_clean, y_calib_podium)
            self.classifier = calibrator # Overwrite with the calibrated model

        # ── Head B: LightGBM regressor ──────────────────────────────
        if optimize and optuna is not None:
            best_params_reg = self._optimize_regressor(X_clean, y_position)
        else:
            best_params_reg = {
                "max_depth": 8,
                "learning_rate": 0.05,
                "n_estimators": 400,
                "subsample": 0.8,
                "colsample_bytree": 0.8,
                "min_child_samples": 10,
                "reg_alpha": 0.1,
                "reg_lambda": 1.0,
            }

        self.regressor = lgb.LGBMRegressor(
            **best_params_reg,
            objective="regression",
            metric="mae",
            random_state=settings.random_seed,
            verbose=-1,
        )
        # Filter out NaN positions for regressor training
        mask = y_position.notna()
        self.regressor.fit(X_clean[mask], y_position[mask])

        self.is_fitted = True

        # Compute training metrics
        metrics = self._compute_metrics(X_clean, y_podium, y_position)
        logger.info("Training metrics: %s", metrics)
        return metrics

    def _optimize_classifier(
        self, X: pd.DataFrame, y: pd.Series, scale_pos_weight: float
    ) -> dict[str, Any]:
        """Run Optuna to find best XGBoost classifier hyperparameters."""
        def objective(trial: optuna.Trial) -> float:
            params = {
                "max_depth": trial.suggest_int("max_depth", 3, 10),
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
                "n_estimators": trial.suggest_int("n_estimators", 100, 600),
                "subsample": trial.suggest_float("subsample", 0.6, 1.0),
                "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
                "min_child_weight": trial.suggest_int("min_child_weight", 1, 10),
                "reg_alpha": trial.suggest_float("reg_alpha", 1e-3, 10.0, log=True),
                "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 10.0, log=True),
            }

            model = xgb.XGBClassifier(
                **params,
                scale_pos_weight=scale_pos_weight,
                objective="binary:logistic",
                eval_metric="logloss",
                random_state=settings.random_seed,
                use_label_encoder=False,
            )

            # Temporal CV
            tscv = TimeSeriesSplit(n_splits=3)
            scores = []
            for train_idx, val_idx in tscv.split(X):
                model.fit(X.iloc[train_idx], y.iloc[train_idx])
                y_prob = model.predict_proba(X.iloc[val_idx])[:, 1]
                scores.append(roc_auc_score(y.iloc[val_idx], y_prob))

            return np.mean(scores)

        study = optuna.create_study(direction="maximize")
        study.optimize(objective, n_trials=min(settings.optuna_n_trials, 50),
                       show_progress_bar=True)
        logger.info("Best classifier AUC: %.4f", study.best_value)
        return study.best_params

    def _optimize_regressor(self, X: pd.DataFrame, y: pd.Series) -> dict[str, Any]:
        """Run Optuna for LightGBM regressor hyperparameters."""
        mask = y.notna()
        X_r, y_r = X[mask], y[mask]

        def objective(trial: optuna.Trial) -> float:
            params = {
                "max_depth": trial.suggest_int("max_depth", 3, 12),
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
                "n_estimators": trial.suggest_int("n_estimators", 100, 800),
                "subsample": trial.suggest_float("subsample", 0.6, 1.0),
                "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
                "min_child_samples": trial.suggest_int("min_child_samples", 5, 30),
                "reg_alpha": trial.suggest_float("reg_alpha", 1e-3, 10.0, log=True),
                "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 10.0, log=True),
            }

            model = lgb.LGBMRegressor(
                **params, objective="regression", metric="mae",
                random_state=settings.random_seed, verbose=-1,
            )

            tscv = TimeSeriesSplit(n_splits=3)
            scores = []
            for train_idx, val_idx in tscv.split(X_r):
                model.fit(X_r.iloc[train_idx], y_r.iloc[train_idx])
                y_pred = model.predict(X_r.iloc[val_idx])
                mae = np.mean(np.abs(y_r.iloc[val_idx].values - y_pred))
                scores.append(-mae)  # Negative MAE to maximize

            return np.mean(scores)

        study = optuna.create_study(direction="maximize")
        study.optimize(objective, n_trials=min(settings.optuna_n_trials, 50),
                       show_progress_bar=True)
        logger.info("Best regressor MAE: %.4f", -study.best_value)
        return study.best_params

    # ── Prediction ──────────────────────────────────────────────────

    def predict_podium_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Predict podium probability per driver.

        Returns:
            Array of shape (n_drivers,) with P(podium).
        """
        assert self.is_fitted, "Model not fitted"
        X_clean = X[self.feature_columns].fillna(X[self.feature_columns].median())
        return self.classifier.predict_proba(X_clean)[:, 1]

    def predict_position(self, X: pd.DataFrame) -> np.ndarray:
        """Predict finish position per driver.

        Returns:
            Array of shape (n_drivers,) with predicted position.
        """
        assert self.is_fitted, "Model not fitted"
        X_clean = X[self.feature_columns].fillna(X[self.feature_columns].median())
        return self.regressor.predict(X_clean)

    # ── Metrics ─────────────────────────────────────────────────────

    def _compute_metrics(
        self, X: pd.DataFrame, y_podium: pd.Series, y_position: pd.Series
    ) -> dict[str, float]:
        """Compute training-set metrics for both heads."""
        y_prob = self.predict_podium_proba(X)
        y_pred = (y_prob >= 0.5).astype(int)

        metrics = {
            "classifier_accuracy": accuracy_score(y_podium, y_pred),
            "classifier_precision": precision_score(y_podium, y_pred, zero_division=0),
            "classifier_recall": recall_score(y_podium, y_pred, zero_division=0),
            "classifier_f1": f1_score(y_podium, y_pred, zero_division=0),
            "classifier_auc": roc_auc_score(y_podium, y_prob),
            "classifier_log_loss": log_loss(y_podium, y_prob),
        }

        mask = y_position.notna()
        if mask.sum() > 0:
            pos_pred = self.predict_position(X[mask])
            metrics["regressor_mae"] = np.mean(np.abs(y_position[mask].values - pos_pred))

        return metrics

    # ── Feature importance ──────────────────────────────────────────

    def get_feature_importance(self, top_n: int = 15) -> pd.DataFrame:
        """Get feature importance from the classifier."""
        assert self.is_fitted, "Model not fitted"
        
        # If classifier is wrapped in CalibratedClassifierCV, extract base estimator
        base_clf = self.classifier
        if hasattr(self.classifier, "calibrated_classifiers_"):
            base_clf = self.classifier.calibrated_classifiers_[0].estimator
            
        importance = base_clf.feature_importances_
        df = pd.DataFrame({
            "feature": self.feature_columns,
            "importance": importance,
        }).sort_values("importance", ascending=False)
        return df.head(top_n)

    # ── Persistence ─────────────────────────────────────────────────

    def save(self, path: Path | None = None) -> Path:
        """Save the model to disk."""
        if path is None:
            path = settings.abs_model_dir / "stage1_prerace.joblib"
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)
        logger.info("Saved PreRacePredictor to %s", path)
        return path

    @classmethod
    def load(cls, path: Path | None = None) -> "PreRacePredictor":
        """Load a saved model from disk."""
        if path is None:
            path = settings.abs_model_dir / "stage1_prerace.joblib"
        model = joblib.load(path)
        logger.info("Loaded PreRacePredictor from %s", path)
        return model
