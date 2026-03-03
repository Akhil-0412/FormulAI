"""Stage 3 — Ensemble + constraint enforcement (exactly 3 podium finishers)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class PodiumPrediction:
    """A single driver's podium prediction."""

    driver_id: int | str
    predicted_position: int  # 1, 2, or 3
    probability: float
    confidence: float


@dataclass
class PodiumResult:
    """Complete podium prediction result."""

    podium: list[PodiumPrediction]  # Exactly 3 drivers
    full_grid: dict[int | str, float]  # All drivers with P(podium)
    confidence_level: Literal["high", "medium", "low"]
    margin: float  # Probability gap between P3 and P4


def enforce_podium_constraints(
    podium_probs: dict[int | str, float],
    position_preds: dict[int | str, float] | None = None,
    confidence_threshold: float = 0.05,
) -> PodiumResult:
    """Enforce exactly 3 podium finishers and rank P1/P2/P3.

    Algorithm (Plackett-Luce / Softmax):
    1. Convert expected finishing positions (Head B) into a probability
       distribution using Softmax over negative position. This enforces
       mutual exclusivity across the grid.
    2. Sort drivers by this coherent ranking score.
    3. Select top 3 as P1/P2/P3.
    """
    if not podium_probs:
        raise ValueError("No driver probabilities provided")

    drivers = list(podium_probs.keys())

    if position_preds:
        # Softmax over negative expected finish position (lower position = better)
        # Temp=3.0 scales the differences smoothly
        temp = 3.0
        neg_pos = np.array([-position_preds.get(d, 10.0) for d in drivers])
        # Prevent overflow
        neg_pos = neg_pos - np.max(neg_pos)
        exp_vals = np.exp(neg_pos / temp)
        weights = exp_vals / np.sum(exp_vals)
        ranking_scores = {d: p for d, p in zip(drivers, weights)}
    else:
        total = sum(podium_probs.values()) + 1e-9
        ranking_scores = {d: p / total for d, p in podium_probs.items()}

    # Sort by the normalized, mutually-exclusive ranking scores
    sorted_drivers = sorted(ranking_scores.items(), key=lambda x: x[1], reverse=True)

    top3 = sorted_drivers[:3]
    rest = sorted_drivers[3:] if len(sorted_drivers) > 3 else []
    
    # Confidence margin: gap in softmax probability between P3 and P4
    p3_score = top3[2][1] if len(top3) >= 3 else 0.0
    p4_score = rest[0][1] if rest else 0.0
    margin = p3_score - p4_score

    # Build predictions, showing the original marginal P(podium) for clarity,
    # but strictly ranked by the coherent Plackett-Luce distribution.
    podium = []
    for i, (driver_id, _) in enumerate(top3):
        podium.append(PodiumPrediction(
            driver_id=driver_id,
            predicted_position=i + 1,
            probability=podium_probs.get(driver_id, 0.0),
            confidence=margin,
        ))

    if margin >= confidence_threshold * 2:
        confidence_level = "high"
    elif margin >= confidence_threshold:
        confidence_level = "medium"
    else:
        confidence_level = "low"

    return PodiumResult(
        podium=podium,
        full_grid=podium_probs,
        confidence_level=confidence_level,
        margin=margin,
    )


def monte_carlo_podium(
    podium_probs: dict[int | str, float],
    n_simulations: int = 10000,
    seed: int = 42,
) -> dict:
    """Run Monte Carlo simulation for podium predictions.

    Samples from probability distributions to estimate:
    - P(podium) per driver (simulation-based)
    - Most likely podium combination
    - P1/P2/P3 individual probabilities

    Args:
        podium_probs: {driver_id: P(podium)} for all drivers.
        n_simulations: Number of Monte Carlo samples.
        seed: Random seed for reproducibility.

    Returns:
        Dict with simulation results.
    """
    rng = np.random.default_rng(seed)
    drivers = list(podium_probs.keys())
    probs = np.array([podium_probs[d] for d in drivers])

    # Normalise probabilities for sampling
    # Each simulation: draw 3 drivers weighted by their probabilities
    probs_norm = probs / probs.sum()

    podium_counts: dict[int | str, int] = {d: 0 for d in drivers}
    position_counts: dict[int | str, dict[int, int]] = {
        d: {1: 0, 2: 0, 3: 0} for d in drivers
    }
    combo_counts: dict[tuple, int] = {}

    for _ in range(n_simulations):
        # Sample 3 unique drivers weighted by probability
        try:
            selected_indices = rng.choice(
                len(drivers), size=3, replace=False, p=probs_norm
            )
        except ValueError:
            # Handle edge case where probabilities are degenerate
            selected_indices = rng.choice(len(drivers), size=3, replace=False)

        selected = tuple(sorted(drivers[i] for i in selected_indices))

        # Count podium appearances
        for idx, driver_idx in enumerate(selected_indices):
            driver = drivers[driver_idx]
            podium_counts[driver] += 1
            position_counts[driver][idx + 1] += 1

        # Count combinations
        combo_counts[selected] = combo_counts.get(selected, 0) + 1

    # Normalise
    podium_pct = {d: c / n_simulations for d, c in podium_counts.items()}
    position_pct = {
        d: {pos: cnt / n_simulations for pos, cnt in pos_counts.items()}
        for d, pos_counts in position_counts.items()
    }

    # Most common combination
    most_common_combo = max(combo_counts, key=combo_counts.get) if combo_counts else ()
    most_common_pct = combo_counts.get(most_common_combo, 0) / n_simulations

    # Sort by podium percentage
    sorted_podium = sorted(podium_pct.items(), key=lambda x: x[1], reverse=True)

    return {
        "podium_probability": dict(sorted_podium),
        "position_probability": position_pct,
        "most_likely_combo": most_common_combo,
        "most_likely_combo_probability": most_common_pct,
        "top_combos": sorted(
            combo_counts.items(), key=lambda x: x[1], reverse=True
        )[:5],
        "n_simulations": n_simulations,
    }
