"""FastF1 client — loads qualifying, practice, and race sessions with caching."""

from __future__ import annotations

import logging
from typing import Literal

import fastf1
import pandas as pd

from config.settings import settings

logger = logging.getLogger(__name__)

SessionType = Literal["FP1", "FP2", "FP3", "Q", "R", "S", "SQ"]


def _ensure_cache() -> None:
    """Create the FastF1 cache directory and enable caching."""
    cache_dir = settings.abs_cache_dir
    cache_dir.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(cache_dir))


def load_session(year: int, round_number: int, session_type: SessionType) -> fastf1.core.Session:
    """Load and return a FastF1 session (data already loaded).

    Args:
        year: Season year (e.g. 2023).
        round_number: Round number within the season.
        session_type: One of FP1/FP2/FP3/Q/R/S/SQ.

    Returns:
        A loaded FastF1 Session object.

    Raises:
        ValueError: If the session cannot be loaded.
    """
    _ensure_cache()
    try:
        session = fastf1.get_session(year, round_number, session_type)
        session.load()
        logger.info("Loaded %s %d R%d", session_type, year, round_number)
        return session
    except Exception as exc:
        logger.warning("Could not load %s %d R%d: %s", session_type, year, round_number, exc)
        raise ValueError(f"Session {session_type} {year} R{round_number} unavailable") from exc


def get_qualifying_results(year: int, round_number: int) -> pd.DataFrame:
    """Extract qualifying results for a race.

    Returns a DataFrame with columns:
        DriverNumber, Abbreviation, TeamName, Position, Q1, Q2, Q3
    """
    session = load_session(year, round_number, "Q")
    results = session.results
    if results is None or results.empty:
        return pd.DataFrame()

    cols = ["DriverNumber", "Abbreviation", "TeamName", "Position", "Q1", "Q2", "Q3"]
    available = [c for c in cols if c in results.columns]
    df = results[available].copy()

    # Convert timedelta Q columns to seconds
    for q_col in ["Q1", "Q2", "Q3"]:
        if q_col in df.columns:
            df[q_col] = df[q_col].apply(
                lambda td: td.total_seconds() if pd.notna(td) and hasattr(td, "total_seconds") else None
            )

    return df.reset_index(drop=True)


def get_practice_results(
    year: int, round_number: int, session_type: SessionType = "FP2"
) -> pd.DataFrame:
    """Extract practice session results.

    Returns a DataFrame with columns:
        DriverNumber, Abbreviation, TeamName, BestLapTime, LapCount
    """
    session = load_session(year, round_number, session_type)
    laps = session.laps
    if laps is None or laps.empty:
        return pd.DataFrame()

    # Best lap per driver
    summary = (
        laps.groupby(["DriverNumber", "Driver", "Team"])
        .agg(
            BestLapTime=("LapTime", "min"),
            LapCount=("LapNumber", "count"),
            AvgLapTime=("LapTime", "mean"),
        )
        .reset_index()
    )

    # Convert timedeltas to seconds
    for col in ["BestLapTime", "AvgLapTime"]:
        summary[col] = summary[col].apply(
            lambda td: td.total_seconds() if pd.notna(td) and hasattr(td, "total_seconds") else None
        )

    return summary


def get_race_laps(year: int, round_number: int) -> pd.DataFrame:
    """Get all lap-by-lap data for a race session.

    Returns a DataFrame with columns from FastF1 Laps:
        DriverNumber, Driver, Team, LapNumber, LapTime, Position,
        Compound, TyreLife, Stint, etc.
    """
    session = load_session(year, round_number, "R")
    laps = session.laps
    if laps is None or laps.empty:
        return pd.DataFrame()

    # Convert LapTime to seconds
    df = laps.copy()
    if "LapTime" in df.columns:
        df["LapTimeSec"] = df["LapTime"].apply(
            lambda td: td.total_seconds() if pd.notna(td) and hasattr(td, "total_seconds") else None
        )
    return df.reset_index(drop=True)


def get_race_results(year: int, round_number: int) -> pd.DataFrame:
    """Get final race results (finishing order, status, points).

    Returns a DataFrame from session.results with key columns:
        DriverNumber, Abbreviation, TeamName, Position, GridPosition, Status, Points
    """
    session = load_session(year, round_number, "R")
    results = session.results
    if results is None or results.empty:
        return pd.DataFrame()

    cols = [
        "DriverNumber", "Abbreviation", "TeamName",
        "Position", "GridPosition", "Status", "Points",
    ]
    available = [c for c in cols if c in results.columns]
    return results[available].copy().reset_index(drop=True)


def get_season_schedule(year: int) -> pd.DataFrame:
    """Return the event schedule for a given year.

    Returns a DataFrame with columns:
        RoundNumber, EventName, Country, Location, EventDate, EventFormat
    """
    _ensure_cache()
    schedule = fastf1.get_event_schedule(year)
    cols = ["RoundNumber", "EventName", "Country", "Location", "EventDate", "EventFormat"]
    available = [c for c in cols if c in schedule.columns]
    return schedule[available].copy()
