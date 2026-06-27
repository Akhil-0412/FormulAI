"""Ingestion script to backfill FP2 long runs."""

import logging
from config.settings import settings
from data.db import get_connection, upsert_fp2_long_run
from data.fastf1_client import get_fp2_long_runs, get_season_schedule

logger = logging.getLogger(__name__)

def ingest_fp2_long_runs_for_race(year: int, round_number: int, race_id: str) -> None:
    """Fetch and ingest FP2 long runs for a specific race."""
    df = get_fp2_long_runs(year, round_number)
    if df.empty:
        logger.info(f"No FP2 long runs found for {race_id}")
        return

    # Basic grouping for long runs
    # True logic would require filtering for consecutive laps without yellow flags
    runs = df.groupby(["DriverNumber", "Compound"]).agg(
        avg_pace_sec=("LapTimeSec", "mean"),
        laps_in_run=("LapNumber", "count")
    ).reset_index()

    runs = runs[runs["laps_in_run"] >= 5] # Minimum 5 laps

    with get_connection() as conn:
        for _, row in runs.iterrows():
            run = {
                "race_id": race_id,
                "driver_id": str(row.get("DriverNumber")),
                "compound": str(row.get("Compound")),
                "avg_pace_sec": float(row.get("avg_pace_sec", 0.0)),
                "deg_rate_ms_lap": 0.0, # Placeholder
                "laps_in_run": int(row.get("laps_in_run", 0))
            }
            upsert_fp2_long_run(conn, run)
    logger.info(f"Ingested {len(runs)} FP2 long runs for {race_id}")

def backfill_fp2_long_runs(start_year: int = 2018, end_year: int = 2024):
    """Backfill FP2 long runs for a range of years."""
    for year in range(start_year, end_year + 1):
        schedule = get_season_schedule(year)
        for _, event in schedule.iterrows():
            round_num = event["RoundNumber"]
            race_id = f"{year}_{round_num}"
            try:
                ingest_fp2_long_runs_for_race(year, round_num, race_id)
            except Exception as e:
                logger.error(f"Failed to ingest FP2 long runs for {race_id}: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    backfill_fp2_long_runs()
