"""Ingestion orchestrator — pulls from Jolpica + FastF1 into the SQLite DB."""

from __future__ import annotations

import logging
import re
from typing import Any

from data.db import (
    get_connection,
    init_db,
    upsert_constructor,
    upsert_driver,
    upsert_pit_stop,
    upsert_qualifying,
    upsert_race,
    upsert_result,
    upsert_standings,
)
from data.jolpica_client import JolpicaClient

logger = logging.getLogger(__name__)


def _parse_lap_time(time_str: str | None) -> float | None:
    """Convert 'M:SS.mmm' to seconds."""
    if not time_str:
        return None
    match = re.match(r"(\d+):(\d+\.\d+)", time_str)
    if match:
        return int(match.group(1)) * 60 + float(match.group(2))
    return None


def _circuit_key(circuit_id: str) -> str:
    """Normalise Jolpica circuit ID to our circuits.json key."""
    mapping = {
        "bahrain": "bahrain", "jeddah": "jeddah", "albert_park": "albert_park",
        "suzuka": "suzuka", "shanghai": "shanghai", "miami": "miami",
        "imola": "imola", "monaco": "monaco", "villeneuve": "montreal",
        "catalunya": "barcelona", "red_bull_ring": "spielberg",
        "silverstone": "silverstone", "hungaroring": "hungaroring",
        "spa": "spa", "zandvoort": "zandvoort", "monza": "monza",
        "baku": "baku", "marina_bay": "singapore", "americas": "cota",
        "rodriguez": "mexico_city", "interlagos": "interlagos",
        "las_vegas": "las_vegas", "losail": "lusail", "yas_marina": "yas_marina",
    }
    return mapping.get(circuit_id, circuit_id)


def ingest_season(year: int, client: JolpicaClient | None = None) -> int:
    """Ingest a complete season of race results into the database.

    Args:
        year: Season year.
        client: Optional Jolpica client (created if not provided).

    Returns:
        Number of races ingested.
    """
    if client is None:
        client = JolpicaClient()

    init_db()
    races = client.get_all_season_results(year)
    logger.info("Ingesting %d races for %d", len(races), year)

    count = 0
    for race_data in races:
        try:
            _ingest_single_race(year, race_data, client)
            count += 1
        except Exception as exc:
            logger.error("Failed to ingest %s %d R%s: %s",
                         race_data.get("raceName", "?"), year, race_data.get("round", "?"), exc)

    logger.info("Ingested %d/%d races for %d", count, len(races), year)
    return count


def _ingest_single_race(year: int, race_data: dict, client: JolpicaClient) -> None:
    """Ingest one race's results, qualifying, standings, and pit stops."""
    round_num = int(race_data["round"])
    race_id = f"{year}_{round_num}"
    circuit_data = race_data.get("Circuit", {})
    circuit_id = circuit_data.get("circuitId", "")

    with get_connection() as conn:
        # ── Race ────────────────────────────────────────────────────
        upsert_race(conn, {
            "race_id": race_id,
            "year": year,
            "round": round_num,
            "circuit_id": _circuit_key(circuit_id),
            "circuit_name": circuit_data.get("circuitName", ""),
            "country": circuit_data.get("Location", {}).get("country", ""),
            "race_date": race_data.get("date", ""),
            "total_laps": None,
        })

        # ── Results ─────────────────────────────────────────────────
        for result in race_data.get("Results", []):
            driver = result.get("Driver", {})
            constructor = result.get("Constructor", {})
            driver_id = driver.get("driverId", "")
            constructor_id = constructor.get("constructorId", "")

            upsert_driver(conn, {
                "driver_id": driver_id,
                "code": driver.get("code", ""),
                "full_name": f"{driver.get('givenName', '')} {driver.get('familyName', '')}".strip(),
                "nationality": driver.get("nationality", ""),
            })

            upsert_constructor(conn, {
                "constructor_id": constructor_id,
                "name": constructor.get("name", ""),
                "nationality": constructor.get("nationality", ""),
            })

            pos_text = result.get("positionText", "")
            pos = _safe_int(result.get("position"))
            upsert_result(conn, {
                "race_id": race_id,
                "driver_id": driver_id,
                "constructor_id": constructor_id,
                "grid": _safe_int(result.get("grid")),
                "position": pos,
                "position_text": pos_text,
                "status": result.get("status", ""),
                "points": _safe_float(result.get("points")),
                "laps_completed": _safe_int(result.get("laps")),
                "fastest_lap_rank": _safe_int(
                    result.get("FastestLap", {}).get("rank") if result.get("FastestLap") else None
                ),
                "is_podium": 1 if pos and pos <= 3 else 0,
            })

    # ── Qualifying ──────────────────────────────────────────────────
    _ingest_qualifying(year, round_num, race_id, client)

    # ── Standings snapshot (before this race) ───────────────────────
    _ingest_standings(year, round_num, race_id, client)

    # ── Pit stops ───────────────────────────────────────────────────
    _ingest_pit_stops(year, round_num, race_id, client)


def _ingest_qualifying(year: int, round_num: int, race_id: str, client: JolpicaClient) -> None:
    """Ingest qualifying results for a race."""
    try:
        quali_races = client.get_qualifying(year, round_num)
    except Exception as exc:
        logger.warning("No qualifying data for %s: %s", race_id, exc)
        return

    if not quali_races:
        return

    with get_connection() as conn:
        for result in quali_races[0].get("QualifyingResults", []):
            driver_id = result.get("Driver", {}).get("driverId", "")
            constructor_id = result.get("Constructor", {}).get("constructorId", "")
            upsert_qualifying(conn, {
                "race_id": race_id,
                "driver_id": driver_id,
                "constructor_id": constructor_id,
                "position": _safe_int(result.get("position")),
                "q1_sec": _parse_lap_time(result.get("Q1")),
                "q2_sec": _parse_lap_time(result.get("Q2")),
                "q3_sec": _parse_lap_time(result.get("Q3")),
            })


def _ingest_standings(year: int, round_num: int, race_id: str, client: JolpicaClient) -> None:
    """Ingest championship standings snapshot before a race."""
    # Use previous round's standings as the "before race" snapshot
    prev_round = round_num - 1
    if prev_round < 1:
        return  # No standings before first race

    try:
        driver_standings = client.get_driver_standings(year, prev_round)
        constructor_standings = client.get_constructor_standings(year, prev_round)
    except Exception as exc:
        logger.warning("No standings for %s R%d: %s", year, prev_round, exc)
        return

    # Build constructor standings lookup
    constructor_lookup: dict[str, tuple[float, int]] = {}
    for cs in constructor_standings:
        cid = cs.get("Constructor", {}).get("constructorId", "")
        constructor_lookup[cid] = (
            _safe_float(cs.get("points")),
            _safe_int(cs.get("position")),
        )

    with get_connection() as conn:
        for ds in driver_standings:
            driver_id = ds.get("Driver", {}).get("driverId", "")
            # Jolpica returns Constructors as a list
            constructors = ds.get("Constructors", [])
            cid = constructors[0].get("constructorId", "") if constructors else ""
            c_pts, c_pos = constructor_lookup.get(cid, (None, None))

            upsert_standings(conn, {
                "race_id": race_id,
                "driver_id": driver_id,
                "points": _safe_float(ds.get("points")),
                "position": _safe_int(ds.get("position")),
                "constructor_id": cid,
                "constructor_pts": c_pts,
                "constructor_pos": c_pos,
            })


def _ingest_pit_stops(year: int, round_num: int, race_id: str, client: JolpicaClient) -> None:
    """Ingest pit stop data for a race."""
    try:
        pit_stops = client.get_pit_stops(year, round_num)
    except Exception as exc:
        logger.warning("No pit stop data for %s: %s", race_id, exc)
        return

    with get_connection() as conn:
        for pit in pit_stops:
            upsert_pit_stop(conn, {
                "race_id": race_id,
                "driver_id": pit.get("driverId", ""),
                "stop_number": _safe_int(pit.get("stop")),
                "lap": _safe_int(pit.get("lap")),
                "duration_sec": _safe_float(pit.get("duration")),
            })


def _safe_int(val: Any) -> int | None:
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _safe_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None
