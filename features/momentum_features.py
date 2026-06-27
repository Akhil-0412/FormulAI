"""Momentum and trend features for F1 drivers.

Captures dynamic performance trajectories:
- Position trend (improving/declining)
- Podium/points streaks
- Grid vs finish delta trends
- Points efficiency
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from data.db import query_df

logger = logging.getLogger(__name__)


def compute_momentum_features(driver_id: str, race_id: str) -> dict:
    """Compute momentum and trend features for a driver.

    All features are computed using only data strictly BEFORE race_id
    to prevent temporal leakage.
    """
    features: dict = {}

    # Get last 5 race results
    recent = query_df(
        """SELECT r.race_id, res.position, res.grid, res.is_podium, res.points, res.status
           FROM results res
           JOIN races r ON res.race_id = r.race_id
           WHERE res.driver_id = ? AND r.race_id < ?
             AND res.position IS NOT NULL
           ORDER BY r.year DESC, r.round DESC
           LIMIT 5""",
        (driver_id, race_id),
    )

    if recent.empty:
        features["position_trend_3r"] = 0.0
        features["podium_streak"] = 0
        features["points_per_race_last5"] = 0.0
        features["grid_vs_finish_trend_3r"] = 0.0
        features["consistency_std_3r"] = 10.0
        features["points_finish_ratio"] = 0.0
        features["win_rate_last5"] = 0.0
        features["top5_rate_last5"] = 0.0
        features["top10_rate_last5"] = 0.0
        return features

    positions = recent["position"].values
    grids = recent["grid"].values
    points = recent["points"].values
    podiums = recent["is_podium"].values

    # ── Position Trend (slope of last 3 positions) ─────────────────
    # Negative slope = improving (positions getting lower = better)
    if len(positions) >= 3:
        last3 = positions[:3]  # Most recent 3
        x = np.arange(len(last3))
        # Fit linear regression: position = slope * race_index + intercept
        slope = np.polyfit(x, last3, 1)[0] if len(set(last3)) > 1 else 0.0
        features["position_trend_3r"] = float(slope)
    else:
        features["position_trend_3r"] = 0.0

    # ── Podium Streak ──────────────────────────────────────────────
    streak = 0
    for p in podiums:
        if p == 1:
            streak += 1
        else:
            break
    features["podium_streak"] = streak

    # ── Points Per Race (last 5) ───────────────────────────────────
    features["points_per_race_last5"] = float(points.mean())

    # ── Grid vs Finish Delta Trend ─────────────────────────────────
    # Positive = consistently finishing better than starting
    if len(positions) >= 3:
        deltas = grids[:3] - positions[:3]  # Positive = gained positions
        x = np.arange(len(deltas))
        slope = np.polyfit(x, deltas, 1)[0] if len(set(deltas)) > 1 else 0.0
        features["grid_vs_finish_trend_3r"] = float(slope)
    else:
        features["grid_vs_finish_trend_3r"] = 0.0

    # ── Consistency (std of last 3 positions) ──────────────────────
    if len(positions) >= 3:
        features["consistency_std_3r"] = float(np.std(positions[:3]))
    else:
        features["consistency_std_3r"] = float(np.std(positions)) if len(positions) > 1 else 10.0

    # ── Points/Finish Ratio ────────────────────────────────────────
    # How efficient is the driver at converting finishes to points?
    total_pts = float(points.sum())
    features["points_finish_ratio"] = total_pts / len(points) if len(points) > 0 else 0.0

    # ── Rate Features ──────────────────────────────────────────────
    features["win_rate_last5"] = float((positions == 1).mean())
    features["top5_rate_last5"] = float((positions <= 5).mean())
    features["top10_rate_last5"] = float((positions <= 10).mean())

    return features
