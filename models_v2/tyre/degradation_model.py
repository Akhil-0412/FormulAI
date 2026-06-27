"""Tyre degradation model."""

import numpy as np

class DegradationModel:
    def __init__(self):
        self.base_deg_rates = {"Soft": 0.1, "Medium": 0.05, "Hard": 0.02}

    def predict_degradation(self, compound: str, laps: int) -> float:
        """Predict lap time loss due to degradation."""
        rate = self.base_deg_rates.get(compound, 0.05)
        return rate * laps
