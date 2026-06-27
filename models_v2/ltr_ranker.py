"""Learning-to-Rank model — XGBoost LambdaMART + LightGBM Ranker ensemble.

Core model for FormulAI v3. Replaces binary classification with
ranking-based prediction that directly optimizes for correct ordering
of the full grid, with emphasis on podium positions via NDCG@3.

The F1 points system is used as relevance labels:
  P1=25, P2=18, P3=15, P4=12, ... P10=1, rest=0

This forces the ranker to prioritize podium discrimination over
midfield shuffling.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

try:
    import xgboost as xgb
except ImportError:
    xgb = None

try:
    import lightgbm as lgb
except ImportError:
    lgb = None

try:
    import optuna
except ImportError:
    optuna = None

from config.settings import settings

logger = logging.getLogger(__name__)


class F1LTRRanker:
    """Learning-to-Rank ensemble for F1 grid prediction.

    Uses XGBoost LambdaMART + LightGBM LambdaRank with weighted
    score blending. Softmax converts ranking scores to calibrated
    podium probabilities.
    """

    def __init__(
        self,
        xgb_params: dict | None = None,
        lgb_params: dict | None = None,
        blend_weight_xgb: float = 0.5,
        softmax_temperature: float = 3.0,
    ):
        self.xgb_params = xgb_params or {
            "objective": "rank:ndcg",
            "tree_method": "hist",
            "lambdarank_num_pair_per_sample": 8,
            "lambdarank_pair_method": "topk",
            "max_depth": 6,
            "learning_rate": 0.05,
            "n_estimators": 500,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "min_child_weight": 3,
            "reg_alpha": 0.1,
            "reg_lambda": 1.0,
            "random_state": 42,
            "verbosity": 0,
        }
        self.lgb_params = lgb_params or {
            "objective": "lambdarank",
            "metric": "ndcg",
            "ndcg_eval_at": [3, 5],
            "n_estimators": 500,
            "max_depth": 6,
            "learning_rate": 0.05,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "min_child_samples": 10,
            "reg_alpha": 0.1,
            "reg_lambda": 1.0,
            "random_state": 42,
            "verbosity": -1,
        }
        self.blend_weight_xgb = blend_weight_xgb
        self.softmax_temperature = softmax_temperature

        self.xgb_model: xgb.XGBRanker | None = None
        self.lgb_model: lgb.LGBMRanker | None = None
        self.feature_columns: list[str] = []
        self.is_fitted = False
        self.metadata: dict[str, Any] = {}

    def fit(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        group_train: np.ndarray,
        X_val: pd.DataFrame | None = None,
        y_val: pd.Series | None = None,
        group_val: np.ndarray | None = None,
        optimize: bool = False,
        n_trials: int = 30,
    ) -> dict[str, float]:
        """Train both rankers on the LTR data.

        Args:
            X_train: Feature matrix.
            y_train: Relevance labels (F1 points).
            group_train: Array of group sizes (drivers per race).
            X_val: Optional validation features.
            y_val: Optional validation labels.
            group_val: Optional validation group sizes.
            optimize: Whether to run Optuna hyperparameter search.
            n_trials: Number of Optuna trials.

        Returns:
            Dict of training metrics.
        """
        start_time = time.time()
        self.feature_columns = list(X_train.columns)

        # Clean data
        X_train_clean = self._clean_features(X_train)
        y_train_clean = y_train.fillna(0).astype(float)

        X_val_clean = self._clean_features(X_val) if X_val is not None else None
        y_val_clean = y_val.fillna(0).astype(float) if y_val is not None else None

        if optimize and optuna is not None:
            logger.info("Running Optuna optimization (%d trials)...", n_trials)
            self._optimize_hyperparams(
                X_train_clean, y_train_clean, group_train,
                X_val_clean, y_val_clean, group_val,
                n_trials=n_trials,
            )

        # ── Train XGBoost Ranker ──────────────────────────────────────
        logger.info("Training XGBoost LambdaMART ranker...")
        xgb_params = {k: v for k, v in self.xgb_params.items()}
        n_estimators = xgb_params.pop("n_estimators", 500)
        random_state = xgb_params.pop("random_state", 42)

        self.xgb_model = xgb.XGBRanker(
            n_estimators=n_estimators,
            random_state=random_state,
            **xgb_params,
        )

        eval_qid = None
        eval_set_xgb = None
        if X_val_clean is not None and y_val_clean is not None and group_val is not None:
            eval_set_xgb = [(X_val_clean, y_val_clean)]
            eval_qid = [self._groups_to_qid(group_val)]

        self.xgb_model.fit(
            X_train_clean, y_train_clean,
            qid=self._groups_to_qid(group_train),
            eval_set=eval_set_xgb,
            eval_qid=eval_qid,
            verbose=False,
        )

        # ── Train LightGBM Ranker ─────────────────────────────────────
        logger.info("Training LightGBM LambdaRank ranker...")
        lgb_params = {k: v for k, v in self.lgb_params.items()}
        n_est_lgb = lgb_params.pop("n_estimators", 500)

        self.lgb_model = lgb.LGBMRanker(
            n_estimators=n_est_lgb,
            **lgb_params,
        )

        eval_set_lgb = None
        eval_group_lgb = None
        eval_name_lgb = None
        if X_val_clean is not None and y_val_clean is not None and group_val is not None:
            eval_set_lgb = [(X_val_clean, y_val_clean)]
            eval_group_lgb = [group_val.tolist()]
            eval_name_lgb = ["valid"]

        callbacks = [lgb.log_evaluation(period=0)]

        self.lgb_model.fit(
            X_train_clean, y_train_clean,
            group=group_train.tolist(),
            eval_set=eval_set_lgb,
            eval_group=eval_group_lgb,
            eval_names=eval_name_lgb,
            callbacks=callbacks,
        )

        self.is_fitted = True
        duration = time.time() - start_time

        self.metadata = {
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "train_duration_sec": round(duration, 2),
            "train_size": len(X_train),
            "n_features": len(self.feature_columns),
            "n_groups": len(group_train),
            "blend_weight_xgb": self.blend_weight_xgb,
            "softmax_temperature": self.softmax_temperature,
            "optimized": optimize,
        }

        logger.info(
            "LTR training completed in %.1fs (%d samples, %d groups)",
            duration, len(X_train), len(group_train),
        )

        return {"train_duration": duration}

    def predict_scores(self, X: pd.DataFrame) -> np.ndarray:
        """Predict raw ranking scores (higher = better predicted finish).

        Args:
            X: Feature matrix.

        Returns:
            1D array of ranking scores.
        """
        assert self.is_fitted, "Model not fitted"
        X_clean = self._clean_features(X)

        xgb_scores = self.xgb_model.predict(X_clean)
        lgb_scores = self.lgb_model.predict(X_clean)

        # Normalize to same scale before blending
        xgb_norm = self._normalize_scores(xgb_scores)
        lgb_norm = self._normalize_scores(lgb_scores)

        blended = (
            self.blend_weight_xgb * xgb_norm
            + (1 - self.blend_weight_xgb) * lgb_norm
        )
        return blended

    def predict_race(
        self,
        X: pd.DataFrame,
        driver_ids: list[str],
    ) -> dict[str, float]:
        """Predict podium probabilities for a single race.

        Converts ranking scores to probabilities via softmax
        with tunable temperature.

        Args:
            X: Feature matrix for all drivers in ONE race.
            driver_ids: List of driver IDs corresponding to X rows.

        Returns:
            Dict of {driver_id: P(podium)} sorted by probability.
        """
        scores = self.predict_scores(X)

        # Softmax with temperature
        scaled = scores / max(self.softmax_temperature, 0.1)
        scaled = scaled - np.max(scaled)  # Numerical stability
        exp_vals = np.exp(scaled)
        probs = exp_vals / np.sum(exp_vals)

        # Build sorted dict
        prob_dict = {d: float(p) for d, p in zip(driver_ids, probs)}
        return dict(sorted(prob_dict.items(), key=lambda x: x[1], reverse=True))

    def _clean_features(self, X: pd.DataFrame) -> pd.DataFrame:
        """Ensure features are numeric and handle missing values."""
        if X is None:
            return None

        X_subset = X[self.feature_columns].copy() if self.feature_columns else X.copy()

        # Drop non-numeric columns
        for col in X_subset.columns:
            if X_subset[col].dtype == object:
                X_subset = X_subset.drop(columns=[col])

        # Fill NaN
        numeric_cols = X_subset.select_dtypes(include=["number"]).columns
        if len(numeric_cols) > 0:
            X_subset[numeric_cols] = X_subset[numeric_cols].fillna(
                X_subset[numeric_cols].median()
            ).fillna(0)

        return X_subset

    def _normalize_scores(self, scores: np.ndarray) -> np.ndarray:
        """Min-max normalize scores to [0, 1]."""
        s_min, s_max = scores.min(), scores.max()
        if s_max - s_min < 1e-9:
            return np.ones_like(scores) * 0.5
        return (scores - s_min) / (s_max - s_min)

    @staticmethod
    def _groups_to_qid(group_sizes: np.ndarray) -> np.ndarray:
        """Convert group sizes array to per-sample query IDs for XGBoost."""
        qids = []
        for i, size in enumerate(group_sizes):
            qids.extend([i] * int(size))
        return np.array(qids)

    def _optimize_hyperparams(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        group_train: np.ndarray,
        X_val: pd.DataFrame | None,
        y_val: pd.Series | None,
        group_val: np.ndarray | None,
        n_trials: int = 30,
    ) -> None:
        """Optimize hyperparameters using Optuna."""
        if X_val is None or y_val is None or group_val is None:
            logger.warning("No validation data for optimization, skipping")
            return

        def objective(trial: optuna.Trial) -> float:
            # XGBoost params
            xgb_p = {
                "objective": "rank:ndcg",
                "tree_method": "hist",
                "lambdarank_num_pair_per_sample": trial.suggest_int("xgb_npair", 4, 16),
                "lambdarank_pair_method": "topk",
                "max_depth": trial.suggest_int("xgb_max_depth", 3, 8),
                "learning_rate": trial.suggest_float("xgb_lr", 0.01, 0.2, log=True),
                "n_estimators": trial.suggest_int("xgb_n_est", 100, 800),
                "subsample": trial.suggest_float("xgb_subsample", 0.6, 1.0),
                "colsample_bytree": trial.suggest_float("xgb_colsample", 0.5, 1.0),
                "min_child_weight": trial.suggest_int("xgb_mcw", 1, 10),
                "reg_alpha": trial.suggest_float("xgb_alpha", 1e-3, 10.0, log=True),
                "reg_lambda": trial.suggest_float("xgb_lambda", 1e-3, 10.0, log=True),
                "random_state": 42,
                "verbosity": 0,
            }

            # LightGBM params
            lgb_p = {
                "objective": "lambdarank",
                "metric": "ndcg",
                "ndcg_eval_at": [3, 5],
                "n_estimators": trial.suggest_int("lgb_n_est", 100, 800),
                "max_depth": trial.suggest_int("lgb_max_depth", 3, 8),
                "learning_rate": trial.suggest_float("lgb_lr", 0.01, 0.2, log=True),
                "subsample": trial.suggest_float("lgb_subsample", 0.6, 1.0),
                "colsample_bytree": trial.suggest_float("lgb_colsample", 0.5, 1.0),
                "min_child_samples": trial.suggest_int("lgb_mcs", 5, 30),
                "reg_alpha": trial.suggest_float("lgb_alpha", 1e-3, 10.0, log=True),
                "reg_lambda": trial.suggest_float("lgb_lambda", 1e-3, 10.0, log=True),
                "random_state": 42,
                "verbosity": -1,
            }

            blend_w = trial.suggest_float("blend_weight_xgb", 0.2, 0.8)
            temperature = trial.suggest_float("softmax_temp", 1.0, 10.0)

            # Train XGBoost
            xgb_n_est = xgb_p.pop("n_estimators")
            xgb_model = xgb.XGBRanker(n_estimators=xgb_n_est, **xgb_p)
            xgb_model.fit(
                X_train, y_train,
                qid=self._groups_to_qid(group_train),
                eval_set=[(X_val, y_val)],
                verbose=False,
            )

            # Train LightGBM
            lgb_n_est = lgb_p.pop("n_estimators")
            lgb_model = lgb.LGBMRanker(n_estimators=lgb_n_est, **lgb_p)
            callbacks_lgb = [lgb.log_evaluation(period=0)]
            lgb_model.fit(
                X_train, y_train,
                group=group_train.tolist(),
                eval_set=[(X_val, y_val)],
                eval_group=[group_val.tolist()],
                eval_names=["valid"],
                callbacks=callbacks_lgb,
            )

            # Evaluate on validation
            xgb_scores = self._normalize_scores(xgb_model.predict(X_val))
            lgb_scores = self._normalize_scores(lgb_model.predict(X_val))
            blended = blend_w * xgb_scores + (1 - blend_w) * lgb_scores

            # Compute NDCG@3 manually
            ndcg = self._compute_ndcg_at_k(
                blended, y_val.values, group_val, k=3
            )

            return ndcg

        study = optuna.create_study(direction="maximize")
        optuna.logging.set_verbosity(optuna.logging.WARNING)
        study.optimize(objective, n_trials=n_trials, timeout=600)

        # Apply best params
        best = study.best_params
        logger.info("Best Optuna params (NDCG@3=%.4f): %s", study.best_value, best)

        self.xgb_params.update({
            "lambdarank_num_pair_per_sample": best.get("xgb_npair", 8),
            "max_depth": best.get("xgb_max_depth", 6),
            "learning_rate": best.get("xgb_lr", 0.05),
            "n_estimators": best.get("xgb_n_est", 500),
            "subsample": best.get("xgb_subsample", 0.8),
            "colsample_bytree": best.get("xgb_colsample", 0.8),
            "min_child_weight": best.get("xgb_mcw", 3),
            "reg_alpha": best.get("xgb_alpha", 0.1),
            "reg_lambda": best.get("xgb_lambda", 1.0),
        })
        self.lgb_params.update({
            "n_estimators": best.get("lgb_n_est", 500),
            "max_depth": best.get("lgb_max_depth", 6),
            "learning_rate": best.get("lgb_lr", 0.05),
            "subsample": best.get("lgb_subsample", 0.8),
            "colsample_bytree": best.get("lgb_colsample", 0.8),
            "min_child_samples": best.get("lgb_mcs", 10),
            "reg_alpha": best.get("lgb_alpha", 0.1),
            "reg_lambda": best.get("lgb_lambda", 1.0),
        })
        self.blend_weight_xgb = best.get("blend_weight_xgb", 0.5)
        self.softmax_temperature = best.get("softmax_temp", 3.0)

    @staticmethod
    def _compute_ndcg_at_k(
        scores: np.ndarray,
        relevance: np.ndarray,
        group_sizes: np.ndarray,
        k: int = 3,
    ) -> float:
        """Compute NDCG@k across all groups."""
        ndcg_values = []
        offset = 0

        for size in group_sizes:
            size = int(size)
            group_scores = scores[offset:offset + size]
            group_rel = relevance[offset:offset + size]

            # Predicted order
            pred_order = np.argsort(-group_scores)[:k]
            pred_rel = group_rel[pred_order]

            # Ideal order
            ideal_order = np.argsort(-group_rel)[:k]
            ideal_rel = group_rel[ideal_order]

            # DCG
            positions = np.arange(1, len(pred_rel) + 1)
            dcg = np.sum(pred_rel / np.log2(positions + 1))

            # IDCG
            ideal_positions = np.arange(1, len(ideal_rel) + 1)
            idcg = np.sum(ideal_rel / np.log2(ideal_positions + 1))

            if idcg > 0:
                ndcg_values.append(dcg / idcg)

            offset += size

        return float(np.mean(ndcg_values)) if ndcg_values else 0.0

    def save(self, path: Path | None = None) -> Path:
        """Save the entire ranker to disk."""
        if path is None:
            path = settings.abs_model_dir / "ltr_ranker.joblib"
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)
        logger.info("Saved F1LTRRanker to %s", path)
        return path

    @classmethod
    def load(cls, path: Path | None = None) -> "F1LTRRanker":
        """Load a saved ranker."""
        if path is None:
            path = settings.abs_model_dir / "ltr_ranker.joblib"
        model = joblib.load(path)
        logger.info("Loaded F1LTRRanker from %s", path)
        return model
