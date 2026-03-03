"""CLI script — Ingest historical F1 data into the local database."""

import argparse
import logging
import sys
from pathlib import Path

from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.ingest import ingest_season
from data.jolpica_client import JolpicaClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest historical and current F1 data")
    parser.add_argument("--start-year", type=int, default=2018, help="First season to ingest")
    parser.add_argument("--end-year", type=int, help="Last season to ingest (if not using --latest)")
    parser.add_argument("--latest", action="store_true", help="Ingest up to the current calendar year")
    parser.add_argument("--year", type=int, help="Single year to ingest (overrides start/end)")
    args = parser.parse_args()

    client = JolpicaClient()

    if args.year:
        start, end = args.year, args.year
    else:
        start_year = args.start_year
        if args.latest:
            end_year = datetime.now().year
        else:
            end_year = args.end_year if args.end_year else 2024
        start, end = start_year, end_year

    total = 0
    for year in range(start, end + 1):
        logger.info("=== Ingesting %d ===", year)
        try:
            count = ingest_season(year, client)
            total += count
        except Exception as exc:
            logger.error("Failed to ingest %d: %s", year, exc)

    logger.info("=== Done: ingested %d total races ===", total)
    client.close()


if __name__ == "__main__":
    main()
