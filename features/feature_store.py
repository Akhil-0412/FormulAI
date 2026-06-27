"""Feature store — build, cache, and serve feature matrices."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from config.settings import settings
from features.pre_race import build_full_training_set

logger = logging.getLogger(__name__)

_FEATURE_CACHE_DIR = settings.project_root / "data" / "feature_cache"

# Columns that are NOT features (meta/target columns)
_META_COLS = {
    "driver_id", "race_id", "constructor_id",
    "is_podium", "finish_position", "relevance",
    "is_dnf", "points_scored", "status",
}

# Columns with string values that need to be dropped for numeric models
_STRING_FEATURE_COLS = {"quali_compound"}


def get_training_features(
    start_year: int = 2014,
    end_year: int = 2026,
    force_rebuild: bool = False,
) -> pd.DataFrame:
    """Get the full training feature matrix, using cache if available.

    Args:
        start_year: First season to include.
        end_year: Last season to include.
        force_rebuild: If True, rebuild even if cache exists.

    Returns:
        DataFrame with all pre-race features + labels.
    """
    cache_path = _cache_path(start_year, end_year)

    if not force_rebuild and cache_path.exists():
        logger.info("Loading cached features from %s", cache_path)
        return pd.read_parquet(cache_path)

    logger.info("Building training features for %d–%d...", start_year, end_year)
    df = build_full_training_set(start_year, end_year)

    if not df.empty:
        _FEATURE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        df.to_parquet(cache_path, index=False)
        logger.info("Cached %d rows to %s", len(df), cache_path)

    return df


def _cache_path(start_year: int, end_year: int) -> Path:
    """Generate a cache file path for a year range."""
    key = f"prerace_v3_{start_year}_{end_year}"
    return _FEATURE_CACHE_DIR / f"{key}.parquet"


def get_feature_columns(df: pd.DataFrame) -> list[str]:
    """Return the list of feature columns (excludes meta, target, and string columns)."""
    return [
        c for c in df.columns
        if c not in _META_COLS and c not in _STRING_FEATURE_COLS
    ]


def get_X_y(
    df: pd.DataFrame,
    target: str = "is_podium",
) -> tuple[pd.DataFrame, pd.Series]:
    """Split a feature DataFrame into X (features) and y (target).

    Args:
        df: Feature matrix from build_pre_race_features.
        target: Target column name ("is_podium", "finish_position", "relevance", "is_dnf").

    Returns:
        (X, y) — features DataFrame and target Series.
    """
    feature_cols = get_feature_columns(df)
    X = df[feature_cols].copy()

    # Drop any remaining non-numeric columns
    for col in X.columns:
        if X[col].dtype == object:
            X = X.drop(columns=[col])

    y = df[target].copy()
    return X, y


def get_X_y_grouped(
    df: pd.DataFrame,
    target: str = "relevance",
) -> tuple[pd.DataFrame, pd.Series, np.ndarray, list[str]]:
    """Split into X, y, group_sizes for Learning-to-Rank.

    The data is grouped by race_id. Each group represents one race
    with all its drivers. The XGBoost/LightGBM rankers need group_sizes
    to know which rows belong to the same query (race).

    Args:
        df: Full feature DataFrame with race_id column.
        target: Target column (default="relevance" = F1 points).

    Returns:
        (X, y, group_sizes, race_ids) where:
        - X: Feature matrix (numeric only)
        - y: Relevance labels
        - group_sizes: Array of ints, each being the number of drivers in a race
        - race_ids: List of race_ids in order (for debugging)
    """
    # Sort by race_id to ensure groups are contiguous
    df_sorted = df.sort_values("race_id").reset_index(drop=True)

    feature_cols = get_feature_columns(df_sorted)
    X = df_sorted[feature_cols].copy()

    # Drop any remaining non-numeric columns
    for col in X.columns:
        if X[col].dtype == object:
            X = X.drop(columns=[col])

    y = df_sorted[target].copy().fillna(0).astype(float)

    # Compute group sizes
    race_groups = df_sorted.groupby("race_id", sort=False)
    group_sizes = race_groups.size().values
    race_ids = list(race_groups.groups.keys())

    return X, y, group_sizes, race_ids
