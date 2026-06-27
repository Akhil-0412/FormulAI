"""Pit Stop Head — Predicts expected number of pit stops and optimal window."""

import xgboost as xgb
import pandas as pd
from typing import Any

class PitStopHead:
    def __init__(self, params: dict[str, Any] | None = None):
        if params is None:
            params = {
                "max_depth": 5,
                "learning_rate": 0.1,
                "n_estimators": 100,
                "objective": "reg:squarederror",
                "enable_categorical": True,
                "device": "cuda"
            }
        self.model = xgb.XGBRegressor(**params)
        self.is_fitted = False
        self.feature_columns = []

    def fit(self, X: pd.DataFrame, y_stops: pd.Series):
        self.feature_columns = list(X.columns)
        self.model.fit(X, y_stops)
        self.is_fitted = True

    def predict_expected_stops(self, X: pd.DataFrame) -> pd.Series:
        if not self.is_fitted:
            raise ValueError("Model not fitted")
        return pd.Series(self.model.predict(X[self.feature_columns]), index=X.index)
