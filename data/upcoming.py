"""The next race to forecast — schedule, field and (if run) qualifying.

Nothing here is written to the database. The old forward-prediction path
inserted a fake race plus placeholder results (every driver "P10, Pending")
and deleted them afterwards; that briefly polluted the results table and,
because the placeholders had no grid, fed the model grid=20 for the entire
field — a pre-qualifying situation the model had never been trained on.
Now the race is described in memory and the right regime is chosen
explicitly: post-qualifying when Jolpica has the session, pre-qualifying
otherwise.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd

from data.db import query_df
from data.ingest import _circuit_key, _parse_lap_time, _safe_int
from data.jolpica_client import JolpicaClient

logger = logging.getLogger(__name__)


@dataclass
class UpcomingRace:
    race_id: str
    year: int
    round: int
    race_name: str
    circuit_id: str
    country: str
    date: str
    entries: pd.DataFrame          # race_id, driver_id, constructor_id, circuit_id, grid
    quali: pd.DataFrame | None     # qualifying rows when the session has run
    sprint: pd.DataFrame | None = None  # sprint finishing order on sprint weekends

    @property
    def has_qualifying(self) -> bool:
        return self.quali is not None and not self.quali.empty


def _completed_rounds(year: int) -> set[int]:
    df = query_df(
        "SELECT DISTINCT r.round FROM races r JOIN results res ON res.race_id = r.race_id "
        "WHERE r.year = ? AND res.status != 'Pending'",
        (year,),
    )
    return set(int(x) for x in df["round"])


def _latest_field(year: int) -> pd.DataFrame:
    """Driver/constructor pairs from the most recent completed race."""
    df = query_df(
        """SELECT res.driver_id, res.constructor_id FROM results res
           JOIN races r ON r.race_id = res.race_id
           WHERE r.year <= ? AND res.status != 'Pending'
             AND r.year * 100 + r.round = (
                 SELECT MAX(r2.year * 100 + r2.round) FROM races r2
                 JOIN results x ON x.race_id = r2.race_id
                 WHERE r2.year <= ? AND x.status != 'Pending')""",
        (year, year),
    )
    return df.drop_duplicates("driver_id")


def find_upcoming_race(year: int, client: JolpicaClient | None = None) -> UpcomingRace | None:
    """The first scheduled round of `year` whose results aren't in the DB."""
    own_client = client is None
    client = client or JolpicaClient()
    try:
        schedule = client.get_schedule(year)
        done = _completed_rounds(year)
        pending = [r for r in schedule if int(r["round"]) not in done]
        if not pending:
            return None
        nxt = min(pending, key=lambda r: int(r["round"]))
        rnd = int(nxt["round"])
        race_id = f"{year}_{rnd}"
        circuit = nxt.get("Circuit", {})
        circuit_id = _circuit_key(circuit.get("circuitId", ""))

        quali_rows = []
        try:
            q = client.get_qualifying(year, rnd)
            for row in (q[0].get("QualifyingResults", []) if q else []):
                quali_rows.append({
                    "race_id": race_id,
                    "driver_id": row.get("Driver", {}).get("driverId", ""),
                    "constructor_id": row.get("Constructor", {}).get("constructorId", ""),
                    "quali_pos": _safe_int(row.get("position")),
                    "q1_sec": _parse_lap_time(row.get("Q1")),
                    "q2_sec": _parse_lap_time(row.get("Q2")),
                    "q3_sec": _parse_lap_time(row.get("Q3")),
                })
        except Exception as exc:  # no session yet, or API hiccup
            logger.info("No qualifying for %s yet (%s)", race_id, exc)
        quali = pd.DataFrame(quali_rows) if quali_rows else None

        sprint = None
        if "Sprint" in nxt:
            try:
                s = client.get_sprint_results(year, rnd)
                rows = [{"race_id": race_id,
                         "driver_id": r.get("Driver", {}).get("driverId", ""),
                         "sprint_pos": _safe_int(r.get("position"))}
                        for r in (s[0].get("SprintResults", []) if s else [])]
                sprint = pd.DataFrame(rows) if rows else None
            except Exception as exc:
                logger.info("No sprint result for %s yet (%s)", race_id, exc)

        if quali is not None:
            entries = quali[["driver_id", "constructor_id"]].copy()
        else:
            entries = _latest_field(year)
        entries = entries.assign(race_id=race_id, circuit_id=circuit_id, grid=float("nan"))

        return UpcomingRace(
            race_id=race_id, year=year, round=rnd,
            race_name=nxt.get("raceName", f"Round {rnd}"),
            circuit_id=circuit_id,
            country=circuit.get("Location", {}).get("country", ""),
            date=nxt.get("date", ""),
            entries=entries[["race_id", "driver_id", "constructor_id", "circuit_id", "grid"]],
            quali=quali,
            sprint=sprint,
        )
    finally:
        if own_client:
            client.close()
