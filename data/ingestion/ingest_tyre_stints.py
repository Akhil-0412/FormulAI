"""Ingestion script to backfill tyre stints."""

import logging
from config.settings import settings
from data.db import get_connection, upsert_tyre_stint
from data.fastf1_client import get_tyre_stints, get_season_schedule

logger = logging.getLogger(__name__)

def ingest_tyre_stints_for_race(year: int, round_number: int, race_id: str) -> None:
    """Fetch and ingest tyre stints for a specific race."""
    df = get_tyre_stints(year, round_number)
    if df.empty:
        logger.info(f"No tyre stints found for {race_id}")
        return

    with get_connection() as conn:
        for _, row in df.iterrows():
            stint = {
                "race_id": race_id,
                "driver_id": str(row.get("DriverNumber")),
                "stint_number": int(row.get("Stint")),
                "compound": str(row.get("Compound")),
                "lap_start": int(row.get("LapStart")),
                "lap_end": int(row.get("LapEnd")),
                "tyre_age": int(row.get("TyreAge", 0)),
                "avg_deg_rate": 0.0 # Will be computed later or by deg model
            }
            upsert_tyre_stint(conn, stint)
    logger.info(f"Ingested {len(df)} tyre stints for {race_id}")

def backfill_tyre_stints(start_year: int = 2018, end_year: int = 2024):
    """Backfill tyre stints for a range of years."""
    for year in range(start_year, end_year + 1):
        schedule = get_season_schedule(year)
        for _, event in schedule.iterrows():
            round_num = event["RoundNumber"]
            race_id = f"{year}_{round_num}"
            try:
                ingest_tyre_stints_for_race(year, round_num, race_id)
            except Exception as e:
                logger.error(f"Failed to ingest tyre stints for {race_id}: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    backfill_tyre_stints()
