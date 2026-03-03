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
    # BUG FIX: Previously only iterated results, which could be partial
    # (e.g., sprint weekends, incomplete ingestion → 1 driver).
    # Now we UNION all driver_ids from both tables to guarantee the full grid.
    roster: list[dict] = []
    seen_drivers: set[str] = set()

    # Primary source: results (has actual outcome labels)
    for _, res in results.iterrows():
        did = res["driver_id"]
        if did not in seen_drivers:
            seen_drivers.add(did)
            roster.append({
                "driver_id": did,
                "constructor_id": res["constructor_id"],
                "is_podium": res["is_podium"],
                "finish_position": res["position"],
                "status": res.get("status", ""),
            })

    # Secondary source: qualifying (catch drivers missing from results)
    for _, q in qualifying.iterrows():
        did = q["driver_id"]
        if did not in seen_drivers:
            seen_drivers.add(did)
            # Look up result if it exists but was missed
            res_row = results[results["driver_id"] == did]
            if not res_row.empty:
                r = res_row.iloc[0]
                roster.append({
                    "driver_id": did,
                    "constructor_id": r["constructor_id"],
                    "is_podium": r["is_podium"],
                    "finish_position": r["position"],
                    "status": r.get("status", ""),
                })
            else:
                roster.append({
                    "driver_id": did,
                    "constructor_id": q.get("constructor_id", ""),
                    "is_podium": 0,
                    "finish_position": None,  # DNF/DNS
                    "status": "Unknown",
                })

    if not roster:
        logger.warning("No drivers found for %s", race_id)
        return pd.DataFrame()

    circuit_id = race_info.iloc[0]["circuit_id"]
    country = race_info.iloc[0]["country"]
    race_date = race_info.iloc[0]["race_date"]

    # Get total rounds this year up to this point
    total_rounds = query_df(
        "SELECT MAX(round) as max_round FROM races WHERE year = ?", (year,)
    )
    max_round = total_rounds.iloc[0]["max_round"] if not total_rounds.empty else 24

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

        # Target variables
        features["is_podium"] = entry["is_podium"]
        features["finish_position"] = entry["finish_position"]
        features["driver_id"] = driver_id
        features["race_id"] = race_id

        rows.append(features)

    df = pd.DataFrame(rows)
    logger.info("Built pre-race features for %s: %d drivers, %d features",
                race_id, len(df), len(df.columns) - 4)  # minus meta cols
    return df


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
    """Build all pre-race features for a single driver."""
    features: dict = {}

    # ── Qualifying features ─────────────────────────────────────────
    driver_quali = qualifying[qualifying["driver_id"] == driver_id]
    if not driver_quali.empty:
        q = driver_quali.iloc[0]
        features["grid_position"] = q["position"]

        # Gap to pole
        pole_time = qualifying["q3_sec"].min()
        driver_q3 = q["q3_sec"]
        if pd.notna(driver_q3) and pd.notna(pole_time) and pole_time > 0:
            features["quali_gap_to_pole"] = driver_q3 - pole_time
        else:
            features["quali_gap_to_pole"] = np.nan

        features["quali_q3_reached"] = 1 if pd.notna(q["q3_sec"]) else 0

        # Sector consistency (approx from Q1/Q2/Q3 times)
        q_times = [q[c] for c in ["q1_sec", "q2_sec", "q3_sec"] if pd.notna(q[c])]
        features["quali_consistency"] = np.std(q_times) if len(q_times) >= 2 else np.nan
    else:
        features["grid_position"] = 20
        features["quali_gap_to_pole"] = np.nan
        features["quali_q3_reached"] = 0
        features["quali_consistency"] = np.nan

    # ── Recent form ─────────────────────────────────────────────────
    recent = query_df(
        """SELECT position, is_podium, status FROM results
           WHERE driver_id = ? AND race_id < ? AND position IS NOT NULL
           ORDER BY race_id DESC LIMIT 5""",
        (driver_id, race_id),
    )
    if not recent.empty:
        features["driver_last3_avg_pos"] = recent.head(3)["position"].mean()
        features["driver_last5_podium_rate"] = recent["is_podium"].mean()
        features["driver_last5_avg_pos"] = recent["position"].mean()
        dnfs = recent["status"].apply(
            lambda s: not (s == "Finished" or (s and str(s).startswith("+")))
        ).sum()
        features["driver_recent_dnf_rate"] = dnfs / len(recent)
    else:
        features["driver_last3_avg_pos"] = 15.0
        features["driver_last5_podium_rate"] = 0.0
        features["driver_last5_avg_pos"] = 15.0
        features["driver_recent_dnf_rate"] = 0.0

    # ── Circuit history ─────────────────────────────────────────────
    circuit_hist = query_df(
        """SELECT position FROM results
           JOIN races ON results.race_id = races.race_id
           WHERE results.driver_id = ? AND races.circuit_id = ?
             AND results.race_id < ? AND results.position IS NOT NULL""",
        (driver_id, circuit_id, race_id),
    )
    if not circuit_hist.empty:
        features["driver_circuit_avg_pos"] = circuit_hist["position"].mean()
        features["driver_circuit_best_pos"] = circuit_hist["position"].min()
    else:
        features["driver_circuit_avg_pos"] = 10.0
        features["driver_circuit_best_pos"] = 10

    # ── Championship standings ──────────────────────────────────────
    driver_standing = standings[standings["driver_id"] == driver_id]
    if not driver_standing.empty:
        s = driver_standing.iloc[0]
        features["driver_championship_pos"] = s["position"]
        features["driver_championship_pts"] = s["points"]
        features["constructor_championship_pos"] = s["constructor_pos"]
        features["constructor_championship_pts"] = s["constructor_pts"]
    else:
        features["driver_championship_pos"] = 20
        features["driver_championship_pts"] = 0
        features["constructor_championship_pos"] = 10
        features["constructor_championship_pts"] = 0

    # ── Constructor reliability & Survival Model ────────────────────
    # 1. Recent reliability (last 20 races)
    rel_recent = query_df(
        """SELECT status FROM results
           WHERE constructor_id = ? AND race_id < ?
           ORDER BY race_id DESC LIMIT 20""",
        (constructor_id, race_id),
    )
    if not rel_recent.empty:
        finished = rel_recent["status"].apply(
            lambda s: s == "Finished" or (s and str(s).startswith("+"))
        ).sum()
        features["constructor_reliability"] = finished / len(rel_recent)
    else:
        features["constructor_reliability"] = 0.9

    # 2. Season reliability (P(Finish | constructor, season))
    rel_season = query_df(
        """SELECT status FROM results
           JOIN races ON results.race_id = races.race_id
           WHERE results.constructor_id = ? AND races.year = ? AND results.race_id < ?""",
        (constructor_id, year, race_id),
    )
    if not rel_season.empty and len(rel_season) >= 2:
        finished = rel_season["status"].apply(
            lambda s: s == "Finished" or (s and str(s).startswith("+"))
        ).sum()
        features["constructor_season_reliability"] = finished / len(rel_season)
    else:
        features["constructor_season_reliability"] = features["constructor_reliability"]

    # 3. Circuit reliability (P(Finish | constructor, circuit))
    rel_circuit = query_df(
        """SELECT status FROM results
           JOIN races ON results.race_id = races.race_id
           WHERE results.constructor_id = ? AND races.circuit_id = ? AND results.race_id < ?""",
        (constructor_id, circuit_id, race_id),
    )
    if not rel_circuit.empty:
        finished = rel_circuit["status"].apply(
            lambda s: s == "Finished" or (s and str(s).startswith("+"))
        ).sum()
        features["constructor_circuit_reliability"] = finished / len(rel_circuit)
    else:
        features["constructor_circuit_reliability"] = features["constructor_reliability"]

    # 4. Composite Survival Probability P(Finish)
    features["constructor_survival_prob"] = (
        0.5 * features["constructor_season_reliability"] +
        0.3 * features["constructor_reliability"] +
        0.2 * features["constructor_circuit_reliability"]
    )

    # ── Teammate quali gap ──────────────────────────────────────────
    teammate_quali = qualifying[
        (qualifying["constructor_id"] == constructor_id)
        & (qualifying["driver_id"] != driver_id)
    ]
    if not teammate_quali.empty and not driver_quali.empty:
        driver_best_q = driver_quali.iloc[0]["q3_sec"] or driver_quali.iloc[0]["q2_sec"] or driver_quali.iloc[0]["q1_sec"]
        tm_best_q = teammate_quali.iloc[0]["q3_sec"] or teammate_quali.iloc[0]["q2_sec"] or teammate_quali.iloc[0]["q1_sec"]
        if pd.notna(driver_best_q) and pd.notna(tm_best_q) and tm_best_q > 0:
            features["teammate_quali_gap"] = driver_best_q - tm_best_q
        else:
            features["teammate_quali_gap"] = 0.0
    else:
        features["teammate_quali_gap"] = 0.0

    # ── Circuit metadata ────────────────────────────────────────────
    circuit_info = CIRCUIT_META.get(circuit_id, {})
    features["circuit_type"] = _CIRCUIT_TYPE_MAP.get(circuit_info.get("type", ""), 1)
    features["circuit_overtake_difficulty"] = circuit_info.get("overtake_difficulty", 0.5)

    # ── Home race ───────────────────────────────────────────────────
    driver_info = drivers[drivers["driver_id"] == driver_id]
    if not driver_info.empty:
        nationality = driver_info.iloc[0]["nationality"]
        home_country = _NATIONALITY_TO_COUNTRY.get(nationality, "")
        home_circuits = _COUNTRY_CIRCUIT_MAP.get(home_country, [])
        features["home_race"] = 1 if circuit_id in home_circuits else 0
    else:
        features["home_race"] = 0

    # ── Season progress ─────────────────────────────────────────────
    features["season_progress"] = round_number / max(max_round, 1) if max_round else 0.5

    return features


def build_full_training_set(
    start_year: int = 2018,
    end_year: int = 2024,
) -> pd.DataFrame:
    """Build the complete training feature matrix across multiple seasons.

    Returns:
        A single DataFrame with all driver-race entries and features.
    """
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
