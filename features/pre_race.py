"""Pre-race feature engineering — builds the feature matrix from DB data."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from data.db import get_connection, query_df

logger = logging.getLogger(__name__)

_CIRCUITS_PATH = Path(__file__).resolve().parent.parent / "config" / "circuits.json"


def _load_circuit_metadata() -> dict[str, dict]:
    with open(_CIRCUITS_PATH) as f:
        return json.load(f).get("circuits", {})


CIRCUIT_META = _load_circuit_metadata()

# Circuit type encoding
_CIRCUIT_TYPE_MAP = {"street": 0, "technical": 1, "high_speed": 2}

# Nationality → country for home race detection
_NATIONALITY_TO_COUNTRY = {
    "British": "UK", "Dutch": "Netherlands", "Spanish": "Spain",
    "German": "Germany", "French": "France", "Finnish": "Finland",
    "Australian": "Australia", "Mexican": "Mexico", "Canadian": "Canada",
    "Monegasque": "Monaco", "Japanese": "Japan", "Chinese": "China",
    "Thai": "Thailand", "Danish": "Denmark", "American": "USA",
    "Italian": "Italy", "Brazilian": "Brazil",
}

_COUNTRY_CIRCUIT_MAP = {
    "UK": ["silverstone"], "Netherlands": ["zandvoort"], "Spain": ["barcelona"],
    "Germany": [], "France": [], "Finland": [], "Australia": ["albert_park"],
    "Mexico": ["mexico_city"], "Canada": ["montreal"], "Monaco": ["monaco"],
    "Japan": ["suzuka"], "China": ["shanghai"], "Thailand": [],
    "Denmark": [], "USA": ["cota", "miami", "las_vegas"], "Italy": ["monza", "imola"],
    "Brazil": ["interlagos"],
}

# F1 points system for LTR relevance labels
F1_POINTS = {
    1: 25, 2: 18, 3: 15, 4: 12, 5: 10,
    6: 8, 7: 6, 8: 4, 9: 2, 10: 1,
}


def build_pre_race_features(year: int, round_number: int) -> pd.DataFrame:
    """Build the full pre-race feature matrix for all drivers in a race.

    Args:
        year: Season year.
        round_number: Round number.

    Returns:
        DataFrame with one row per driver and all pre-race features.
    """
    race_id = f"{year}_{round_number}"

    # ── Base data ───────────────────────────────────────────────────
    results = query_df(
        "SELECT * FROM results WHERE race_id = ?", (race_id,)
    )
    qualifying = query_df(
        "SELECT * FROM qualifying WHERE race_id = ?", (race_id,)
    )
    race_info = query_df(
        "SELECT * FROM races WHERE race_id = ?", (race_id,)
    )
    standings = query_df(
        "SELECT * FROM standings_snapshot WHERE race_id = ?", (race_id,)
    )
    drivers = query_df("SELECT * FROM drivers")

    if race_info.empty:
        logger.warning("No race info for %s", race_id)
        return pd.DataFrame()

    # ── Build FULL driver roster from results + qualifying ──────────
    roster: list[dict] = []
    seen_drivers: set[str] = set()

    # Primary source: results (has actual outcome labels)
    for _, res in results.iterrows():
        did = res["driver_id"]
        if did not in seen_drivers:
            seen_drivers.add(did)

            pos = res["position"]
            status = res.get("status", "")
            is_finished = status == "Finished" or (status and str(status).startswith("+"))

            roster.append({
                "driver_id": did,
                "constructor_id": res["constructor_id"],
                "is_podium": res["is_podium"],
                "finish_position": pos,
                "status": status,
                "points": res.get("points", 0),
                "grid": res.get("grid", 20),
                # LTR relevance label: F1 points (25,18,15,...,0)
                "relevance": F1_POINTS.get(int(pos), 0) if pos and not pd.isna(pos) else 0,
                # DNF target
                "is_dnf": 0 if is_finished else 1,
            })

    # Secondary source: qualifying (catch drivers missing from results)
    for _, q in qualifying.iterrows():
        did = q["driver_id"]
        if did not in seen_drivers:
            seen_drivers.add(did)
            res_row = results[results["driver_id"] == did]
            if not res_row.empty:
                r = res_row.iloc[0]
                pos = r["position"]
                status = r.get("status", "")
                is_finished = status == "Finished" or (status and str(status).startswith("+"))
                roster.append({
                    "driver_id": did,
                    "constructor_id": r["constructor_id"],
                    "is_podium": r["is_podium"],
                    "finish_position": pos,
                    "status": status,
                    "points": r.get("points", 0),
                    "grid": r.get("grid", 20),
                    "relevance": F1_POINTS.get(int(pos), 0) if pos and not pd.isna(pos) else 0,
                    "is_dnf": 0 if is_finished else 1,
                })
            else:
                roster.append({
                    "driver_id": did,
                    "constructor_id": q.get("constructor_id", ""),
                    "is_podium": 0,
                    "finish_position": None,
                    "status": "Unknown",
                    "points": 0,
                    "grid": 20,
                    "relevance": 0,
                    "is_dnf": 1,
                })

    if not roster:
        # Fallback for upcoming races
        try:
            prev_results = query_df(
                """
                SELECT DISTINCT res.driver_id, res.constructor_id
                FROM results res
                JOIN races r ON res.race_id = r.race_id
                WHERE r.year = ? AND r.round < ?
                ORDER BY r.round DESC
                """, (year, round_number)
            )
            if not prev_results.empty:
                for _, r in prev_results.drop_duplicates(subset=['driver_id']).iterrows():
                    roster.append({
                        "driver_id": r["driver_id"],
                        "constructor_id": r["constructor_id"],
                        "is_podium": 0,
                        "finish_position": None,
                        "status": "Upcoming",
                        "points": 0,
                        "grid": 20,
                        "relevance": 0,
                        "is_dnf": 0,
                    })
        except Exception as e:
            logger.warning("Skipping %s: %s", race_id, e)

    if not roster:
        logger.warning("No drivers found for %s!", race_id)
        return pd.DataFrame()

    circuit_id = race_info.iloc[0]["circuit_id"]
    country = race_info.iloc[0]["country"]

    # Get total rounds
    total_rounds = query_df(
        "SELECT MAX(round) as max_round FROM races WHERE year = ?", (year,)
    )
    try:
        _raw = total_rounds.iloc[0]["max_round"] if not total_rounds.empty else None
        if isinstance(_raw, bytes):
            max_round = int.from_bytes(_raw, 'little') if _raw else 24
        elif _raw is not None and not (isinstance(_raw, float) and np.isnan(_raw)):
            max_round = int(_raw)
        else:
            max_round = 24
    except (ValueError, TypeError):
        max_round = 24

    rows = []
    for entry in roster:
        driver_id = entry["driver_id"]
        constructor_id = entry["constructor_id"]

        features = _build_driver_features(
            driver_id=driver_id,
            constructor_id=constructor_id,
            race_id=race_id,
            year=year,
            round_number=round_number,
            circuit_id=circuit_id,
            country=country,
            qualifying=qualifying,
            standings=standings,
            drivers=drivers,
            max_round=max_round,
        )

        # Target/meta columns
        features["is_podium"] = entry["is_podium"]
        features["finish_position"] = entry["finish_position"]
        features["relevance"] = entry["relevance"]
        features["is_dnf"] = entry["is_dnf"]
        features["points_scored"] = entry["points"]
        features["driver_id"] = driver_id
        features["constructor_id"] = constructor_id
        features["race_id"] = race_id

        rows.append(features)

    df = pd.DataFrame(rows)
    logger.info("Built pre-race features for %s: %d drivers, %d features",
                race_id, len(df), len(df.columns) - 8)  # minus meta cols
    return df


from features.qualifying_features import compute_qualifying_features
from features.tyre_features import compute_tyre_features
from features.strategy_features import compute_strategy_features
from features.reliability_features import compute_reliability_features
from features.development_features import compute_development_features
from features.safety_car_features import compute_safety_car_features
from features.weather_features import compute_weather_features
from features.form_features import compute_form_features
from features.circuit_features import compute_circuit_features
from features.elo import compute_elo_features
from features.momentum_features import compute_momentum_features


def _build_driver_features(
    *,
    driver_id: str,
    constructor_id: str,
    race_id: str,
    year: int,
    round_number: int,
    circuit_id: str,
    country: str,
    qualifying: pd.DataFrame,
    standings: pd.DataFrame,
    drivers: pd.DataFrame,
    max_round: int,
) -> dict:
    """Build all pre-race features for a single driver using the domain modules."""
    circuit_info = CIRCUIT_META.get(circuit_id, {})
    circuit_info["id"] = circuit_id  # Ensure id is available

    features: dict = {}

    features.update(compute_qualifying_features(driver_id, qualifying, race_id))
    features.update(compute_tyre_features(driver_id, circuit_id, circuit_info))
    features.update(compute_strategy_features(driver_id, circuit_info))
    features.update(compute_reliability_features(constructor_id, driver_id, race_id))
    features.update(compute_development_features(driver_id, constructor_id, race_id))

    weather_feats = compute_weather_features(race_id)
    features.update(weather_feats)

    rain_prob = weather_feats.get("rain_prob", 0.0)
    features.update(compute_safety_car_features(circuit_id, circuit_info, rain_prob))

    features.update(compute_form_features(driver_id, circuit_id, race_id, constructor_id))
    features.update(compute_circuit_features(driver_id, constructor_id, circuit_info, standings, race_id))

    # New v3 features
    features.update(compute_elo_features(driver_id, constructor_id, circuit_id, race_id))
    features.update(compute_momentum_features(driver_id, race_id))

    return features


def build_full_training_set(
    start_year: int = 2014,
    end_year: int = 2026,
) -> pd.DataFrame:
    """Build the complete training feature matrix across multiple seasons."""
    all_frames = []

    for year in range(start_year, end_year + 1):
        races = query_df("SELECT round FROM races WHERE year = ? ORDER BY round", (year,))
        for _, race in races.iterrows():
            round_num = race["round"]
            try:
                df = build_pre_race_features(year, round_num)
                if not df.empty:
                    all_frames.append(df)
            except Exception as exc:
                logger.warning("Skipping %d R%d: %s", year, round_num, exc)

    if not all_frames:
        return pd.DataFrame()

    full = pd.concat(all_frames, ignore_index=True)
    logger.info("Full training set: %d rows, %d columns", len(full), len(full.columns))
    return full
