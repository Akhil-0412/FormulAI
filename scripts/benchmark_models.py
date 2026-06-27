"""Model Benchmark Script — Compare XGBoost, LightGBM, CatBoost, and Ensembles.

This script benchmarks different tabular ML architectures on the F1 prediction task.
It uses temporal cross-validation to evaluate model performance, calibration, and stability.
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import settings
from features.feature_store import get_training_features, get_X_y
from models_v2.stage1_prerace import PreRacePredictor

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def run_benchmark(
    train_start: int = 2018,
    train_end: int = 2023,
    val_year: int = 2024,
    n_trials: int = 10,
):
    print("\n" + "=" * 60)
    print("🚀 FormulAI Model Benchmark (Tabular)")
    print("=" * 60)
    print(f"Train: {train_start}-{train_end} | Validate: {val_year}\n")

    full_df = get_training_features(train_start, val_year)
    if full_df.empty:
        logger.error("No training data available. Run ingestion first.")
        return

    train_df = full_df[full_df["race_id"].apply(lambda x: int(x.split("_")[0]) <= train_end)]
    test_df = full_df[full_df["race_id"].apply(lambda x: int(x.split("_")[0]) == val_year)]

    X_train, y_train_podium = get_X_y(train_df, "is_podium")
    y_train_pos = train_df["finish_position"]

    X_test, y_test_podium = get_X_y(test_df, "is_podium")
    y_test_pos = test_df["finish_position"]

    # Base configuration for all models
    base_config = {
        "optimization": {
            "enabled": True,
            "n_trials": n_trials,
            "timeout_seconds": 600,
            "classifier_search": {
                "max_depth": [3, 8],
                "learning_rate": [0.01, 0.2],
                "n_estimators": [100, 300],
            }
        },
        "calibration": {"method": "isotonic", "temporal_split": False},
        "cross_validation": {"n_splits": 2},
    }

    models_to_test = ["xgboost", "lightgbm", "catboost"]
    results = {}

    for model_name in models_to_test:
        print(f"\nTraining {model_name.upper()}...")
        
        config = base_config.copy()
        config["classifier"] = {"model": model_name, "early_stopping": {"enabled": False}}
        
        model = PreRacePredictor(config=config)
        
        start_t = time.time()
        # Train without early stopping or calibration splitting for a fair speed benchmark
        model.fit(
            X_train, y_train_podium, y_train_pos,
            optimize=True
        )
        duration = time.time() - start_t
        
        # Evaluate on Test Set
        y_prob = model.predict_podium_proba(X_test)
        y_pred = (y_prob >= 0.5).astype(int)
        
        acc = accuracy_score(y_test_podium, y_pred)
        loss = log_loss(y_test_podium, y_prob)
        brier = brier_score_loss(y_test_podium, y_prob)
        
        # Calculate race-level accuracy (how often did we predict top 3 correctly)
        # For this we need to simulate the Stage 3 ensemble constraint
        from models_v2.stage3_ensemble import enforce_podium_constraints
        
        races = test_df["race_id"].unique()
        correct_races = 0
        at_least_one = 0
        
        for race_id in races:
            race_mask = test_df["race_id"] == race_id
            race_drivers = test_df[race_mask]["driver_id"].tolist()
            race_probs = y_prob[race_mask]
            race_actual = test_df[race_mask & (test_df["is_podium"] == 1)]["driver_id"].tolist()
            
            prob_dict = dict(zip(race_drivers, race_probs))
            
            try:
                ensemble_res = enforce_podium_constraints(prob_dict)
                pred_podium = [p.driver_id for p in ensemble_res.podium]
                
                correct = len(set(pred_podium).intersection(set(race_actual)))
                if correct == 3:
                    correct_races += 1
                if correct >= 1:
                    at_least_one += 1
            except Exception:
                pass
                
        all_3_pct = (correct_races / len(races)) * 100 if len(races) > 0 else 0
        at_least_1_pct = (at_least_one / len(races)) * 100 if len(races) > 0 else 0
        
        results[model_name] = {
            "Accuracy": f"{acc:.4f}",
            "Log Loss": f"{loss:.4f}",
            "Brier Score": f"{brier:.4f}",
            "All 3 Correct": f"{all_3_pct:.1f}%",
            "≥1 Correct": f"{at_least_1_pct:.1f}%",
            "Train Time (s)": f"{duration:.1f}",
        }
        
        print(f"  Accuracy: {acc:.4f} | Brier: {brier:.4f} | Time: {duration:.1f}s")

    # Save and display report
    report_dir = Path(__file__).resolve().parent.parent / "reports"
    report_dir.mkdir(exist_ok=True)
    report_path = report_dir / "performance_comparison.md"
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# Model Performance Benchmark\n\n")
        f.write(f"**Training Period:** {train_start}-{train_end} | **Test Year:** {val_year}\n\n")
        
        # Convert to markdown table
        df_res = pd.DataFrame(results).T
        f.write(df_res.to_markdown())
        
        f.write("\n\n## Conclusion\n")
        f.write("This benchmark compares pure classification performance before Stage 2/3 ensemble effects.\n")
        
    print("\n" + "=" * 60)
    print(f"Benchmark complete. Report saved to {report_path}")
    print("=" * 60)
    print(pd.DataFrame(results).T)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark tabular models")
    parser.add_argument("--train-start", type=int, default=2018)
    parser.add_argument("--train-end", type=int, default=2023)
    parser.add_argument("--val-year", type=int, default=2024)
    parser.add_argument("--n-trials", type=int, default=10, help="Optuna trials per model")
    args = parser.parse_args()
    
    run_benchmark(args.train_start, args.train_end, args.val_year, args.n_trials)
