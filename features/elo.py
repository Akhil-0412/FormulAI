"""ELO rating system for F1 drivers and constructors.

Maintains rolling ratings updated after each race based on actual vs expected
finishing positions. Includes:
- Driver ELO: Overall driver skill rating
- Constructor ELO: Team performance rating
- Surface ELO: Driver skill on specific circuit types (street/high-speed/permanent)

K-factor decays with experience so rookies adapt faster.
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict

import pandas as pd

from data.db import query_df

logger = logging.getLogger(__name__)

# Default starting ELO
_BASE_ELO = 1500.0
# K-factor range
_K_MAX = 48.0  # For rookies (< 5 races)
_K_MIN = 16.0  # For veterans (> 40 races)
_K_DECAY_RACES = 40  # Number of races for K to reach K_MIN

# Circuit family mapping for surface ELO
SURFACE_FAMILIES = {
    "monaco": "street", "baku": "street", "marina_bay": "street",
    "jeddah": "street", "miami": "street", "vegas": "street",
    "albert_park": "street", "gilles_villeneuve": "street",
    "montreal": "street", "singapore": "street", "las_vegas": "street",

    "monza": "high_speed", "spa": "high_speed", "silverstone": "high_speed",
    "suzuka": "high_speed", "spielberg": "high_speed", "interlagos": "high_speed",
    "red_bull_ring": "high_speed",

    "bahrain": "permanent", "barcelona": "permanent", "hungaroring": "permanent",
    "zandvoort": "permanent", "cota": "permanent", "lusail": "permanent",
    "yas_marina": "permanent", "shanghai": "permanent", "imola": "permanent",
    "mexico_city": "permanent", "mexico": "permanent",
}


def _k_factor(n_races: int) -> float:
    """Compute K-factor that decays with experience."""
    if n_races <= 0:
        return _K_MAX
    decay = min(n_races / _K_DECAY_RACES, 1.0)
    return _K_MAX - decay * (_K_MAX - _K_MIN)


def _expected_score(rating_a: float, rating_b: float) -> float:
    """Expected score of A vs B using logistic curve."""
    return 1.0 / (1.0 + math.pow(10.0, (rating_b - rating_a) / 400.0))


def _compute_pairwise_update(
    driver_rating: float,
    opponent_ratings: list[float],
    actual_position: int,
    opponent_positions: list[int],
    k: float,
) -> float:
    """Compute ELO update from pairwise comparisons within a race.

    For each opponent, the driver either "won" (finished ahead) or "lost"
    (finished behind). The ELO update is the sum of all pairwise updates.
    """
    if not opponent_ratings:
        return 0.0

    total_update = 0.0
    for opp_rating, opp_pos in zip(opponent_ratings, opponent_positions):
        expected = _expected_score(driver_rating, opp_rating)
        # actual = 1 if driver finished ahead, 0 if behind, 0.5 if same
        if actual_position < opp_pos:
            actual = 1.0
        elif actual_position > opp_pos:
            actual = 0.0
        else:
            actual = 0.5
        total_update += k * (actual - expected)

    # Normalize by number of opponents to prevent extreme swings
    return total_update / len(opponent_ratings)


class ELOSystem:
    """Manages ELO ratings for drivers and constructors."""

    def __init__(self):
        self.driver_elo: dict[str, float] = defaultdict(lambda: _BASE_ELO)
        self.constructor_elo: dict[str, float] = defaultdict(lambda: _BASE_ELO)
        self.surface_elo: dict[str, dict[str, float]] = defaultdict(
            lambda: defaultdict(lambda: _BASE_ELO)
        )
        self.driver_race_count: dict[str, int] = defaultdict(int)
        self.constructor_race_count: dict[str, int] = defaultdict(int)
        self._is_built = False

    def build_from_db(self, up_to_race_id: str | None = None) -> None:
        """Build ELO ratings by replaying all historical races in order.

        Args:
            up_to_race_id: If provided, stop building after this race
                           (exclusive — this race is NOT included).
        """
        condition = ""
        params: tuple = ()
        if up_to_race_id:
            condition = "WHERE r.race_id < ?"
            params = (up_to_race_id,)

        races_df = query_df(
            f"""SELECT DISTINCT r.race_id, r.circuit_id, r.year, r.round
                FROM races r
                JOIN results res ON r.race_id = res.race_id
                {condition}
                ORDER BY r.year, r.round""",
            params,
        )

        if races_df.empty:
            logger.warning("No races found for ELO computation")
            return

        for _, race in races_df.iterrows():
            race_id = race["race_id"]
            circuit_id = race["circuit_id"]
            surface = SURFACE_FAMILIES.get(circuit_id, "permanent")

            results = query_df(
                """SELECT driver_id, constructor_id, position, status
                   FROM results WHERE race_id = ? AND position IS NOT NULL
                   ORDER BY position""",
                (race_id,),
            )

            if results.empty or len(results) < 2:
                continue

            drivers = results["driver_id"].tolist()
            constructors = results["constructor_id"].tolist()
            positions = results["position"].tolist()

            # Compute updates for each driver
            driver_updates: dict[str, float] = {}
            constructor_updates: dict[str, float] = {}

            for i, (did, cid, pos) in enumerate(zip(drivers, constructors, positions)):
                # Opponent ratings
                opp_ratings = [self.driver_elo[d] for j, d in enumerate(drivers) if j != i]
                opp_positions = [p for j, p in enumerate(positions) if j != i]

                k = _k_factor(self.driver_race_count[did])
                update = _compute_pairwise_update(
                    self.driver_elo[did], opp_ratings, pos, opp_positions, k
                )
                driver_updates[did] = update

                # Constructor update (averaged across team's drivers)
                opp_c_ratings = [self.constructor_elo[c] for j, c in enumerate(constructors) if j != i]
                k_c = _k_factor(self.constructor_race_count[cid])
                c_update = _compute_pairwise_update(
                    self.constructor_elo[cid], opp_c_ratings, pos, opp_positions, k_c
                )
                if cid not in constructor_updates:
                    constructor_updates[cid] = []
                constructor_updates[cid].append(c_update)

                # Surface-specific ELO
                opp_surface_ratings = [
                    self.surface_elo[d][surface] for j, d in enumerate(drivers) if j != i
                ]
                surface_update = _compute_pairwise_update(
                    self.surface_elo[did][surface],
                    opp_surface_ratings, pos, opp_positions, k * 0.7
                )
                self.surface_elo[did][surface] += surface_update

            # Apply driver updates
            for did, upd in driver_updates.items():
                self.driver_elo[did] += upd
                self.driver_race_count[did] += 1

            # Apply constructor updates (average across team's drivers)
            for cid, upd_list in constructor_updates.items():
                avg_upd = sum(upd_list) / len(upd_list) if upd_list else 0
                self.constructor_elo[cid] += avg_upd
                self.constructor_race_count[cid] += 1

        self._is_built = True
        logger.info(
            "ELO system built from %d races. Top drivers: %s",
            len(races_df),
            sorted(self.driver_elo.items(), key=lambda x: x[1], reverse=True)[:5],
        )

    def get_features(self, driver_id: str, constructor_id: str, circuit_id: str) -> dict:
        """Get ELO features for a driver in a specific race context."""
        surface = SURFACE_FAMILIES.get(circuit_id, "permanent")

        return {
            "driver_elo": self.driver_elo[driver_id],
            "constructor_elo": self.constructor_elo[constructor_id],
            "driver_surface_elo": self.surface_elo[driver_id][surface],
            "elo_driver_vs_field_median": (
                self.driver_elo[driver_id] - _BASE_ELO
            ),
            "elo_constructor_vs_field_median": (
                self.constructor_elo[constructor_id] - _BASE_ELO
            ),
            "driver_elo_race_count": self.driver_race_count[driver_id],
        }


# Module-level singleton (rebuilt per training context)
_elo_system: ELOSystem | None = None


def get_elo_system(race_id: str | None = None) -> ELOSystem:
    """Get or build the ELO system, cached at module level."""
    global _elo_system
    # Always rebuild when race_id changes (to maintain temporal integrity)
    _elo_system = ELOSystem()
    _elo_system.build_from_db(up_to_race_id=race_id)
    return _elo_system


def compute_elo_features(
    driver_id: str, constructor_id: str, circuit_id: str, race_id: str
) -> dict:
    """Compute ELO features for a driver using temporal-safe ELO system."""
    elo = get_elo_system(race_id)
    return elo.get_features(driver_id, constructor_id, circuit_id)
