"""Ingestion script to backfill lap data for GRU training."""

import logging
from config.settings import settings
from data.db import get_connection, upsert_lap_data
from data.fastf1_client import get_race_laps, get_season_schedule

logger = logging.getLogger(__name__)

def ingest_lap_data_for_race(year: int, round_number: int, race_id: str) -> None:
    """Fetch and ingest per-lap telemetry for a specific race."""
    df = get_race_laps(year, round_number)
    if df.empty:
        logger.info(f"No lap data found for {race_id}")
        return

    with get_connection() as conn:
        for _, row in df.iterrows():
            lap = {
                "race_id": race_id,
                "driver_id": str(row.get("DriverNumber")),
                "lap_number": int(row.get("LapNumber", 0)),
                "lap_time_ms": int(row.get("LapTimeSec", 0) * 1000) if row.get("LapTimeSec") else 0,
                "position": int(row.get("Position", 0)),
                "gap_to_leader_ms": 0, # Should be calculated
                "pit_in": 1 if row.get("PitInTime") else 0,
                "pit_out": 1 if row.get("PitOutTime") else 0,
                "sc_active": 1 if "TrackStatus" in row and ("4" in str(row["TrackStatus"])) else 0,
                "vsc_active": 1 if "TrackStatus" in row and ("6" in str(row["TrackStatus"])) else 0,
                "compound": str(row.get("Compound")),
                "tyre_age": int(row.get("TyreLife", 0))
            }
            upsert_lap_data(conn, lap)
    logger.info(f"Ingested {len(df)} lap records for {race_id}")

def backfill_lap_data(start_year: int = 2020, end_year: int = 2024):
    """Backfill lap data for a range of years."""
    for year in range(start_year, end_year + 1):
        schedule = get_season_schedule(year)
        for _, event in schedule.iterrows():
            round_num = event["RoundNumber"]
            race_id = f"{year}_{round_num}"
            try:
                ingest_lap_data_for_race(year, round_num, race_id)
            except Exception as e:
                logger.error(f"Failed to ingest lap data for {race_id}: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    backfill_lap_data()
