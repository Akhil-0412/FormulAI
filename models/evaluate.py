"""Evaluation metrics and race-level accuracy reporting."""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score

from features.feature_store import get_X_y
from models.stage1_prerace import PreRacePredictor
from models.stage3_ensemble import enforce_podium_constraints

logger = logging.getLogger(__name__)


def evaluate_race(
    model: PreRacePredictor,
    race_df: pd.DataFrame,
) -> dict:
    """Evaluate model predictions against actual results for a single race.

    Args:
        model: Fitted PreRacePredictor.
        race_df: Feature DataFrame for one race (from build_pre_race_features).

    Returns:
        Dict of metrics for this race.
    """
    X, y_podium = get_X_y(race_df, "is_podium")
    y_position = race_df["finish_position"]
    driver_ids = race_df["driver_id"].tolist()

    # Get predictions
    podium_probs = model.predict_podium_proba(X)
    position_preds = model.predict_position(X)

    # Build dicts
    prob_dict = {d: p for d, p in zip(driver_ids, podium_probs)}
    pos_dict = {d: p for d, p in zip(driver_ids, position_preds)}

    # Enforce constraints
    result = enforce_podium_constraints(prob_dict, pos_dict)
    # result.podium is ordered P1, P2, P3
    predicted_podium_ordered = [p.driver_id for p in result.podium]
    predicted_podium_set = set(predicted_podium_ordered)

    # Actual podium
    actual_podium_mask = y_podium == 1
    actual_df = race_df[actual_podium_mask].sort_values("finish_position")
    actual_podium_ordered = actual_df["driver_id"].tolist()
    actual_podium_set = set(actual_podium_ordered)

    # ── Race-level metrics ──────────────────────────────────────────
    correct = predicted_podium_set & actual_podium_set
    n_correct = len(correct)

    metrics = {
        "race_id": race_df["race_id"].iloc[0],
        "predicted_podium": predicted_podium_ordered,
        "actual_podium": actual_podium_ordered,
        "correct_predictions": n_correct,
        "all_3_correct": n_correct == 3,
        "at_least_2_correct": n_correct >= 2,
        "at_least_1_correct": n_correct >= 1,
        "confidence_level": result.confidence_level,
        "margin": result.margin,
        "driver_probs": podium_probs.tolist(),
        "driver_probs_id": driver_ids,
        "driver_actuals": y_podium.tolist(),
    }

    # ── Driver-level metrics ────────────────────────────────────────
    y_pred_binary = (podium_probs >= 0.5).astype(int)

    try:
        metrics["auc_roc"] = roc_auc_score(y_podium, podium_probs)
    except ValueError:
        metrics["auc_roc"] = None

    try:
        metrics["log_loss"] = log_loss(y_podium, podium_probs)
    except ValueError:
        metrics["log_loss"] = None

    try:
        metrics["brier_score"] = brier_score_loss(y_podium, podium_probs)
    except ValueError:
        metrics["brier_score"] = None

    # Position MAE
    mask = y_position.notna()
    if mask.sum() > 0:
        metrics["position_mae"] = float(np.mean(np.abs(
            y_position[mask].values - position_preds[mask.values]
        )))
    else:
        metrics["position_mae"] = None

    return metrics


def evaluate_season(
    model: PreRacePredictor,
    season_df: pd.DataFrame,
) -> pd.DataFrame:
    """Evaluate model across all races in a season.

    Args:
        model: Fitted PreRacePredictor.
        season_df: Feature DataFrame with multiple races.

    Returns:
        DataFrame with one row per race and all metrics.
    """
    races = season_df["race_id"].unique()
    all_metrics = []

    for race_id in sorted(races):
        race_df = season_df[season_df["race_id"] == race_id]
        try:
            metrics = evaluate_race(model, race_df)
            all_metrics.append(metrics)
        except Exception as exc:
            logger.warning("Failed to evaluate %s: %s", race_id, exc)

    results = pd.DataFrame(all_metrics)

    if not results.empty:
        # Summary statistics
        logger.info("=== Season Evaluation Summary ===")
        logger.info("Total races: %d", len(results))
        logger.info("All 3 correct: %d/%d (%.1f%%)",
                     results["all_3_correct"].sum(), len(results),
                     results["all_3_correct"].mean() * 100)
        logger.info("≥2 correct: %d/%d (%.1f%%)",
                     results["at_least_2_correct"].sum(), len(results),
                     results["at_least_2_correct"].mean() * 100)
        logger.info("≥1 correct: %d/%d (%.1f%%)",
                     results["at_least_1_correct"].sum(), len(results),
                     results["at_least_1_correct"].mean() * 100)
        avg_mae = results["position_mae"].dropna().mean()
        logger.info("Avg position MAE: %.2f", avg_mae if avg_mae else 0)

    return results


def evaluation_summary(results: pd.DataFrame) -> dict:
    """Create a summary dict from season evaluation results."""
    if results.empty:
        return {}

    return {
        "total_races": len(results),
        "all_3_correct": int(results["all_3_correct"].sum()),
        "all_3_correct_pct": float(results["all_3_correct"].mean() * 100),
        "at_least_2_correct": int(results["at_least_2_correct"].sum()),
        "at_least_2_pct": float(results["at_least_2_correct"].mean() * 100),
        "at_least_1_correct": int(results["at_least_1_correct"].sum()),
        "at_least_1_pct": float(results["at_least_1_correct"].mean() * 100),
        "avg_position_mae": float(results["position_mae"].dropna().mean()),
        "avg_brier_score": float(results["brier_score"].dropna().mean()),
        "avg_log_loss": float(results["log_loss"].dropna().mean()),
        "high_confidence_pct": float(
            (results["confidence_level"] == "high").mean() * 100
        ),
    }
