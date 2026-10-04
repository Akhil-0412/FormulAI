"""CLI script — Ingest historical F1 data into the local database."""

import argparse
import logging
import sys
from pathlib import Path

from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.db import init_db, query_df
from data.ingest import ingest_season
from data.jolpica_client import JolpicaClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


def _season_in_db(year: int) -> bool:
    df = query_df(
        "SELECT COUNT(DISTINCT r.race_id) AS n FROM races r "
        "JOIN results res ON res.race_id = r.race_id WHERE r.year = ?",
        (year,),
    )
    return int(df.iloc[0]["n"]) > 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest historical and current F1 data")
    parser.add_argument("--start-year", type=int, default=2018, help="First season to ingest")
    parser.add_argument("--end-year", type=int, help="Last season to ingest (if not using --latest)")
    parser.add_argument("--latest", action="store_true", help="Ingest up to the current calendar year")
    parser.add_argument("--year", type=int, help="Single year to ingest (overrides start/end)")
    parser.add_argument("--incremental", action="store_true",
                        help="Skip finished past seasons already in the DB; always refresh the current one")
    parser.add_argument("--evaluate", action="store_true",
                        help="Also run the legacy sequential evaluation (scripts/evaluate_races.py)")
    args = parser.parse_args()

    client = JolpicaClient()
    current_year = datetime.now().year

    if args.year:
        start, end = args.year, args.year
    else:
        start_year = args.start_year
        if args.latest:
            end_year = current_year
        else:
            end_year = args.end_year if args.end_year else 2024
        start, end = start_year, end_year

    init_db()
    total = 0
    for year in range(start, end + 1):
        if args.incremental and year < current_year and _season_in_db(year):
            logger.info("=== %d already in DB, skipping (incremental) ===", year)
            continue
        logger.info("=== Ingesting %d ===", year)
        try:
            count = ingest_season(year, client)
            total += count
        except Exception as exc:
            logger.error("Failed to ingest %d: %s", year, exc)

    logger.info("=== Done: ingested %d total races ===", total)
    client.close()

    if args.evaluate:
        logger.info("=== Running Sequential Evaluation ===")
        try:
            import scripts.evaluate_races as evaluate_races
            sys.argv = [sys.argv[0]]  # evaluate_races parses its own argv independently
            evaluate_races.main()
        except Exception as e:
            logger.error("Evaluation failed: %s", e)


if __name__ == "__main__":
    main()
