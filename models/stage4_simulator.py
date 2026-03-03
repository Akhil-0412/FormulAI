"""Stage 4: Strategic Counterfactual Simulator.

Simulates the race forward from the current live posterior by perturbing
the likelihood coefficients (alpha, beta) over N iterations to construct
a counterfactual distribution. Not outcome manipulation—parameter perturbation.
"""

import logging
from typing import Any

import numpy as np
import pandas as pd

from models.stage3_ensemble import enforce_podium_constraints

logger = logging.getLogger(__name__)


def simulate_forward(
    current_state_df: pd.DataFrame,
    current_posterior_probs: dict[int, float],
    scenario_params: dict[str, Any],
    total_laps: int,
    current_lap: int,
    n_runs: int = 1000,
) -> dict[str, Any]:
    """Run a counterfactual Monte Carlo simulation from the current lap to the end.

    Args:
        current_state_df: Live features DataFrame at current lap.
        current_posterior_probs: Stage 2 posterior probabilities at current lap.
        scenario_params: Dictionary of scenario instructions.
            - sc_prob_multiplier (float): Multiplier for nominal SC probability.
            - rain_onset_lap (int | None): Lap when rain starts.
            - early_pit_driver (int | None): Driver number to force pit stop.
            - base_dnf_prob (float): Per-lap DNF probability.
        total_laps: Total laps in the race.
        current_lap: Starting lap for the simulation.
        n_runs: Number of Monte Carlo trajectories.

    Returns:
        Dict detailing the shifted distribution, delta probabilities, and expected finish positions.
    """
    if current_state_df.empty or not current_posterior_probs:
        return {}

    # ── 1. Initialize State Vectors ──────────────────────────────────────
    drivers = current_state_df["driver_number"].astype(int).tolist()
    n_drivers = len(drivers)

    # Initial probabilities
    base_probs = np.array([current_posterior_probs.get(d, 0.01) for d in drivers])

    # Initial state matrices (shape: N_drivers)
    gaps = current_state_df["gap_to_leader"].fillna(999.0).values.astype(float)
    tyre_ages = current_state_df["compound_age"].fillna(1.0).values.astype(float)
    compounds = current_state_df.get("current_compound", pd.Series([1]*n_drivers)).values.astype(int)

    # Base decay slopes
    base_betas = np.where(compounds == 0, 0.015, np.where(compounds == 2, 0.005, 0.01))

    # Reverse-engineer the base prior (Stage 1) from the current posterior (Stage 2)
    # Posterior = Prior * Likelihood
    # Prior = Posterior / Likelihood
    current_alphas = np.full(n_drivers, 0.02)
    sc_active_current = current_state_df["safety_car_active"].values.astype(bool)
    current_alphas[sc_active_current] = 0.005
    
    current_betas = base_betas.copy()
    current_betas[sc_active_current] *= 2.0
    
    current_likelihood = np.exp(-current_alphas * gaps - current_betas * tyre_ages)
    current_progress = current_lap / max(total_laps, 1)
    current_burn_in = min(1.0, current_progress * 3.0)
    current_effective_likelihood = 1.0 + (current_likelihood - 1.0) * current_burn_in
    
    # Recover latent base prior
    latent_base_priors = base_probs / np.where(current_effective_likelihood > 0, current_effective_likelihood, 1.0)

    # Scenario parameters
    sc_prob = 0.03 * scenario_params.get("sc_prob_multiplier", 1.0)
    rain_lap = scenario_params.get("rain_onset_lap", 999)
    early_pit_driver = scenario_params.get("early_pit_driver", -1)
    base_dnf_prob = scenario_params.get("base_dnf_prob", 0.002)

    # To track final outcomes across all runs
    final_probs_matrix = np.zeros((n_runs, n_drivers))
    
    rng = np.random.default_rng(42)  # Fixed seed for scenario stability

    # ── 2. Run Monte Carlo Trajectories ──────────────────────────────────
    for run_idx in range(n_runs):
        # Initialize run state
        t_probs = base_probs.copy()
        t_tyre_ages = tyre_ages.copy()
        t_gaps = gaps.copy()  
        t_dnf_mask = np.zeros(n_drivers, dtype=bool)
        
        # Determine if SC is active currently for this run
        sc_active = False
        sc_laps_remaining = 0
        
        for lap in range(current_lap + 1, total_laps + 1):
            race_progress = lap / max(total_laps, 1)
            
            # Scenario: Rain onset
            is_raining = lap >= rain_lap
            
            # Scenario: Safety Car Event
            if sc_laps_remaining > 0:
                sc_laps_remaining -= 1
                sc_active = True
            else:
                if rng.random() < sc_prob:
                    sc_active = True
                    sc_laps_remaining = rng.integers(2, 5)
                else:
                    sc_active = False
            
            # Simulate lap evolution
            # 1. Update absolute tyre ages
            t_tyre_ages += 1.0
            
            # 2. DNF Simulation (hazard model)
            new_dnfs = rng.random(n_drivers) < base_dnf_prob
            t_dnf_mask = t_dnf_mask | new_dnfs
            
            # 3. Pit Stop Simulation (heuristic: pit if tyre age > 30, or forced scenario)
            pit_mask = t_tyre_ages > 30.0
            
            forced_mask = np.zeros(n_drivers, dtype=bool)
            if early_pit_driver != -1:
                # Force pit within next 2 laps
                if lap == current_lap + rng.integers(1, 3):
                    forced_mask = (np.array(drivers) == early_pit_driver)
                    pit_mask = pit_mask | forced_mask
            
            t_tyre_ages[pit_mask] = 0.0
            
            # Counterfactual: Only forced strategic deviations incur a relative track position penalty.
            # Natural pit cycles roughly preserve relative gaps across the field.
            t_gaps[forced_mask] += 20.0
            
            # 4. Filter Coefficients
            # Default alpha and beta
            alphas = np.full(n_drivers, 0.02)
            betas = base_betas.copy()
            
            if sc_active:
                alphas[:] = 0.005
                betas *= 2.0  # tyres degrade faster on restart due to temp loss
                
            if is_raining:
                alphas[:] = 0.01  # gaps matter less in rain (survival more important)
                # Randomize beta multiplier (variance increase)
                betas *= rng.lognormal(mean=0.2, sigma=0.5, size=n_drivers)
                
            # Pit stops suppress likelihood penalty temporarily for this lap
            alphas[pit_mask] = 0.000
            betas[pit_mask] = 0.000
            
            # Absolute Likelihood against the Latent Prior
            likelihood = np.exp(-alphas * t_gaps - betas * t_tyre_ages)
            
            # Burn-in attenuation
            burn_in = min(1.0, race_progress * 3.0)
            effective_likelihood = 1.0 + (likelihood - 1.0) * burn_in
            
            # DNF zeroes out probability
            effective_likelihood[t_dnf_mask] = 0.0
            
            # Apply update to the Latent Base Prior, NOT recursively to t_probs
            t_probs = latent_base_priors * effective_likelihood
            
            # 5. Fast proportional normalization for stability mid-run
            total = np.sum(t_probs)
            if total > 0:
                target_sum = min(3.0, np.sum(~t_dnf_mask))
                t_probs = np.minimum(t_probs * (target_sum / total), 0.99)
                t_probs[t_dnf_mask] = 0.0
                
        # End of race for this run, apply formal Plackett-Luce constraint
        final_run_probs_dict = {d: float(p) for d, p in zip(drivers, t_probs)}
        final_normalized_dict = enforce_podium_constraints(final_run_probs_dict).full_grid
        
        final_probs_matrix[run_idx, :] = [final_normalized_dict.get(d, 0.0) for d in drivers]

    # ── 3. Aggregate Delta & Output ──────────────────────────────────────
    mean_probs = np.mean(final_probs_matrix, axis=0)
    std_probs = np.std(final_probs_matrix, axis=0)
    
    # Calculate baseline for delta comparison
    baseline_res = enforce_podium_constraints(current_posterior_probs).full_grid
    baseline_array = np.array([baseline_res.get(d, 0.0) for d in drivers])
    
    deltas = mean_probs - baseline_array
    
    # Pack response
    driver_stats = {}
    for i, d in enumerate(drivers):
        driver_stats[d] = {
            "baseline_prob": float(baseline_array[i]),
            "simulated_prob": float(mean_probs[i]),
            "delta_prob": float(deltas[i]),
            "uncertainty_std": float(std_probs[i]),
        }
        
    return {
        "n_runs": n_runs,
        "sc_prob_multiplier": scenario_params.get("sc_prob_multiplier", 1.0),
        "drivers": driver_stats,
        "most_positively_affected": int(drivers[np.argmax(deltas)]),
        "most_negatively_affected": int(drivers[np.argmin(deltas)]),
    }
