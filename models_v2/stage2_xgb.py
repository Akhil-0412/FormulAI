import logging
import joblib
from pathlib import Path
import numpy as np
import pandas as pd
from xgboost import XGBRegressor
from config.settings import settings

logger = logging.getLogger(__name__)

class Stage2XGB:
    def __init__(self):
        self.model = XGBRegressor(
            n_estimators=100,
            learning_rate=0.05,
            max_depth=4,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            enable_categorical=True
        )
        self.feature_columns = []
        self.is_fitted = False

    def fit(self, X_train: pd.DataFrame, y_train: pd.Series, X_valid: pd.DataFrame = None, y_valid: pd.Series = None):
        # Convert objects/strings to category
        for col in X_train.select_dtypes(include=["object", "string"]).columns:
            X_train[col] = X_train[col].astype("category")
            if X_valid is not None:
                X_valid[col] = X_valid[col].astype("category")
                
        self.feature_columns = list(X_train.columns)
        
        eval_set = None
        if X_valid is not None and y_valid is not None:
            eval_set = [(X_valid, y_valid)]
            
        self.model.fit(
            X_train, y_train,
            eval_set=eval_set,
            verbose=False
        )
        self.is_fitted = True

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        assert self.is_fitted, "Model must be fitted first"
        X_subset = X[self.feature_columns].copy()
        
        for col in X_subset.select_dtypes(include=["object", "string"]).columns:
            X_subset[col] = X_subset[col].astype("category")
        
        # Fill missing values for numericals
        num_cols = X_subset.select_dtypes(include=["number"]).columns
        if len(num_cols) > 0:
            X_subset[num_cols] = X_subset[num_cols].fillna(X_subset[num_cols].median()).fillna(0)
            
        return self.model.predict(X_subset)

    def save(self, path: Path | None = None):
        if path is None:
            path = settings.abs_model_dir / "stage2_xgb.joblib"
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)
        logger.info(f"Saved Meta-Learner (XGB) to {path}")

    @classmethod
    def load(cls, path: Path | None = None) -> 'Stage2XGB':
        if path is None:
            path = settings.abs_model_dir / "stage2_xgb.joblib"
        return joblib.load(path)
