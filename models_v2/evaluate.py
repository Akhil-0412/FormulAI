"""Evaluation metrics for LTR-based F1 prediction.

Includes standard race-level metrics plus LTR-specific:
- NDCG@3: Ranking quality for podium positions
- Kendall's Tau: Full grid rank correlation
- Top-3 Precision: Fraction of predicted top-3 that are actual top-3
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from scipy.stats import kendalltau
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score

from features.feature_store import get_X_y, get_feature_columns
from models_v2.ltr_ranker import F1LTRRanker
from models_v2.stage3_ensemble import enforce_podium_constraints

logger = logging.getLogger(__name__)


def evaluate_race(
    model: F1LTRRanker,
    race_df: pd.DataFrame,
) -> dict:
    """Evaluate LTR model predictions against actual results for a single race.

    Args:
        model: Fitted F1LTRRanker.
        race_df: Feature DataFrame for one race.

    Returns:
        Dict of metrics for this race.
    """
    driver_ids = race_df["driver_id"].tolist()

    # Get features
    feature_cols = [
        c for c in model.feature_columns
        if c in race_df.columns
    ]
    X = race_df[feature_cols].copy()
    for col in X.columns:
        if X[col].dtype == object:
            X = X.drop(columns=[col])
    numeric_cols = X.select_dtypes(include=["number"]).columns
    X[numeric_cols] = X[numeric_cols].fillna(X[numeric_cols].median()).fillna(0)

    # Get ranking scores and convert to podium probabilities
    prob_dict = model.predict_race(X, driver_ids)

    # Build position prediction dict (use negative scores for enforce_podium_constraints)
    scores = model.predict_scores(X)
    pos_dict = {d: -float(s) for d, s in zip(driver_ids, scores)}  # Lower = better position

    # Enforce constraints
    result = enforce_podium_constraints(prob_dict, pos_dict)
    predicted_podium_ordered = [p.driver_id for p in result.podium]
    predicted_podium_set = set(predicted_podium_ordered)

    # Actual podium
    y_podium = race_df["is_podium"]
    actual_podium_mask = y_podium == 1
    actual_df = race_df[actual_podium_mask].sort_values("finish_position")
    actual_podium_ordered = actual_df["driver_id"].tolist()
    actual_podium_set = set(actual_podium_ordered)

    # ── Race-level metrics ──────────────────────────────────────────
    correct = predicted_podium_set & actual_podium_set
    n_correct = len(correct)

    # Podium probabilities for binary metrics
    podium_probs = np.array([prob_dict.get(d, 0.0) for d in driver_ids])

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

    # ── Binary classification metrics ──────────────────────────────
    try:
        metrics["auc_roc"] = roc_auc_score(y_podium, podium_probs)
    except ValueError:
        metrics["auc_roc"] = None

    try:
        metrics["log_loss"] = log_loss(y_podium, np.clip(podium_probs, 1e-7, 1 - 1e-7))
    except ValueError:
        metrics["log_loss"] = None

    try:
        metrics["brier_score"] = brier_score_loss(y_podium, podium_probs)
    except ValueError:
        metrics["brier_score"] = None

    # ── LTR-specific metrics ───────────────────────────────────────
    # NDCG@3
    y_relevance = race_df["relevance"].values if "relevance" in race_df.columns else y_podium.values
    pred_order = np.argsort(-scores)[:3]
    ideal_order = np.argsort(-y_relevance)[:3]

    pred_rel = y_relevance[pred_order]
    ideal_rel = y_relevance[ideal_order]

    positions = np.arange(1, len(pred_rel) + 1)
    dcg = np.sum(pred_rel / np.log2(positions + 1))
    idcg = np.sum(ideal_rel / np.log2(np.arange(1, len(ideal_rel) + 1) + 1))
    metrics["ndcg_at_3"] = float(dcg / idcg) if idcg > 0 else 0.0

    # Kendall's Tau (full grid rank correlation)
    actual_positions = pd.to_numeric(race_df["finish_position"], errors="coerce").values
    mask = pd.notna(actual_positions) & (actual_positions > 0)
    if mask.sum() > 3:
        pred_ranks = np.argsort(np.argsort(-scores))  # Convert scores to ranks
        try:
            tau, _ = kendalltau(actual_positions[mask], pred_ranks[mask])
            metrics["kendall_tau"] = float(tau) if not np.isnan(tau) else 0.0
        except Exception:
            metrics["kendall_tau"] = 0.0
    else:
        metrics["kendall_tau"] = 0.0

    # Top-3 Precision
    predicted_top3 = set(np.array(driver_ids)[np.argsort(-scores)[:3]])
    metrics["top3_precision"] = len(predicted_top3 & actual_podium_set) / 3.0

    # Position MAE
    if mask.sum() > 0:
        # Map scores to predicted positions (rank-based)
        pred_positions = np.argsort(np.argsort(-scores)) + 1
        metrics["position_mae"] = float(np.mean(np.abs(
            actual_positions[mask] - pred_positions[mask]
        )))
    else:
        metrics["position_mae"] = None

    return metrics


def evaluate_season(
    model: F1LTRRanker,
    season_df: pd.DataFrame,
) -> pd.DataFrame:
    """Evaluate model across all races in a season."""
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
        avg_ndcg = results["ndcg_at_3"].dropna().mean()
        logger.info("Avg NDCG@3: %.4f", avg_ndcg if avg_ndcg else 0)
        avg_tau = results["kendall_tau"].dropna().mean()
        logger.info("Avg Kendall's Tau: %.4f", avg_tau if avg_tau else 0)
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
        "avg_ndcg_at_3": float(results["ndcg_at_3"].dropna().mean()),
        "avg_kendall_tau": float(results["kendall_tau"].dropna().mean()),
        "avg_position_mae": float(results["position_mae"].dropna().mean()),
        "avg_brier_score": float(results["brier_score"].dropna().mean()),
        "avg_log_loss": float(results["log_loss"].dropna().mean()),
        "avg_top3_precision": float(results["top3_precision"].dropna().mean()),
        "high_confidence_pct": float(
            (results["confidence_level"] == "high").mean() * 100
        ),
    }
