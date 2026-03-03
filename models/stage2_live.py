"""Stage 2 — Live race updater that blends pre-race priors with live data."""

from __future__ import annotations

import logging
from typing import Literal

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class LiveRaceUpdater:
    """Update pre-race podium probabilities using live race data.

    Supports two strategies:
    1. **bayesian**: Treat Stage 1 probabilities as priors and update using
       live features as likelihood signals.
    2. **blended**: Blend Stage 1 probabilities with a secondary model's
       predictions using a lap-dependent weighting function.
    """

    def __init__(
        self,
        strategy: Literal["bayesian", "blended"] = "bayesian",
        temperature: float = 10.0,
    ) -> None:
        self.strategy = strategy
        self.temperature = temperature  # Controls sigmoid steepness for blending

    def update(
        self,
        pre_race_probs: dict[int, float],
        live_features: pd.DataFrame,
        current_lap: int,
        total_laps: int,
    ) -> dict[int, float]:
        """Update podium probabilities using live race data.

        Args:
            pre_race_probs: {driver_number: pre_race_probability}.
            live_features: DataFrame from live_race.build_live_features_all_drivers.
            current_lap: Current lap number.
            total_laps: Total race laps.

        Returns:
            {driver_number: updated_probability}.
        """
        if self.strategy == "bayesian":
            return self._bayesian_update(pre_race_probs, live_features, current_lap, total_laps)
        else:
            return self._blended_update(pre_race_probs, live_features, current_lap, total_laps)

    def _bayesian_update(
        self,
        pre_race_probs: dict[int, float],
        live_features: pd.DataFrame,
        current_lap: int,
        total_laps: int,
    ) -> dict[int, float]:
        """Bayesian update via state-space filtering.

        Posterior(t) ∝ Likelihood(data_t | x_t) × Posterior(t-1)
        
        Likelihood model:
        L_i(t) = exp(-α * gap_i(t) - β * tyre_age_i(t))
        
        Conditioned on regime:
        - Normal racing: gap carries high signal (large α)
        - Safety Car: field is compressed, gap carries low signal (small α)
        """
        updated = {}
        race_progress = current_lap / max(total_laps, 1)

        for _, row in live_features.iterrows():
            driver_num = int(row["driver_number"])
            prior = pre_race_probs.get(driver_num, 0.05)

            # ── Base features ───────────────────────────────────────
            gap_to_leader = row.get("gap_to_leader", 999.0)
            if pd.isna(gap_to_leader):
                gap_to_leader = 999.0
                
            tyre_age = row.get("compound_age", 1)
            compound = row.get("current_compound", 1)  # 0=SOFT, 1=MEDIUM, 2=HARD, etc.

            # ── Regime switching (Observation Model) ────────────────
            sc_active = row.get("safety_car_active", 0)
            is_pit_phase = row.get("is_pit_phase", False)
            
            # Base degradation slopes conditioned on compound
            # Soft degrades fastest, Hard degrades slowest
            base_beta = 0.01
            if compound == 0:    # Soft
                base_beta = 0.015
            elif compound == 2:  # Hard
                base_beta = 0.005
            
            
            if is_pit_phase:
                # During pit phase (in/pit/out lap):
                # Gap explodes transiently. Suppress gap penalty.
                alpha = 0.000  # Zero gap penalty during pit sequence
                beta = 0.000   # Tyres are fresh anyway or being swapped
            elif sc_active:
                # Under Safety Car, gaps are artificial and field compresses
                alpha = 0.005  # Reduced gap penalty
                beta = base_beta * 2.0  # Tyre age penalty increases due to temp loss
            else:
                # Normal racing regime
                alpha = 0.02   # ~2% decay in probability per second behind
                beta = base_beta # Context-conditioned tyre degradation
                
            # ── Counterfactual Overrides (Stage 4) ──────────────────
            alpha_override = row.get("alpha_override", None)
            beta_multiplier = row.get("beta_multiplier", 1.0)
            
            if pd.notna(alpha_override) and alpha_override is not None:
                alpha = float(alpha_override)
            beta *= float(beta_multiplier)
            
            # ── Likelihood ──────────────────────────────────────────
            likelihood = float(np.exp(-alpha * gap_to_leader - beta * tyre_age))
            
            # Position-based bonus for leaders (optional stabilizing anchor)
            position = row.get("current_position", 20)
            if position <= 3 and not sc_active and not is_pit_phase:
                likelihood *= 1.2  # Slight bump for actually holding track position
                
            # ── Posterior Update ────────────────────────────────────
            # To prevent early over-reaction, we can soften the likelihood 
            # early in the race (burn-in period)
            burn_in_factor = min(1.0, race_progress * 3.0) 
            effective_likelihood = 1.0 + (likelihood - 1.0) * burn_in_factor

            posterior = prior * effective_likelihood
            updated[driver_num] = float(posterior)

        # ── Normalization ───────────────────────────────────────────
        # Normalize sum of probabilities across the grid (approx 3.0 for 3 podium spots)
        # Note: the rigorous Plackett-Luce ranking happens in Stage 3 downstream
        total = sum(updated.values())
        if total > 0:
            target_sum = min(3.0, len(updated))
            scale = target_sum / total
            updated = {k: min(v * scale, 0.99) for k, v in updated.items()}

        return updated

    def _blended_update(
        self,
        pre_race_probs: dict[int, float],
        live_features: pd.DataFrame,
        current_lap: int,
        total_laps: int,
    ) -> dict[int, float]:
        """Blended update: weighted combination of pre-race and live signals.

        weight_live(lap) = sigmoid((lap - total_laps/2) / temperature)
        final_prob = (1 - weight_live) * stage1_prob + weight_live * live_estimate
        """
        # Compute live weight based on race progress
        midpoint = total_laps / 2
        weight_live = _sigmoid((current_lap - midpoint) / self.temperature)

        updated = {}
        for _, row in live_features.iterrows():
            driver_num = int(row["driver_number"])
            prior = pre_race_probs.get(driver_num, 0.05)

            # Compute a simple live probability estimate from position
            position = row.get("current_position", 20)
            live_estimate = _position_to_probability(position)

            # Blend
            prob = (1 - weight_live) * prior + weight_live * live_estimate
            updated[driver_num] = float(np.clip(prob, 0.01, 0.99))

        return updated


def _sigmoid(x: float) -> float:
    """Numerically stable sigmoid."""
    if x >= 0:
        z = np.exp(-x)
        return 1.0 / (1.0 + z)
    else:
        z = np.exp(x)
        return z / (1.0 + z)


def _position_to_probability(position: int | float) -> float:
    """Convert current race position to podium probability estimate."""
    if position <= 1:
        return 0.85
    elif position <= 2:
        return 0.75
    elif position <= 3:
        return 0.65
    elif position <= 5:
        return 0.30
    elif position <= 8:
        return 0.10
    elif position <= 12:
        return 0.03
    else:
        return 0.01
