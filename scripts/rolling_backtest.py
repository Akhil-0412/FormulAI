"""CLI script — Rolling window backtest with online learning for LTR model."""

import argparse
import json
import logging
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.db import query_df, get_connection
from features.pre_race import build_pre_race_features
from features.feature_store import get_training_features, get_X_y_grouped, get_feature_columns
from models_v2.ltr_ranker import F1LTRRanker
from models_v2.evaluate import evaluate_race

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


def _train_and_inject_aux(train_df, feature_cols):
    """Train auxiliary heads and inject predictions as features."""
    from models_v2.training import _train_auxiliary_heads, _inject_auxiliary_features
    dnf_head, pace_head = _train_auxiliary_heads(train_df, feature_cols)
    train_df = _inject_auxiliary_features(train_df, feature_cols, dnf_head, pace_head)
    return train_df, dnf_head, pace_head


def main() -> None:
    parser = argparse.ArgumentParser(description="Rolling backtest with LTR model")
    parser.add_argument("--test-year", type=int, required=True, help="Year to backtest")
    parser.add_argument("--train-start", type=int, default=2014, help="Initial training start year")
    parser.add_argument("--no-optimize", action="store_true", help="Skip Optuna optimization")
    args = parser.parse_args()

    print(f"\n{'='*80}")
    print(f"ROLLING BACKTEST (LTR v3) — {args.test_year} Season")
    print(f"{'='*80}")

    # Initial training data up to test_year - 1
    logger.info("Loading initial training data %d - %d...", args.train_start, args.test_year - 1)
    train_df = get_training_features(
        start_year=args.train_start,
        end_year=args.test_year - 1,
        force_rebuild=True,
    )

    if train_df.empty:
        logger.error("No training data found. Run ingestion first.")
        return

    # Get base feature columns
    base_feature_cols = [
        c for c in get_feature_columns(train_df)
        if c in train_df.columns and train_df[c].dtype != object
    ]

    # Train auxiliary heads and inject features
    logger.info("Training auxiliary heads...")
    train_df, dnf_head, pace_head = _train_and_inject_aux(train_df, base_feature_cols)

    # Train LTR model
    logger.info("Training initial LTR model...")
    X_train, y_train, group_train, _ = get_X_y_grouped(train_df, target="relevance")

    model = F1LTRRanker()
    model.fit(X_train, y_train, group_train, optimize=not args.no_optimize)

    # Get all races for the test year
    races = query_df("SELECT round, circuit_name, country FROM races WHERE year = ? ORDER BY round", (args.test_year,))

    if races.empty:
        logger.error(f"No races found for {args.test_year}. Run ingestion first.")
        return

    print(f"\n{'Race':<35} {'Predicted Podium':<45} {'Actual Podium':<45} {'Correct':>7} {'NDCG@3':>7}")
    print("-" * 145)

    all_metrics = []

    for _, row in races.iterrows():
        round_num = row["round"]
        race_name = f"{row['country']} GP (R{round_num})"

        try:
            # 1. Build features for current race
            race_df = build_pre_race_features(args.test_year, round_num)
            if race_df.empty:
                logger.warning("Empty features for R%d", round_num)
                continue

            # Inject auxiliary features
            from models_v2.training import _inject_auxiliary_features
            race_df = _inject_auxiliary_features(race_df, base_feature_cols, dnf_head, pace_head)

            # 2. Evaluate
            metrics = evaluate_race(model, race_df)

            # Print results
            pred_str = ", ".join(metrics["predicted_podium"][:3])
            actual_str = ", ".join(metrics["actual_podium"][:3])
            correct = metrics["correct_predictions"]
            ndcg = metrics.get("ndcg_at_3", 0.0)
            marker = "3/3" if correct == 3 else "2/3" if correct == 2 else "1/3" if correct == 1 else "0/3"

            print(f"{race_name:<35} {pred_str:<45} {actual_str:<45} {marker:>7} {ndcg:>7.3f}")

            result_entry = {
                "round": int(round_num),
                "race_name": race_name,
                "predicted": metrics["predicted_podium"],
                "actual": metrics["actual_podium"],
                "correct": correct,
                "brier_score": metrics.get("brier_score", 0),
                "ndcg_at_3": ndcg,
                "kendall_tau": metrics.get("kendall_tau", 0),
                "top3_precision": metrics.get("top3_precision", 0),
                "probabilities": {
                    d: p for d, p in zip(metrics.get("driver_probs_id", []), metrics.get("driver_probs", []))
                } if "driver_probs_id" in metrics else {}
            }
            all_metrics.append(result_entry)

            # 3. Online learning: add this race and retrain
            train_df = pd.concat([train_df, race_df], ignore_index=True)

            # Re-train auxiliary heads
            train_df_aux, dnf_head, pace_head = _train_and_inject_aux(
                train_df.drop(columns=["aux_p_dnf", "aux_predicted_pace"], errors="ignore"),
                base_feature_cols,
            )
            train_df = train_df_aux

            X_train, y_train, group_train, _ = get_X_y_grouped(train_df, target="relevance")

            logger.debug("Retraining LTR model with R%d added...", round_num)
            model = F1LTRRanker()
            model.fit(X_train, y_train, group_train, optimize=False)

        except Exception as exc:
            logger.warning("Failed R%d: %s", round_num, exc)
            import traceback
            traceback.print_exc()

    # ── Summary ────────────────────────────────────────────────────────
    completed = [m for m in all_metrics if m["correct"] >= 0]
    if completed:
        avg_correct = sum(m["correct"] for m in completed) / len(completed)
        all_3 = sum(1 for m in completed if m["correct"] == 3)
        at_least_2 = sum(1 for m in completed if m["correct"] >= 2)
        at_least_1 = sum(1 for m in completed if m["correct"] >= 1)
        avg_ndcg = sum(m.get("ndcg_at_3", 0) for m in completed) / len(completed)
        avg_brier = sum(m.get("brier_score", 0) for m in completed) / len(completed)

        print(f"\n{'='*80}")
        print(f"SEASON SUMMARY — {args.test_year}")
        print(f"{'='*80}")
        print(f"  Races evaluated:  {len(completed)}")
        print(f"  Avg correct/3:    {avg_correct:.2f}")
        print(f"  All 3 correct:    {all_3}/{len(completed)} ({all_3/len(completed)*100:.1f}%)")
        print(f"  >=2 correct:       {at_least_2}/{len(completed)} ({at_least_2/len(completed)*100:.1f}%)")
        print(f"  >=1 correct:       {at_least_1}/{len(completed)} ({at_least_1/len(completed)*100:.1f}%)")
        print(f"  Avg NDCG@3:       {avg_ndcg:.4f}")
        print(f"  Avg Brier Score:  {avg_brier:.4f}")

    # ── Forward prediction for next round ──────────────────────────────
    if not races.empty:
        next_round = int(races["round"].max()) + 1
        next_race_id = f"{args.test_year}_{next_round}"
        logger.info("Attempting forward prediction for R%d...", next_round)
        inserted_temp = False
        try:
            existing = query_df("SELECT race_id FROM races WHERE race_id = ?", (next_race_id,))

            if existing.empty:
                from data.jolpica_client import JolpicaClient
                jc = JolpicaClient()
                schedule = jc.get_schedule(args.test_year)
                jc.close()

                race_sched = [r for r in schedule if str(r.get("round")) == str(next_round)]
                if race_sched:
                    rs = race_sched[0]
                    circuit_data = rs.get("Circuit", {})
                    circuit_id = circuit_data.get("circuitId", "unknown")
                    circuit_name = circuit_data.get("circuitName", "Unknown")
                    country = circuit_data.get("Location", {}).get("country", "Unknown")
                    race_date = rs.get("date", "")

                    last_race_id = f"{args.test_year}_{races['round'].max()}"
                    last_results = query_df(
                        "SELECT driver_id, constructor_id FROM results WHERE race_id = ?",
                        (last_race_id,),
                    )

                    with get_connection() as conn:
                        conn.execute(
                            """INSERT OR IGNORE INTO races (race_id, year, round, circuit_id, circuit_name, country, race_date)
                               VALUES (?, ?, ?, ?, ?, ?, ?)""",
                            (next_race_id, args.test_year, next_round, circuit_id, circuit_name, country, race_date),
                        )
                        for _, r in last_results.iterrows():
                            conn.execute(
                                """INSERT OR IGNORE INTO results (race_id, driver_id, constructor_id, position, is_podium, status)
                                   VALUES (?, ?, ?, ?, ?, ?)""",
                                (next_race_id, r["driver_id"], r["constructor_id"], 10, 0, "Pending"),
                            )

                    inserted_temp = True

            next_race_df = build_pre_race_features(args.test_year, next_round)

            if not next_race_df.empty:
                next_race_df = _inject_auxiliary_features(next_race_df, base_feature_cols, dnf_head, pace_head)
                driver_ids = next_race_df["driver_id"].tolist()

                # Get features
                feature_cols = [c for c in model.feature_columns if c in next_race_df.columns]
                X_next = next_race_df[feature_cols].copy()
                for col in X_next.columns:
                    if X_next[col].dtype == object:
                        X_next = X_next.drop(columns=[col])
                numeric_cols = X_next.select_dtypes(include=["number"]).columns
                X_next[numeric_cols] = X_next[numeric_cols].fillna(X_next[numeric_cols].median()).fillna(0)

                prob_dict = model.predict_race(X_next, driver_ids)
                top3 = list(prob_dict.items())[:3]

                race_info_df = query_df(
                    "SELECT circuit_name, country FROM races WHERE race_id = ?",
                    (next_race_id,),
                )
                next_race_name = f"{race_info_df.iloc[0]['country']} GP (R{next_round})" if not race_info_df.empty else f"R{next_round}"

                forward_entry = {
                    "round": int(next_round),
                    "race_name": next_race_name,
                    "predicted": [d for d, _ in top3],
                    "actual": [],
                    "correct": -1,
                    "brier_score": -1,
                    "ndcg_at_3": -1,
                    "probabilities": {d: float(p) for d, p in prob_dict.items()},
                    "is_future": True,
                }
                all_metrics.append(forward_entry)

                pred_str = ", ".join([d for d, _ in top3])
                probs_str = ", ".join([f"{p*100:.1f}%" for _, p in top3])
                print(f"\n{'='*80}")
                print(f"FORWARD PREDICTION — R{next_round} ({next_race_name})")
                print(f"{'='*80}")
                print(f"  Predicted Podium: {pred_str}")
                print(f"  Probabilities:    {probs_str}")

            if inserted_temp:
                with get_connection() as conn:
                    conn.execute("DELETE FROM results WHERE race_id = ?", (next_race_id,))
                    conn.execute("DELETE FROM races WHERE race_id = ?", (next_race_id,))

        except Exception as exc:
            logger.warning("Forward prediction for R%d failed: %s", next_round, exc)
            import traceback
            traceback.print_exc()

    # Save results
    out_dir = Path(__file__).resolve().parent.parent / "data"
    out_file = out_dir / f"rolling_backtest_{args.test_year}.json"

    with open(out_file, "w") as f:
        json.dump(all_metrics, f, indent=2)

    print(f"\nSaved rolling backtest results to {out_file}")


if __name__ == "__main__":
    main()
