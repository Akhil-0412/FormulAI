"""Feature store — build, cache, and serve feature matrices."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import pandas as pd

from config.settings import settings
from features.pre_race import build_full_training_set

logger = logging.getLogger(__name__)

_FEATURE_CACHE_DIR = settings.project_root / "data" / "feature_cache"


def get_training_features(
    start_year: int = 2018,
    end_year: int = 2024,
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
    key = f"prerace_{start_year}_{end_year}"
    return _FEATURE_CACHE_DIR / f"{key}.parquet"


def get_feature_columns(df: pd.DataFrame) -> list[str]:
    """Return the list of feature columns (excludes meta and target columns)."""
    meta_cols = {"driver_id", "race_id", "is_podium", "finish_position"}
    return [c for c in df.columns if c not in meta_cols]


def get_X_y(
    df: pd.DataFrame,
    target: str = "is_podium",
) -> tuple[pd.DataFrame, pd.Series]:
    """Split a feature DataFrame into X (features) and y (target).

    Args:
        df: Feature matrix from build_pre_race_features.
        target: Target column name ("is_podium" or "finish_position").

    Returns:
        (X, y) — features DataFrame and target Series.
    """
    feature_cols = get_feature_columns(df)
    X = df[feature_cols].copy()
    y = df[target].copy()
    return X, y
