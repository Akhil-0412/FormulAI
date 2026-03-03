"""CLI script — Train the Stage 1 pre-race model."""

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.train import train_with_temporal_cv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the pre-race prediction model")
    parser.add_argument("--train-start", type=int, default=2018, help="First training year")
    parser.add_argument("--train-end", type=int, default=2023, help="Last training year")
    parser.add_argument("--val-year", type=int, default=2024, help="Validation year")
    parser.add_argument("--no-optimize", action="store_true", help="Skip Optuna optimization")
    args = parser.parse_args()

    logger.info("Training model: %d–%d, validate on %d", args.train_start, args.train_end, args.val_year)
    logger.info("Optimization: %s", "OFF" if args.no_optimize else "ON")

    results = train_with_temporal_cv(
        train_start=args.train_start,
        train_end=args.train_end,
        val_year=args.val_year,
        optimize=not args.no_optimize,
    )

    # Print summary
    print("\n" + "=" * 60)
    print("TRAINING RESULTS")
    print("=" * 60)

    print("\n--- Temporal CV Folds ---")
    for fold in results["fold_results"]:
        print(f"  Val year {fold['fold_val_year']}: "
              f"AUC={fold['classifier_auc']:.4f}, "
              f"F1={fold['classifier_f1']:.4f} "
              f"(train={fold['train_size']}, val={fold['val_size']})")

    print("\n--- Test Metrics ---")
    for k, v in results["test_metrics"].items():
        if isinstance(v, float):
            print(f"  {k}: {v:.4f}")

    print("\n--- Top Features ---")
    for feat in results["feature_importance"][:10]:
        print(f"  {feat['feature']}: {feat['importance']:.4f}")

    print(f"\nModel saved to: {results['model_path']}")


if __name__ == "__main__":
    main()
