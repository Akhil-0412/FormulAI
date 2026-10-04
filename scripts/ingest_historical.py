"""CLI script — Ingest historical F1 data into the local database."""

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.db import get_connection, init_db
from data.ingest import IncompleteSeasonError, ingest_season
from data.jolpica_client import JolpicaClient, RateLimitExhausted

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ── Season log ──────────────────────────────────────────────────────────
# A season is recorded here only after an ingest in which every API call
# succeeded. --incremental skips recorded past seasons, so a cold start that
# hits Jolpica's rate limit (it allows a few hundred calls per hour, a full
# 2014→now ingest needs ~1,200) resumes where it stopped on the next run
# instead of starting over or mistaking a half-ingested season for done.

def _ensure_ingest_log(current_year: int) -> None:
    with get_connection() as conn:
        existed = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'ingest_log'"
        ).fetchone()
        conn.execute(
            "CREATE TABLE IF NOT EXISTS ingest_log (year INTEGER PRIMARY KEY, completed_at TEXT)"
        )
        if not existed:
            # A database built before this log existed: trust the past
            # seasons it already holds rather than re-downloading them all.
            conn.execute(
                """INSERT OR IGNORE INTO ingest_log (year, completed_at)
                   SELECT DISTINCT r.year, 'adopted' FROM races r
                   JOIN results res ON res.race_id = r.race_id WHERE r.year < ?""",
                (current_year,),
            )


def _season_logged(year: int) -> bool:
    with get_connection() as conn:
        return conn.execute("SELECT 1 FROM ingest_log WHERE year = ?", (year,)).fetchone() is not None


def _log_season(year: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO ingest_log (year, completed_at) VALUES (?, ?)",
            (year, datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest historical and current F1 data")
    parser.add_argument("--start-year", type=int, default=2018, help="First season to ingest")
    parser.add_argument("--end-year", type=int, help="Last season to ingest (if not using --latest)")
    parser.add_argument("--latest", action="store_true", help="Ingest up to the current calendar year")
    parser.add_argument("--year", type=int, help="Single year to ingest (overrides start/end)")
    parser.add_argument("--incremental", action="store_true",
                        help="Skip past seasons already fully ingested; always refresh the current one")
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
    _ensure_ingest_log(current_year)
    total = 0
    unfinished: list[int] = []
    for year in range(start, end + 1):
        if args.incremental and year < current_year and _season_logged(year):
            logger.info("=== %d already ingested, skipping (incremental) ===", year)
            continue
        logger.info("=== Ingesting %d ===", year)
        try:
            total += ingest_season(year, client)
            _log_season(year)
        except IncompleteSeasonError as exc:
            logger.warning("Season incomplete, will retry next run: %s", exc)
            unfinished.append(year)
        except RateLimitExhausted:
            logger.warning("Jolpica rate limit reached; %d onwards will be ingested next run.", year)
            unfinished.extend(range(year, end + 1))
            break
        except Exception as exc:
            logger.error("Failed to ingest %d: %s", year, exc)
            unfinished.append(year)

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

    if unfinished:
        logger.error("Data incomplete for %s. Not safe to retrain or publish from this database.",
                     ", ".join(map(str, sorted(set(unfinished)))))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
