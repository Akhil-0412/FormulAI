"""CLI script — Rolling window backtest with online learning."""

import argparse
import json
import logging
import sys
from pathlib import Path
import pandas as pd
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.db import query_df, get_connection
from features.pre_race import build_pre_race_features
from features.feature_store import get_training_features, get_X_y
from models.stage1_prerace import PreRacePredictor
from models.evaluate import evaluate_race

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Rolling backtest predictions with online learning")
    parser.add_argument("--test-year", type=int, required=True, help="Year to backtest (e.g., 2024 or 2025)")
    parser.add_argument("--train-start", type=int, default=2018, help="Initial training start year")
    args = parser.parse_args()

    print(f"\n{'='*80}")
    print(f"ROLLING BACKTEST — {args.test_year} Season")
    print(f"{'='*80}")

    # Initial training data up to test_year - 1
    logger.info("Loading initial training data %d - %d...", args.train_start, args.test_year - 1)
    train_df = get_training_features(start_year=args.train_start, end_year=args.test_year - 1)
    
    if train_df.empty:
        logger.error("No training data found. Run ingestion first.")
        return

    # Initialize model
    model = PreRacePredictor()
    logger.info("Training initial model...")
    X_train, y_train_podium = get_X_y(train_df, "is_podium")
    _, y_train_position = get_X_y(train_df, "finish_position")
    model.fit(X_train, y_train_podium, y_train_position, optimize=False)
    
    # Get all races for the test year
    races = query_df("SELECT round, circuit_name, country FROM races WHERE year = ? ORDER BY round", (args.test_year,))
    
    if races.empty:
        logger.error(f"No races found for {args.test_year}. Run ingestion first.")
        return

    print(f"\n{'Race':<35} {'Predicted Podium':<45} {'Actual Podium':<45} {'Correct'}")
    print("-" * 130)

    all_metrics = []
    
    for _, row in races.iterrows():
        round_num = row["round"]
        race_name = f"{row['country']} GP (R{round_num})"
        
        try:
            # 1. Evaluate current race with existing model
            race_df = build_pre_race_features(args.test_year, round_num)
            if race_df.empty:
                logger.warning("Empty features for R%d", round_num)
                continue

            metrics = evaluate_race(model, race_df)
            
            # Prepare result for frontend
            pred_str = ", ".join(metrics["predicted_podium"])
            actual_str = ", ".join(metrics["actual_podium"])
            correct = metrics["correct_predictions"]
            marker = "✅✅✅" if correct == 3 else "✅✅" if correct == 2 else "✅" if correct == 1 else "❌"
            
            print(f"{race_name:<35} {pred_str:<45} {actual_str:<45} {marker}")

            result_entry = {
                "round": round_num,
                "race_name": race_name,
                "predicted": metrics["predicted_podium"],
                "actual": metrics["actual_podium"],
                "correct": correct,
                "brier_score": getattr(metrics, 'brier_score', metrics.get('brier_score', 0)),
                "probabilities": {
                    d: p for d, p in zip(metrics.get("driver_probs_id", []), metrics.get("driver_probs", []))
                } if "driver_probs_id" in metrics else {}
            }
            all_metrics.append(result_entry)

            # 2. Add current race to training data and retrain
            train_df = pd.concat([train_df, race_df], ignore_index=True)
            X_train, y_train_podium = get_X_y(train_df, "is_podium")
            _, y_train_position = get_X_y(train_df, "finish_position")
            
            logger.debug("Retraining model with R%d added...", round_num)
            model = PreRacePredictor()
            model.fit(X_train, y_train_podium, y_train_position, optimize=False)

        except Exception as exc:
            logger.warning("Failed R%d: %s", round_num, exc)
            import traceback
            traceback.print_exc()

    # ── Forward prediction for the NEXT unraced round ──────────────────
    next_round = races["round"].max() + 1
    next_race_id = f"{args.test_year}_{next_round}"
    logger.info("Attempting forward prediction for R%d...", next_round)
    inserted_temp = False
    try:
        # Check if this next round already has data (unlikely for a future race)
        existing = query_df("SELECT race_id FROM races WHERE race_id = ?", (next_race_id,))

        if existing.empty:
            # Insert a temporary race entry using schedule data
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

                # Get driver roster from the LAST completed race
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

                    # Insert dummy results so build_pre_race_features has a driver roster
                    for _, row in last_results.iterrows():
                        conn.execute(
                            """INSERT OR IGNORE INTO results (race_id, driver_id, constructor_id, position, is_podium, status)
                               VALUES (?, ?, ?, ?, ?, ?)""",
                            (next_race_id, row["driver_id"], row["constructor_id"], 10, 0, "Pending"),
                        )

                inserted_temp = True
                logger.info("Inserted temporary R%d data for prediction", next_round)
            else:
                logger.warning("R%d not found in schedule", next_round)

        next_race_df = build_pre_race_features(args.test_year, next_round)

        if not next_race_df.empty:
            X_next, _ = get_X_y(next_race_df, "is_podium")
            driver_ids = next_race_df["driver_id"].tolist()

            podium_probs = model.predict_podium_proba(X_next)
            prob_dict = dict(zip(driver_ids, podium_probs.tolist()))

            top3 = sorted(prob_dict.items(), key=lambda x: x[1], reverse=True)[:3]

            race_info_df = query_df(
                "SELECT circuit_name, country FROM races WHERE race_id = ?",
                (next_race_id,),
            )
            if not race_info_df.empty:
                next_race_name = f"{race_info_df.iloc[0]['country']} GP (R{next_round})"
            else:
                next_race_name = f"R{next_round}"

            forward_entry = {
                "round": int(next_round),
                "race_name": next_race_name,
                "predicted": [d for d, _ in top3],
                "actual": [],
                "correct": -1,
                "brier_score": -1,
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
        else:
            logger.warning("Could not build features for R%d", next_round)

        # Clean up temporary DB entries
        if inserted_temp:
            with get_connection() as conn:
                conn.execute("DELETE FROM results WHERE race_id = ?", (next_race_id,))
                conn.execute("DELETE FROM races WHERE race_id = ?", (next_race_id,))
            logger.info("Cleaned up temporary R%d DB entries", next_round)

    except Exception as exc:
        logger.warning("Forward prediction for R%d failed: %s", next_round, exc)
        import traceback
        traceback.print_exc()

    # Save results for dashboard
    out_dir = Path(__file__).resolve().parent.parent / "data"
    out_file = out_dir / f"rolling_backtest_{args.test_year}.json"
    
    with open(out_file, "w") as f:
        json.dump(all_metrics, f, indent=2)
        
    print(f"\nSaved rolling backtest results to {out_file}")


if __name__ == "__main__":
    main()
