"""CLI script — Backtest model predictions against actual race results."""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.db import query_df
from features.pre_race import build_pre_race_features
from features.feature_store import get_X_y
from models.stage1_prerace import PreRacePredictor
from models.evaluate import evaluate_race, evaluation_summary

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest predictions against actual results")
    parser.add_argument("--test-year", type=int, required=True, help="Year to backtest")
    parser.add_argument("--model-path", type=str, help="Path to saved model (default: auto)")
    args = parser.parse_args()

    # Load model
    model = PreRacePredictor.load(Path(args.model_path) if args.model_path else None)

    # Get all races for the test year
    races = query_df("SELECT round FROM races WHERE year = ? ORDER BY round", (args.test_year,))

    if races.empty:
        print(f"No races found for {args.test_year}. Run ingestion first.")
        return

    print(f"\n{'='*80}")
    print(f"BACKTEST RESULTS — {args.test_year} Season ({len(races)} races)")
    print(f"{'='*80}")
    print(f"\n{'Race':<35} {'Predicted Podium':<45} {'Actual Podium':<45} {'Correct'}")
    print("-" * 130)

    all_metrics = []
    for _, row in races.iterrows():
        round_num = row["round"]
        try:
            race_df = build_pre_race_features(args.test_year, round_num)
            if race_df.empty:
                continue

            metrics = evaluate_race(model, race_df)

            pred_str = ", ".join(metrics["predicted_podium"])
            actual_str = ", ".join(metrics["actual_podium"])
            correct = metrics["correct_predictions"]
            marker = "✅✅✅" if correct == 3 else "✅✅" if correct == 2 else "✅" if correct == 1 else "❌"

            # Get race name
            race_info = query_df(
                "SELECT circuit_name, country FROM races WHERE race_id = ?",
                (f"{args.test_year}_{round_num}",),
            )
            race_name = f"R{round_num}"
            if not race_info.empty:
                race_name = f"{race_info.iloc[0]['country']} GP (R{round_num})"

            print(f"{race_name:<35} {pred_str:<45} {actual_str:<45} {marker}")
            all_metrics.append(metrics)

        except Exception as exc:
            logger.warning("Failed R%d: %s", round_num, exc)

    # Summary
    import pandas as pd
    results_df = pd.DataFrame(all_metrics)
    summary = evaluation_summary(results_df)

    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"  Total races:         {summary.get('total_races', 0)}")
    print(f"  All 3 correct:       {summary.get('all_3_correct', 0)} ({summary.get('all_3_correct_pct', 0):.1f}%)")
    print(f"  ≥2 correct:          {summary.get('at_least_2_correct', 0)} ({summary.get('at_least_2_pct', 0):.1f}%)")
    print(f"  ≥1 correct:          {summary.get('at_least_1_correct', 0)} ({summary.get('at_least_1_pct', 0):.1f}%)")
    print(f"  Avg position MAE:    {summary.get('avg_position_mae', 0):.2f}")
    print(f"  Avg Brier score:     {summary.get('avg_brier_score', 0):.4f}")
    print(f"  High confidence %:   {summary.get('high_confidence_pct', 0):.1f}%")

    # Calibration Analysis
    all_probs = []
    all_actuals = []
    for m in all_metrics:
        if "driver_probs" in m and "driver_actuals" in m:
            all_probs.extend(m["driver_probs"])
            all_actuals.extend(m["driver_actuals"])
            
    if all_probs:
        try:
            from sklearn.calibration import calibration_curve
            prob_true, prob_pred = calibration_curve(
                all_actuals, all_probs, n_bins=10, strategy='uniform'
            )
            
            print(f"\n{'='*80}")
            print("CALIBRATION ANALYSIS (Probability Reliability)")
            print(f"{'='*80}")
            print(f"{'Predicted Prob Range':<25} | {'Actual Podium Freq':<20}")
            print("-" * 50)
            for t, p in zip(prob_true, prob_pred):
                print(f"{p:>23.1%}   | {t:>18.1%}")
            print("\n* If predicted probability closely matches actual frequency, the model is well-calibrated.")
        except ImportError:
            pass


if __name__ == "__main__":
    main()
