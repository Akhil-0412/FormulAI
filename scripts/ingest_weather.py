"""Backfill observed race-day weather into the `weather` table.

The table has always existed, along with `upsert_weather()` and the reader in
`features/weather_features.py` — only the writer was missing, which left
`track_temp_c`, `rain_prob`, `humidity_pct`, `wind_speed_ms` and
`wet_race_probability` frozen at placeholder constants for every race.

Uses Open-Meteo's archive service (free, no key) and aggregates over the local
race window rather than the whole day.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.db import get_connection, init_db, query_df, upsert_weather
from data.weather_client import WeatherClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# Open-Meteo asks for courtesy pacing on the free tier.
_REQUEST_INTERVAL = 0.2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-year", type=int, default=2014)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--overwrite", action="store_true",
                        help="Refetch races that already have a weather row")
    args = parser.parse_args()

    init_db()

    races = query_df(
        """SELECT r.race_id, r.circuit_id, r.race_date
           FROM races r
           WHERE r.race_date IS NOT NULL
             AND CAST(substr(r.race_id, 1, 4) AS INTEGER) BETWEEN ? AND ?
           ORDER BY r.year, r.round""",
        (args.start_year, args.end_year),
    )
    if races.empty:
        logger.error("No races found in range — run ingestion first.")
        return 1

    existing: set[str] = set()
    if not args.overwrite:
        have = query_df("SELECT race_id FROM weather")
        existing = set(have["race_id"]) if not have.empty else set()
        if existing:
            logger.info("Skipping %d races that already have weather.", len(existing))

    client = WeatherClient()
    written = skipped = failed = 0
    unknown_circuits: set[str] = set()

    try:
        for row in races.itertuples(index=False):
            race_id = row.race_id
            if race_id in existing:
                skipped += 1
                continue

            circuit_id = row.circuit_id or ""
            if client.get_circuit_info(circuit_id) is None:
                unknown_circuits.add(circuit_id)
                failed += 1
                continue

            try:
                w = client.get_historical(circuit_id, str(row.race_date))
            except Exception as exc:
                logger.warning("Fetch failed for %s: %s", race_id, exc)
                failed += 1
                continue

            if w.get("temperature") is None:
                logger.warning("No usable data for %s (%s)", race_id, circuit_id)
                failed += 1
                continue

            with get_connection() as conn:
                upsert_weather(conn, {
                    "race_id": race_id,
                    "temperature": w["temperature"],
                    "precipitation_prob": w["precipitation_prob"],
                    "wind_speed": w["wind_speed"],
                    "humidity": w["humidity"],
                    "condition": w["condition"],
                })
            written += 1
            if written % 25 == 0:
                logger.info("  %d races written...", written)
            time.sleep(_REQUEST_INTERVAL)
    finally:
        client.close()

    logger.info("=== weather backfill: %d written, %d skipped, %d failed ===",
                written, skipped, failed)
    if unknown_circuits:
        logger.warning("Circuits missing from circuits.json: %s",
                       ", ".join(sorted(unknown_circuits)))

    wet = query_df(
        "SELECT COUNT(*) AS n FROM weather WHERE precipitation_prob > 0.5")
    total = query_df("SELECT COUNT(*) AS n FROM weather")
    if not total.empty and total.iloc[0]["n"]:
        n_wet, n_all = int(wet.iloc[0]["n"]), int(total.iloc[0]["n"])
        logger.info("Wet races (>50%% of race window raining): %d / %d (%.1f%%)",
                    n_wet, n_all, 100.0 * n_wet / n_all)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
