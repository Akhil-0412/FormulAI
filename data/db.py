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

CREATE TABLE IF NOT EXISTS predictions (
    race_id         TEXT PRIMARY KEY,
    predicted_podium TEXT,
    actual_podium   TEXT,
    accuracy_score  REAL,
    processed_at    TEXT,
    FOREIGN KEY (race_id) REFERENCES races(race_id)
);

CREATE INDEX IF NOT EXISTS idx_results_race ON results(race_id);
CREATE INDEX IF NOT EXISTS idx_results_driver ON results(driver_id);
CREATE INDEX IF NOT EXISTS idx_qualifying_race ON qualifying(race_id);
CREATE INDEX IF NOT EXISTS idx_standings_race ON standings_snapshot(race_id);

CREATE TABLE IF NOT EXISTS tyre_stints (
    race_id         TEXT NOT NULL,
    driver_id       TEXT NOT NULL,
    stint_number    INTEGER NOT NULL,
    compound        TEXT,
    lap_start       INTEGER,
    lap_end         INTEGER,
    tyre_age        INTEGER,
    avg_deg_rate    REAL,
    PRIMARY KEY (race_id, driver_id, stint_number),
    FOREIGN KEY (race_id) REFERENCES races(race_id)
);

CREATE TABLE IF NOT EXISTS lap_data (
    race_id         TEXT NOT NULL,
    driver_id       TEXT NOT NULL,
    lap_number      INTEGER NOT NULL,
    lap_time_ms     INTEGER,
    position        INTEGER,
    gap_to_leader_ms INTEGER,
    pit_in          INTEGER DEFAULT 0,
    pit_out         INTEGER DEFAULT 0,
    sc_active       INTEGER DEFAULT 0,
    vsc_active      INTEGER DEFAULT 0,
    compound        TEXT,
    tyre_age        INTEGER,
    PRIMARY KEY (race_id, driver_id, lap_number),
    FOREIGN KEY (race_id) REFERENCES races(race_id)
);

CREATE TABLE IF NOT EXISTS constructor_reliability (
    constructor_id  TEXT NOT NULL,
    race_id         TEXT NOT NULL,
    dnf_rate_rolling5 REAL,
    reliability_trend REAL,
    PRIMARY KEY (constructor_id, race_id)
);

CREATE TABLE IF NOT EXISTS circuit_meta (
    circuit_id      TEXT PRIMARY KEY,
    tyre_stress_index REAL,
    sc_probability  REAL,
    vsc_probability REAL,
    overtake_difficulty REAL,
    drs_zones       INTEGER,
    avg_pit_delta_s REAL,
    undercut_window_laps INTEGER,
    is_street_circuit INTEGER
);

CREATE TABLE IF NOT EXISTS fp2_long_runs (
    race_id         TEXT NOT NULL,
    driver_id       TEXT NOT NULL,
    compound        TEXT NOT NULL,
    avg_pace_sec    REAL,
    deg_rate_ms_lap REAL,
    laps_in_run     INTEGER,
    PRIMARY KEY (race_id, driver_id, compound)
);

CREATE INDEX IF NOT EXISTS idx_tyre_stints_race ON tyre_stints(race_id, driver_id);
CREATE INDEX IF NOT EXISTS idx_lap_data_race ON lap_data(race_id, driver_id);
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


def upsert_prediction(conn: sqlite3.Connection, prediction: dict[str, Any]) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO predictions
           (race_id, predicted_podium, actual_podium, accuracy_score, processed_at)
           VALUES (:race_id, :predicted_podium, :actual_podium, :accuracy_score, :processed_at)""",
        prediction,
    )


def upsert_tyre_stint(conn: sqlite3.Connection, stint: dict[str, Any]) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO tyre_stints
           (race_id, driver_id, stint_number, compound, lap_start, lap_end, tyre_age, avg_deg_rate)
           VALUES (:race_id, :driver_id, :stint_number, :compound, :lap_start, :lap_end, :tyre_age, :avg_deg_rate)""",
        stint,
    )


def upsert_lap_data(conn: sqlite3.Connection, lap: dict[str, Any]) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO lap_data
           (race_id, driver_id, lap_number, lap_time_ms, position, gap_to_leader_ms,
            pit_in, pit_out, sc_active, vsc_active, compound, tyre_age)
           VALUES (:race_id, :driver_id, :lap_number, :lap_time_ms, :position, :gap_to_leader_ms,
                   :pit_in, :pit_out, :sc_active, :vsc_active, :compound, :tyre_age)""",
        lap,
    )


def upsert_constructor_reliability(conn: sqlite3.Connection, rel: dict[str, Any]) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO constructor_reliability
           (constructor_id, race_id, dnf_rate_rolling5, reliability_trend)
           VALUES (:constructor_id, :race_id, :dnf_rate_rolling5, :reliability_trend)""",
        rel,
    )


def upsert_circuit_meta(conn: sqlite3.Connection, meta: dict[str, Any]) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO circuit_meta
           (circuit_id, tyre_stress_index, sc_probability, vsc_probability,
            overtake_difficulty, drs_zones, avg_pit_delta_s, undercut_window_laps, is_street_circuit)
           VALUES (:circuit_id, :tyre_stress_index, :sc_probability, :vsc_probability,
                   :overtake_difficulty, :drs_zones, :avg_pit_delta_s, :undercut_window_laps, :is_street_circuit)""",
        meta,
    )


def upsert_fp2_long_run(conn: sqlite3.Connection, run: dict[str, Any]) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO fp2_long_runs
           (race_id, driver_id, compound, avg_pace_sec, deg_rate_ms_lap, laps_in_run)
           VALUES (:race_id, :driver_id, :compound, :avg_pace_sec, :deg_rate_ms_lap, :laps_in_run)""",
        run,
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


def get_driver_tyre_stints(driver_id: str, race_id: str) -> pd.DataFrame:
    """Get a driver's tyre stints for a specific race."""
    return query_df(
        """SELECT * FROM tyre_stints
           WHERE race_id = ? AND driver_id = ?
           ORDER BY stint_number""",
        (race_id, driver_id),
    )


def get_lap_sequence(race_id: str, driver_id: str) -> pd.DataFrame:
    """Get the sequence of laps for a driver in a race."""
    return query_df(
        """SELECT * FROM lap_data
           WHERE race_id = ? AND driver_id = ?
           ORDER BY lap_number""",
        (race_id, driver_id),
    )


def get_constructor_reliability_rolling(constructor_id: str, before_race_id: str) -> pd.DataFrame:
    """Get rolling constructor reliability up to a certain race."""
    return query_df(
        """SELECT cr.* FROM constructor_reliability cr
           JOIN races r ON cr.race_id = r.race_id
           WHERE cr.constructor_id = ? AND r.race_id < ?
           ORDER BY r.year DESC, r.round DESC LIMIT 1""",
        (constructor_id, before_race_id),
    )
