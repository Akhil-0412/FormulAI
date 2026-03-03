"""SQLite database layer — schema + CRUD operations for race history."""

from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

import pandas as pd

from config.settings import settings

logger = logging.getLogger(__name__)

# ── Schema DDL ──────────────────────────────────────────────────────────

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS races (
    race_id         TEXT PRIMARY KEY,   -- "{year}_{round}"
    year            INTEGER NOT NULL,
    round           INTEGER NOT NULL,
    circuit_id      TEXT,
    circuit_name    TEXT,
    country         TEXT,
    race_date       TEXT,
    total_laps      INTEGER,
    UNIQUE(year, round)
);

CREATE TABLE IF NOT EXISTS drivers (
    driver_id       TEXT PRIMARY KEY,   -- e.g. "max_verstappen"
    code            TEXT,               -- e.g. "VER"
    full_name       TEXT,
    nationality     TEXT
);

CREATE TABLE IF NOT EXISTS constructors (
    constructor_id  TEXT PRIMARY KEY,
    name            TEXT,
    nationality     TEXT
);

CREATE TABLE IF NOT EXISTS results (
    race_id         TEXT NOT NULL,
    driver_id       TEXT NOT NULL,
    constructor_id  TEXT,
    grid            INTEGER,
    position        INTEGER,            -- NULL = DNF/DNS
    position_text   TEXT,               -- "1", "2", ..., "Ret", "DNS"
    status          TEXT,
    points          REAL,
    laps_completed  INTEGER,
    fastest_lap_rank INTEGER,
    is_podium       INTEGER DEFAULT 0,  -- 1 if position IN (1,2,3)
    PRIMARY KEY (race_id, driver_id),
    FOREIGN KEY (race_id) REFERENCES races(race_id),
    FOREIGN KEY (driver_id) REFERENCES drivers(driver_id)
);

CREATE TABLE IF NOT EXISTS qualifying (
    race_id         TEXT NOT NULL,
    driver_id       TEXT NOT NULL,
    constructor_id  TEXT,
    position        INTEGER,
    q1_sec          REAL,
    q2_sec          REAL,
    q3_sec          REAL,
    PRIMARY KEY (race_id, driver_id),
    FOREIGN KEY (race_id) REFERENCES races(race_id)
);

CREATE TABLE IF NOT EXISTS practice_sessions (
    race_id         TEXT NOT NULL,
    driver_id       TEXT NOT NULL,
    session_type    TEXT NOT NULL,       -- "FP1", "FP2", "FP3"
    best_lap_sec    REAL,
    avg_lap_sec     REAL,
    laps_completed  INTEGER,
    PRIMARY KEY (race_id, driver_id, session_type),
    FOREIGN KEY (race_id) REFERENCES races(race_id)
);

CREATE TABLE IF NOT EXISTS pit_stops (
    race_id         TEXT NOT NULL,
    driver_id       TEXT NOT NULL,
    stop_number     INTEGER NOT NULL,
    lap             INTEGER,
    duration_sec    REAL,
    PRIMARY KEY (race_id, driver_id, stop_number),
    FOREIGN KEY (race_id) REFERENCES races(race_id)
);

CREATE TABLE IF NOT EXISTS weather (
    race_id             TEXT PRIMARY KEY,
    temperature         REAL,
    precipitation_prob  REAL,
    wind_speed          REAL,
    humidity            REAL,
    condition           TEXT,
    FOREIGN KEY (race_id) REFERENCES races(race_id)
);

CREATE TABLE IF NOT EXISTS standings_snapshot (
    race_id         TEXT NOT NULL,
    driver_id       TEXT NOT NULL,
    points          REAL,
    position        INTEGER,
    constructor_id  TEXT,
    constructor_pts REAL,
    constructor_pos INTEGER,
    PRIMARY KEY (race_id, driver_id),
    FOREIGN KEY (race_id) REFERENCES races(race_id)
);

CREATE INDEX IF NOT EXISTS idx_results_race ON results(race_id);
CREATE INDEX IF NOT EXISTS idx_results_driver ON results(driver_id);
CREATE INDEX IF NOT EXISTS idx_qualifying_race ON qualifying(race_id);
CREATE INDEX IF NOT EXISTS idx_standings_race ON standings_snapshot(race_id);
"""


# ── Connection management ───────────────────────────────────────────────

def _db_path() -> Path:
    path = settings.abs_db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


@contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    """Context manager returning a SQLite connection with WAL mode."""
    conn = sqlite3.connect(str(_db_path()))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create all tables if they don't exist."""
    with get_connection() as conn:
        conn.executescript(_SCHEMA_SQL)
    logger.info("Database initialised at %s", _db_path())


# ── Insert helpers ──────────────────────────────────────────────────────

def upsert_race(conn: sqlite3.Connection, race: dict[str, Any]) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO races
           (race_id, year, round, circuit_id, circuit_name, country, race_date, total_laps)
           VALUES (:race_id, :year, :round, :circuit_id, :circuit_name, :country, :race_date, :total_laps)""",
        race,
    )


def upsert_driver(conn: sqlite3.Connection, driver: dict[str, Any]) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO drivers
           (driver_id, code, full_name, nationality)
           VALUES (:driver_id, :code, :full_name, :nationality)""",
        driver,
    )


def upsert_constructor(conn: sqlite3.Connection, constructor: dict[str, Any]) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO constructors
           (constructor_id, name, nationality)
           VALUES (:constructor_id, :name, :nationality)""",
        constructor,
    )


def upsert_result(conn: sqlite3.Connection, result: dict[str, Any]) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO results
           (race_id, driver_id, constructor_id, grid, position, position_text,
            status, points, laps_completed, fastest_lap_rank, is_podium)
           VALUES (:race_id, :driver_id, :constructor_id, :grid, :position,
                   :position_text, :status, :points, :laps_completed,
                   :fastest_lap_rank, :is_podium)""",
        result,
    )


def upsert_qualifying(conn: sqlite3.Connection, quali: dict[str, Any]) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO qualifying
           (race_id, driver_id, constructor_id, position, q1_sec, q2_sec, q3_sec)
           VALUES (:race_id, :driver_id, :constructor_id, :position, :q1_sec, :q2_sec, :q3_sec)""",
        quali,
    )


def upsert_pit_stop(conn: sqlite3.Connection, pit: dict[str, Any]) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO pit_stops
           (race_id, driver_id, stop_number, lap, duration_sec)
           VALUES (:race_id, :driver_id, :stop_number, :lap, :duration_sec)""",
        pit,
    )


def upsert_weather(conn: sqlite3.Connection, weather: dict[str, Any]) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO weather
           (race_id, temperature, precipitation_prob, wind_speed, humidity, condition)
           VALUES (:race_id, :temperature, :precipitation_prob, :wind_speed, :humidity, :condition)""",
        weather,
    )


def upsert_standings(conn: sqlite3.Connection, standing: dict[str, Any]) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO standings_snapshot
           (race_id, driver_id, points, position, constructor_id, constructor_pts, constructor_pos)
           VALUES (:race_id, :driver_id, :points, :position,
                   :constructor_id, :constructor_pts, :constructor_pos)""",
        standing,
    )


def upsert_practice(conn: sqlite3.Connection, practice: dict[str, Any]) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO practice_sessions
           (race_id, driver_id, session_type, best_lap_sec, avg_lap_sec, laps_completed)
           VALUES (:race_id, :driver_id, :session_type, :best_lap_sec, :avg_lap_sec, :laps_completed)""",
        practice,
    )


# ── Query helpers ───────────────────────────────────────────────────────

def query_df(sql: str, params: tuple = ()) -> pd.DataFrame:
    """Run a SELECT query and return a Pandas DataFrame."""
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn, params=params)


def get_driver_recent_results(driver_id: str, before_race_id: str, n: int = 5) -> pd.DataFrame:
    """Get a driver's last N race results before a given race."""
    return query_df(
        """SELECT r.race_id, r.year, r.round, res.position, res.grid, res.is_podium, res.status
           FROM results res
           JOIN races r ON res.race_id = r.race_id
           WHERE res.driver_id = ?
             AND r.race_id < ?
           ORDER BY r.year DESC, r.round DESC
           LIMIT ?""",
        (driver_id, before_race_id, n),
    )


def get_driver_circuit_history(driver_id: str, circuit_id: str) -> pd.DataFrame:
    """Get a driver's historical results at a specific circuit."""
    return query_df(
        """SELECT r.race_id, r.year, res.position, res.grid, res.is_podium
           FROM results res
           JOIN races r ON res.race_id = r.race_id
           WHERE res.driver_id = ? AND r.circuit_id = ?
           ORDER BY r.year""",
        (driver_id, circuit_id),
    )


def get_constructor_dnf_rate(constructor_id: str, last_n_races: int = 20) -> float:
    """Calculate DNF rate for a constructor over last N race entries."""
    df = query_df(
        """SELECT res.status
           FROM results res
           JOIN races r ON res.race_id = r.race_id
           WHERE res.constructor_id = ?
           ORDER BY r.year DESC, r.round DESC
           LIMIT ?""",
        (constructor_id, last_n_races),
    )
    if df.empty:
        return 0.0
    finished = df["status"].apply(lambda s: s == "Finished" or (s and s.startswith("+"))).sum()
    return 1.0 - (finished / len(df))
