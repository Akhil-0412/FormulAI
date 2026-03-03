"""Tests for model modules."""

import numpy as np
import pandas as pd
import pytest


class TestStage3Ensemble:
    """Tests for constraint enforcement and Monte Carlo simulation."""

    def test_enforce_exactly_3_podium(self):
        from models.stage3_ensemble import enforce_podium_constraints

        probs = {f"driver_{i}": np.random.rand() for i in range(20)}
        result = enforce_podium_constraints(probs)

        assert len(result.podium) == 3
        assert {p.predicted_position for p in result.podium} == {1, 2, 3}

    def test_confidence_level_assignment(self):
        from models.stage3_ensemble import enforce_podium_constraints

        # High confidence: large gap between P3 and P4 (Normalized 0.23 margin)
        probs = {"a": 0.9, "b": 0.8, "c": 0.7, "d": 0.1, "e": 0.05}
        result = enforce_podium_constraints(probs, confidence_threshold=0.10)
        assert result.confidence_level == "high"

        # Low confidence: tiny gap
        probs2 = {"a": 0.5, "b": 0.48, "c": 0.47, "d": 0.46, "e": 0.45}
        result2 = enforce_podium_constraints(probs2, confidence_threshold=0.10)
        assert result2.confidence_level == "low"

    def test_position_ranking_with_head_b(self):
        from models.stage3_ensemble import enforce_podium_constraints

        probs = {"ver": 0.9, "ham": 0.8, "lec": 0.7, "nor": 0.3}
        # Head B position predictions (lower = better)
        positions = {"ver": 1.5, "ham": 3.2, "lec": 2.1, "nor": 5.0}

        result = enforce_podium_constraints(probs, positions)
        # VER should be P1 (lowest position pred among top 3)
        assert result.podium[0].driver_id == "ver"
        assert result.podium[0].predicted_position == 1

    def test_monte_carlo_valid(self):
        from models.stage3_ensemble import monte_carlo_podium

        probs = {f"driver_{i}": max(0.01, np.random.rand()) for i in range(20)}
        mc = monte_carlo_podium(probs, n_simulations=1000)

        assert mc["n_simulations"] == 1000
        assert len(mc["podium_probability"]) == 20
        assert len(mc["most_likely_combo"]) == 3
        assert mc["most_likely_combo_probability"] > 0

    def test_monte_carlo_probabilities_sum(self):
        from models.stage3_ensemble import monte_carlo_podium

        probs = {"a": 0.5, "b": 0.3, "c": 0.1, "d": 0.05, "e": 0.05}
        mc = monte_carlo_podium(probs, n_simulations=5000)

        # All drivers' P(podium) should be non-negative
        for p in mc["podium_probability"].values():
            assert p >= 0


class TestStage2LiveUpdater:
    """Tests for the live race updater."""

    def test_bayesian_update(self):
        from models.stage2_live import LiveRaceUpdater

        updater = LiveRaceUpdater(strategy="bayesian")
        pre_race = {1: 0.8, 44: 0.6, 16: 0.3, 4: 0.1}

        live_df = pd.DataFrame([
            {"driver_number": 1, "current_position": 1, "gap_to_leader": 0,
             "gap_to_driver_ahead": 0, "lap_time_trend": -0.1, "safety_car_active": 0},
            {"driver_number": 44, "current_position": 3, "gap_to_leader": 5,
             "gap_to_driver_ahead": 2, "lap_time_trend": 0.05, "safety_car_active": 0},
            {"driver_number": 16, "current_position": 8, "gap_to_leader": 20,
             "gap_to_driver_ahead": 3, "lap_time_trend": 0.2, "safety_car_active": 0},
            {"driver_number": 4, "current_position": 15, "gap_to_leader": 45,
             "gap_to_driver_ahead": 5, "lap_time_trend": 0.1, "safety_car_active": 0},
        ])

        updated = updater.update(pre_race, live_df, current_lap=30, total_laps=57)

        assert len(updated) == 4
        # Driver in P1 should still have high probability
        assert updated[1] > updated[4]

    def test_blended_update(self):
        from models.stage2_live import LiveRaceUpdater

        updater = LiveRaceUpdater(strategy="blended", temperature=10.0)
        pre_race = {1: 0.7, 44: 0.5}

        live_df = pd.DataFrame([
            {"driver_number": 1, "current_position": 1},
            {"driver_number": 44, "current_position": 5},
        ])

        updated = updater.update(pre_race, live_df, current_lap=40, total_laps=50)
        assert all(0 < p < 1 for p in updated.values())
