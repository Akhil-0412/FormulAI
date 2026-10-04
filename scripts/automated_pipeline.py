"""Automated pipeline — backtest the season, retrain, forecast the next race.

Run after ingestion (see .github/workflows/f1_pipeline.yml):

1. `rolling_backtest.py --test-year <now> --save-model` re-scores every
   completed round walk-forward, refits the production model on all data,
   saves it, and forecasts the next race without results.
2. The forecast is also written to frontend/public/data/latest_prediction.json.

The previous version predicted `MAX(round)` from the races table — the last
race that had already been run, not the next one.
"""

import json
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    year = datetime.now(timezone.utc).year
    logger.info("Backtesting %d, retraining and forecasting the next race...", year)
    try:
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "rolling_backtest.py"),
             "--test-year", str(year), "--save-model"],
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        logger.error("Rolling backtest failed: %s", exc)
        return 1

    entries = json.loads((ROOT / "data" / f"rolling_backtest_{year}.json").read_text())
    forecast = next((e for e in entries if e.get("is_future")), None)
    if forecast is None:
        logger.info("No upcoming race in %d: nothing to forecast.", year)
        return 0

    scored = [e for e in entries if e.get("correct", -1) >= 0]
    payload = {
        "season": year,
        "data_through": forecast.get("data_through"),
        "model_version": "4.0.0",
        "race": {k: forecast.get(k) for k in ("round", "race_name", "grand_prix", "date")},
        "regime": forecast.get("regime"),
        "podium": forecast.get("predicted", []),
        "podium_probabilities": forecast.get("probabilities", {}),
        "win_probabilities": forecast.get("win_probabilities", {}),
        "season_backtest": {
            "races": len(scored),
            "avg_correct_out_of_3": round(sum(e["correct"] for e in scored) / len(scored), 3) if scored else None,
        },
    }
    out = ROOT / "frontend" / "public" / "data" / "latest_prediction.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2))
    logger.info("Wrote %s (%s, %s)", out, forecast.get("race_name"), forecast.get("regime"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
