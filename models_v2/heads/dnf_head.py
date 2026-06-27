"""DNF Head — Predicts P(DNF) before the race using XGBoost."""

import xgboost as xgb
import pandas as pd
from typing import Any

class DNFHead:
    def __init__(self, params: dict[str, Any] | None = None):
        if params is None:
            params = {
                "max_depth": 4,
                "learning_rate": 0.05,
                "n_estimators": 200,
                "objective": "binary:logistic",
                "eval_metric": "logloss",
                "enable_categorical": True,
                "device": "cuda"
            }
        self.model = xgb.XGBClassifier(**params)
        self.is_fitted = False
        self.feature_columns = []

    def fit(self, X: pd.DataFrame, y: pd.Series):
        self.feature_columns = list(X.columns)
        self.model.fit(X, y)
        self.is_fitted = True

    def predict_proba(self, X: pd.DataFrame) -> pd.Series:
        if not self.is_fitted:
            raise ValueError("Model not fitted")
        return pd.Series(self.model.predict_proba(X[self.feature_columns])[:, 1], index=X.index)
