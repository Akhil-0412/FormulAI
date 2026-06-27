"""Pit window strategy model."""

class PitWindowModel:
    def __init__(self):
        pass

    def get_optimal_window(self, compound: str) -> tuple[int, int]:
        """Return optimal pit window (start_lap, end_lap) for a starting compound."""
        if compound == "Soft":
            return 12, 18
        elif compound == "Medium":
            return 20, 28
        else:
            return 28, 38
