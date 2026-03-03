"""Live race feature engineering — computes dynamic features from OpenF1 data."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def build_live_features(
    driver_number: int,
    current_lap: int,
    total_laps: int,
    lap_data: list[dict],
    interval_data: list[dict],
    pit_data: list[dict],
    stint_data: list[dict],
    race_control: list[dict],
) -> dict[str, Any]:
    """Build live race features for a single driver at a specific lap.

    All inputs come from OpenF1 API responses.

    Args:
        driver_number: Driver's car number.
        current_lap: Current lap number in the race.
        total_laps: Total laps in the race.
        lap_data: OpenF1 /laps response for this driver.
        interval_data: OpenF1 /intervals response for this driver.
        pit_data: OpenF1 /pit response for this driver.
        stint_data: OpenF1 /stints response for this driver.
        race_control: OpenF1 /race_control response for the session.

    Returns:
        Dict of live feature values.
    """
    features: dict[str, Any] = {}

    # ── Current position & gap ──────────────────────────────────────
    latest_interval = _latest_entry(interval_data)
    if latest_interval:
        features["current_position"] = latest_interval.get("position", 20)
        features["gap_to_leader"] = _parse_gap(latest_interval.get("gap_to_leader"))
        features["gap_to_driver_ahead"] = _parse_gap(latest_interval.get("interval"))
    else:
        features["current_position"] = 20
        features["gap_to_leader"] = np.nan
        features["gap_to_driver_ahead"] = np.nan

    # ── Positions gained since start ────────────────────────────────
    first_position = _first_entry(interval_data)
    start_pos = first_position.get("position", 20) if first_position else 20
    features["positions_gained"] = start_pos - features["current_position"]

    # ── Lap time analysis ───────────────────────────────────────────
    recent_laps = _get_recent_laps(lap_data, n=5)
    lap_durations = [
        lap.get("lap_duration") for lap in recent_laps
        if lap.get("lap_duration") is not None
    ]

    if lap_durations:
        features["avg_lap_time_last5"] = np.mean(lap_durations)
        if len(lap_durations) >= 3:
            # Trend: negative = improving, positive = degrading
            x = np.arange(len(lap_durations))
            coeffs = np.polyfit(x, lap_durations, 1)
            features["lap_time_trend"] = coeffs[0]
        else:
            features["lap_time_trend"] = 0.0
    else:
        features["avg_lap_time_last5"] = np.nan
        features["lap_time_trend"] = 0.0

    # ── Best lap time vs session best ───────────────────────────────
    all_durations = [
        lap.get("lap_duration") for lap in lap_data
        if lap.get("lap_duration") is not None
    ]
    features["best_lap_time"] = min(all_durations) if all_durations else np.nan

    # ── Pit stops & Phase Modeling ──────────────────────────────────
    features["pit_stops_made"] = len(pit_data)
    
    features["is_pit_phase"] = False
    if pit_data:
        latest_pit = pit_data[-1]
        pit_lap = latest_pit.get("lap", 0)
        # A pit phase encompasses the in-lap (lap - 1), pit lap (lap), and out-lap (lap + 1)
        if abs(current_lap - pit_lap) <= 1:
            features["is_pit_phase"] = True

    # ── Stint info (compound age) ───────────────────────────────────
    current_stint = _latest_entry(stint_data)
    if current_stint:
        features["compound_age"] = current_stint.get("tyre_age_at_start", 0) + (
            current_lap - current_stint.get("lap_start", current_lap)
        )
        features["current_compound"] = _encode_compound(current_stint.get("compound", ""))
    else:
        features["compound_age"] = 0
        features["current_compound"] = 1  # default = MEDIUM

    # Estimate remaining stops (simplified: >30 laps on current tyre → likely 1 more stop)
    laps_remaining = total_laps - current_lap
    features["laps_remaining"] = laps_remaining
    features["race_progress"] = current_lap / max(total_laps, 1)

    if laps_remaining > 30 and features["compound_age"] > 15:
        features["estimated_stops_remaining"] = 1
    elif laps_remaining > 50:
        features["estimated_stops_remaining"] = 2
    else:
        features["estimated_stops_remaining"] = 0

    # ── Safety car ──────────────────────────────────────────────────
    features["safety_car_active"] = _is_safety_car_active(race_control, current_lap)

    # ── Safety car count so far ─────────────────────────────────────
    sc_events = [
        msg for msg in race_control
        if msg.get("category") == "SafetyCar" or "SAFETY CAR" in str(msg.get("message", "")).upper()
    ]
    features["safety_car_count"] = len(sc_events)

    return features


def build_live_features_all_drivers(
    driver_data: dict[int, dict[str, list[dict]]],
    current_lap: int,
    total_laps: int,
    race_control: list[dict],
) -> pd.DataFrame:
    """Build live features for all drivers at a specific lap.

    Args:
        driver_data: {driver_number: {"laps": [...], "intervals": [...],
                      "pit": [...], "stints": [...]}}.
        current_lap: Current lap number.
        total_laps: Total race laps.
        race_control: Race control messages.

    Returns:
        DataFrame with one row per driver.
    """
    rows = []
    for driver_number, data in driver_data.items():
        features = build_live_features(
            driver_number=driver_number,
            current_lap=current_lap,
            total_laps=total_laps,
            lap_data=data.get("laps", []),
            interval_data=data.get("intervals", []),
            pit_data=data.get("pit", []),
            stint_data=data.get("stints", []),
            race_control=race_control,
        )
        features["driver_number"] = driver_number
        rows.append(features)

    return pd.DataFrame(rows)


# ── Helpers ─────────────────────────────────────────────────────────────


def _latest_entry(data: list[dict]) -> dict | None:
    """Get the most recent entry (last in list, assumed time-ordered)."""
    return data[-1] if data else None


def _first_entry(data: list[dict]) -> dict | None:
    """Get the first entry."""
    return data[0] if data else None


def _get_recent_laps(lap_data: list[dict], n: int = 5) -> list[dict]:
    """Get the last N laps from lap data."""
    return lap_data[-n:] if lap_data else []


def _parse_gap(gap_value: Any) -> float:
    """Parse a gap value (could be float, string '+1 LAP', etc.)."""
    if gap_value is None:
        return np.nan
    if isinstance(gap_value, (int, float)):
        return float(gap_value)
    if isinstance(gap_value, str):
        # Handle "+1 LAP" style gaps
        if "LAP" in gap_value.upper():
            try:
                laps = int(gap_value.split()[0].replace("+", ""))
                return laps * 90.0  # Approximate gap in seconds
            except (ValueError, IndexError):
                return 999.0
        try:
            return float(gap_value)
        except ValueError:
            return np.nan
    return np.nan


def _encode_compound(compound: str) -> int:
    """Encode tyre compound as integer."""
    compound_map = {
        "SOFT": 0, "MEDIUM": 1, "HARD": 2,
        "INTERMEDIATE": 3, "WET": 4,
    }
    return compound_map.get(compound.upper(), 1)


def _is_safety_car_active(race_control: list[dict], current_lap: int) -> int:
    """Check if safety car is currently active based on race control messages."""
    sc_deployed = False
    for msg in race_control:
        msg_text = str(msg.get("message", "")).upper()
        lap = msg.get("lap_number", 0)

        if lap and lap > current_lap:
            break

        if "SAFETY CAR DEPLOYED" in msg_text or "VIRTUAL SAFETY CAR DEPLOYED" in msg_text:
            sc_deployed = True
        elif "SAFETY CAR IN" in msg_text or "VIRTUAL SAFETY CAR ENDING" in msg_text:
            sc_deployed = False

    return 1 if sc_deployed else 0
