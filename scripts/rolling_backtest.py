"""CLI script — walk-forward season backtest + next-race forecast (v4).

For every completed race of the season the podium model is refit on all
races strictly before it and then predicts that race from post-qualifying
information — i.e. exactly the prediction it would have published on the
Saturday night. The probability temperature is calibrated once, on races
before the season starts, so nothing from the season leaks into it.

The next race without results is then forecast with a model trained on
everything to date — post-qualifying if Jolpica already has the session,
pre-qualifying otherwise. `--save-model` stores that model as the
production artifact used by the API.

Output (same schema the frontend reads, plus win probabilities/regime):
    data/rolling_backtest_{year}.json
    frontend/public/data/rolling_backtest_{year}.json
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import numpy as np
import pandas as pd
from scipy.stats import kendalltau

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.db import query_df
from features.fast_features import build_features, build_training_frame, clear_cache
from models_v2.podium_predictor import PodiumPredictor, members_from_config
from models_v2.training import _load_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIRS = [ROOT / "data", ROOT / "frontend" / "public" / "data"]


def _evaluate(pred: pd.DataFrame, race: pd.DataFrame) -> dict:
    actual = race.sort_values("finish_position")
    actual_podium = actual["driver_id"].head(3).tolist()
    picks = pred["driver_id"].head(3).tolist()
    correct = len(set(picks) & set(actual_podium))

    finish = race.set_index("driver_id")["finish_position"]
    y = pred["driver_id"].map(lambda d: float(finish.get(d, 99) <= 3)).to_numpy()
    p = pred["p_podium"].to_numpy()
    rel = pred["driver_id"].map(lambda d: {1: 25, 2: 18, 3: 15}.get(int(finish.get(d, 99)), 0)).to_numpy()
    dcg = (rel[:3] / np.log2(np.arange(2, 5))).sum()
    idcg = (np.sort(rel)[::-1][:3] / np.log2(np.arange(2, 5))).sum()
    tau, _ = kendalltau(pred["predicted_rank"], pred["driver_id"].map(finish).to_numpy())
    return {
        "predicted": picks,
        "actual": actual_podium,
        "correct": int(correct),
        "winner_correct": bool(picks[0] == actual_podium[0]) if actual_podium else False,
        "brier_score": float(np.mean((p - y) ** 2)),
        "ndcg_at_3": float(dcg / idcg) if idcg > 0 else 0.0,
        "kendall_tau": float(tau) if tau == tau else 0.0,
        "top3_precision": correct / 3.0,
    }


def _prob_maps(pred: pd.DataFrame) -> tuple[dict, dict]:
    podium = {d: round(float(p), 4) for d, p in zip(pred["driver_id"], pred["p_podium"])}
    win = {d: round(float(p), 4) for d, p in zip(pred["driver_id"], pred["p_win"])}
    return podium, win


def forecast_next(model: PodiumPredictor, year: int) -> dict | None:
    """Forecast the first round of `year` that has no results yet."""
    from data.upcoming import find_upcoming_race

    try:
        up = find_upcoming_race(year)
    except Exception as exc:
        logger.warning("Could not fetch the %d schedule: %s", year, exc)
        return None
    if up is None:
        logger.info("No upcoming race left in %d", year)
        return None

    feats = build_features(up.entries, extra_quali=up.quali, extra_sprint=up.sprint)
    regime = "post" if up.has_qualifying else "pre"
    pred = model.predict(feats, regime=regime)
    podium, win = _prob_maps(pred)
    entry = {
        "round": up.round,
        "race_name": f"{up.country} GP (R{up.round})",
        "grand_prix": up.race_name,
        "date": up.date,
        "predicted": pred["driver_id"].head(3).tolist(),
        "actual": [],
        "correct": -1,
        "brier_score": -1,
        "ndcg_at_3": -1,
        "probabilities": podium,
        "win_probabilities": win,
        "regime": "post-qualifying" if regime == "post" else "pre-qualifying",
        "is_future": True,
        # Deterministic (no wall-clock timestamp) so the 6-hourly CI run only
        # commits when the inputs actually changed.
        "data_through": model.metadata.get("trained_through"),
    }
    print(f"\n{'=' * 80}\nFORECAST - {up.race_name} (R{up.round}, {up.date}) [{entry['regime']}]\n{'=' * 80}")
    for _, r in pred.head(6).iterrows():
        print(f"  {r['predicted_rank']:>2}. {r['driver_id']:<18} P(win) {r['p_win']*100:5.1f}%   "
              f"P(podium) {r['p_podium']*100:5.1f}%")
    return entry


def main() -> None:
    parser = argparse.ArgumentParser(description="Walk-forward backtest + next-race forecast")
    parser.add_argument("--test-year", type=int, required=True, help="Season to backtest")
    parser.add_argument("--train-start", type=int, default=None,
                        help="First training season (default: podium_model.train_start_year in config)")
    parser.add_argument("--save-model", action="store_true",
                        help="Save the all-data model as the production artifact")
    parser.add_argument("--no-forecast", action="store_true", help="Skip the next-race forecast")
    parser.add_argument("--no-optimize", action="store_true", help=argparse.SUPPRESS)  # legacy flag
    args = parser.parse_args()

    config = _load_config()
    if args.train_start is None:
        args.train_start = config.get("podium_model", {}).get("train_start_year", 2014)
    clear_cache()
    frame = build_training_frame(args.train_start)
    members = members_from_config(config)
    season = frame[frame["year"] == args.test_year]
    races = season.drop_duplicates("race_id").sort_values("seq")
    race_meta = query_df("SELECT race_id, round, country FROM races WHERE year = ?", (args.test_year,))
    race_meta = race_meta.set_index("race_id")

    print(f"\n{'=' * 80}\nWALK-FORWARD BACKTEST (v4) - {args.test_year}  members={members['post']}\n{'=' * 80}")

    entries: list[dict] = []
    if not races.empty:
        # Temperature from races before the season only.
        calib = PodiumPredictor(members=members, train_start=args.train_start)
        pre_season = frame[frame["seq"] < races["seq"].min()]
        tau = calib._calibrate("post", pre_season)
        logger.info("Calibrated post-qualifying tau=%.3f on pre-season data", tau)

        print(f"\n{'Race':<26} {'Predicted podium':<44} {'Actual podium':<44} {'Hit':>4}")
        print("-" * 122)
        for _, row in races.iterrows():
            race_id = row["race_id"]
            train = frame[frame["seq"] < row["seq"]]
            race = frame[frame["race_id"] == race_id].reset_index(drop=True)
            model = PodiumPredictor(members=members, train_start=args.train_start)
            model.fitted["post"] = model._fit_members("post", train)
            model.tau["post"] = tau
            pred = model.predict(race, regime="post")
            m = _evaluate(pred, race)
            podium, win = _prob_maps(pred)
            meta = race_meta.loc[race_id]
            name = f"{meta['country']} GP (R{int(meta['round'])})"
            entries.append({
                "round": int(meta["round"]),
                "race_name": name,
                **m,
                "probabilities": podium,
                "win_probabilities": win,
                "regime": "post-qualifying",
            })
            print(f"{name:<26} {', '.join(m['predicted']):<44} {', '.join(m['actual']):<44} {m['correct']}/3")

        done = pd.DataFrame(entries)
        print(f"\n{'=' * 80}\nSEASON SUMMARY - {args.test_year}\n{'=' * 80}")
        print(f"  Races:            {len(done)}")
        print(f"  Avg correct/3:    {done['correct'].mean():.3f}")
        print(f"  All 3 correct:    {(done['correct'] == 3).sum()}/{len(done)}")
        print(f"  Winner correct:   {done['winner_correct'].sum()}/{len(done)}")
        print(f"  Avg NDCG@3:       {done['ndcg_at_3'].mean():.4f}")
        print(f"  Avg Brier:        {done['brier_score'].mean():.4f}")

    if args.save_model or not args.no_forecast:
        model = PodiumPredictor(members=members, train_start=args.train_start).fit(frame)
        if args.save_model:
            model.save()
        if not args.no_forecast:
            nxt = forecast_next(model, args.test_year)
            if nxt is not None:
                entries.append(nxt)

    for out_dir in OUTPUT_DIRS:
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"rolling_backtest_{args.test_year}.json"
        with open(path, "w") as f:
            json.dump(entries, f, indent=2)
        print(f"Saved {path}")


if __name__ == "__main__":
    main()
