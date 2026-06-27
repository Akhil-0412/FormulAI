"""Unified training and evaluation pipeline for FormulAI.

This script runs the full pipeline:
1. Loads config from config/training_config.yaml
2. Trains model using temporal CV
3. Runs backtest on test year
4. Generates an evaluation report
"""

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import settings
from models_v2.train import train_with_temporal_cv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="FormulAI Train & Evaluate Pipeline")
    parser.add_argument("--config", type=str, default="config/training_config.yaml",
                        help="Path to training config YAML")
    parser.add_argument("--no-optimize", action="store_true",
                        help="Skip hyperparameter optimization (fast mode)")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = settings.project_root / config_path

    logger.info("Starting Train & Evaluate pipeline using config: %s", config_path)
    
    # 1. Train Model
    logger.info("--- PHASE 1: TRAINING ---")
    try:
        from models_v2.train import _load_config
        config = _load_config(config_path)
        data_cfg = config.get("data", {})
        
        train_start = data_cfg.get("train_start_year", 2018)
        train_end = data_cfg.get("train_end_year", 2023)
        val_year = data_cfg.get("val_year", 2024)
        test_year = data_cfg.get("test_year", 2025)
        
        results = train_with_temporal_cv(
            train_start=train_start,
            train_end=train_end,
            val_year=val_year,
            optimize=not args.no_optimize,
            config_path=config_path
        )
        
        model_path = results.get("model_path")
        logger.info("Training complete. Model saved to %s", model_path)
        
    except Exception as e:
        logger.error("Training failed: %s", e)
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # 2. Backtest & Evaluate
    logger.info("\n--- PHASE 2: EVALUATION & BACKTEST ---")
    try:
        import subprocess
        logger.info("Running backtest for test year %d...", test_year)
        
        backtest_cmd = [
            sys.executable, 
            str(settings.project_root / "scripts" / "backtest.py"),
            "--test-year", str(test_year),
            "--model-path", model_path
        ]
        
        process = subprocess.Popen(
            backtest_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        
        output_lines = []
        for line in process.stdout:
            sys.stdout.write(line)
            output_lines.append(line)
            
        process.wait()
        
        if process.returncode != 0:
            logger.error("Backtest failed with exit code %d", process.returncode)
            
        # Save output to evaluation report
        report_dir = settings.project_root / "reports"
        report_dir.mkdir(exist_ok=True)
        report_file = report_dir / f"evaluation_report_{test_year}.md"
        
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(f"# FormulAI Evaluation Report: {test_year} Season\n\n")
            f.write(f"**Model:** `{model_path}`\n")
            f.write(f"**Trained on:** {train_start}-{train_end} (Validated on {val_year})\n\n")
            f.write("```text\n")
            f.write("".join(output_lines))
            f.write("\n```\n")
            
        logger.info("Evaluation report saved to %s", report_file)
        
    except Exception as e:
        logger.error("Evaluation failed: %s", e)
        import traceback
        traceback.print_exc()

    logger.info("Pipeline complete.")


if __name__ == "__main__":
    main()
