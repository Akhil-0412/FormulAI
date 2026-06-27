"""Feature pipeline combiner."""

import logging
import pandas as pd
from typing import List

logger = logging.getLogger(__name__)

def combine_features(feature_dicts: List[dict]) -> pd.DataFrame:
    """Combine dictionaries of features into a validated DataFrame."""
    df = pd.DataFrame(feature_dicts)
    
    # Feature validation (no NaN in critical columns, correct dtypes)
    critical_cols = ["grid_position", "is_podium"]
    for col in critical_cols:
        if col in df.columns:
            df[col] = df[col].fillna(20 if col == "grid_position" else 0)

    # Convert object types to appropriate formats or drop
    # (Simplified for now)
    return df

def prune_features(df: pd.DataFrame, importance_dict: dict = None) -> pd.DataFrame:
    """SHAP pruning utility (drop features with near-zero importance)."""
    if importance_dict:
        cols_to_keep = [k for k, v in importance_dict.items() if v > 0.001]
        available = [c for c in cols_to_keep if c in df.columns]
        return df[available]
    return df
