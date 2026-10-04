"""Regression gate — the model must beat the qualifying sheet.

About 69% of podium finishers start in the top 3 grid slots, so "predict the
three fastest qualifiers" is a strong heuristic. A learned model that scores
below it is not adding value over a single column of the input.

The model side is read from the walk-forward backtest file written by
`scripts/rolling_backtest.py`, i.e. genuinely out-of-sample picks (each race
predicted by a model trained only on earlier races). The previous gate
scored the saved production model on a season that model had been trained
on, which made the comparison meaningless. Baselines are scored on exactly
the same races.

Exits non-zero when the model falls short of the best baseline (unless
--warn-only), so this can run as a CI step.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from features.fast_features import build_training_frame

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent

# Heuristics to beat: column -> (label, ascending)
BASELINES = {
    "grid_pos": ("top 3 on the grid", True),
    "q_gap_pct": ("smallest quali gap to pole", True),
    "d_season_pts": ("top 3 in championship", False),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, default=datetime.now().year,
                        help="Season whose backtest file to check")
    parser.add_argument("--tolerance", type=float, default=0.0,
                        help="Allowed shortfall vs the best baseline, in podium slots")
    parser.add_argument("--warn-only", action="store_true", help="Report but always exit 0")
    args = parser.parse_args()

    path = ROOT / "data" / f"rolling_backtest_{args.season}.json"
    if not path.exists():
        logger.error("No backtest file %s; run scripts/rolling_backtest.py first.", path)
        return 0 if args.warn_only else 1
    scored = [e for e in json.loads(path.read_text()) if e.get("correct", -1) >= 0]
    if not scored:
        logger.warning("No completed races in %s; skipping gate.", path.name)
        return 0
    rounds = {int(e["round"]) for e in scored}
    model_score = float(np.mean([e["correct"] for e in scored]))

    frame = build_training_frame(args.season, args.season)
    frame = frame[frame["round"].isin(rounds)]
    results = []
    for col, (label, asc) in BASELINES.items():
        per_race = []
        for _, race in frame.groupby("race_id"):
            if race[col].isna().all():
                continue
            picks = race.sort_values(col, ascending=asc, na_position="last").head(3)
            per_race.append(int((picks["finish_position"] <= 3).sum()))
        if per_race:
            results.append((label, float(np.mean(per_race))))

    print()
    print(f"{'approach':<34}{'avg correct / 3':>18}   ({len(scored)} races, {args.season})")
    print("-" * 52)
    print(f"{'MODEL (walk-forward)':<34}{model_score:>18.4f}")
    for label, score in sorted(results, key=lambda kv: -kv[1]):
        print(f"{'  baseline: ' + label:<34}{score:>18.4f}")
    print("-" * 52)

    if not results:
        logger.warning("No baseline could be computed; skipping gate.")
        return 0
    best_label, best_score = max(results, key=lambda kv: kv[1])
    margin = model_score - best_score
    if margin >= -args.tolerance:
        logger.info("PASS: model %+.4f vs best baseline (%s)", margin, best_label)
        return 0
    logger.error(
        "FAIL: model scores %.4f, below '%s' at %.4f (short by %.4f).",
        model_score, best_label, best_score, -margin,
    )
    return 0 if args.warn_only else 1


if __name__ == "__main__":
    raise SystemExit(main())
