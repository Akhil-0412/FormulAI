"""Pace Head — Predicts race pace relative to field average."""

import xgboost as xgb
import pandas as pd
from typing import Any

class PaceHead:
    def __init__(self, params: dict[str, Any] | None = None):
        if params is None:
            params = {
                "max_depth": 6,
                "learning_rate": 0.05,
                "n_estimators": 250,
                "objective": "reg:squarederror",
                "enable_categorical": True,
                "device": "cuda"
            }
        self.model = xgb.XGBRegressor(**params)
        self.is_fitted = False
        self.feature_columns = []

    def fit(self, X: pd.DataFrame, y_pace: pd.Series):
        self.feature_columns = list(X.columns)
        self.model.fit(X, y_pace)
        self.is_fitted = True

    def predict_pace_delta(self, X: pd.DataFrame) -> pd.Series:
        if not self.is_fitted:
            raise ValueError("Model not fitted")
        return pd.Series(self.model.predict(X[self.feature_columns]), index=X.index)
