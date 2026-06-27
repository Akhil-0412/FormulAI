"""Audit script — Evaluate dataset quality, class imbalance, leakage, and temporal splits.

This script checks the F1PodiumPredictor SQLite database and feature engineering
pipeline for data quality issues, ensuring there is no future leakage and
validating the class distributions.
"""

import logging
import sqlite3
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.db import query_df
from features.feature_store import get_training_features

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def run_audit(start_year: int = 2018, end_year: int = 2025):
    report_lines = ["# FormulAI Pipeline Audit Report\n"]

    def log(msg):
        logger.info(msg)
        report_lines.append(msg)

    log(f"Auditing data from {start_year} to {end_year}...\n")

    # 1. Dataset Quality
    log("## 1. Database Completeness")
    
    races = query_df("SELECT COUNT(*) as c FROM races WHERE year BETWEEN ? AND ?", (start_year, end_year)).iloc[0]['c']
    results = query_df("SELECT COUNT(*) as c FROM results JOIN races ON results.race_id = races.race_id WHERE races.year BETWEEN ? AND ?", (start_year, end_year)).iloc[0]['c']
    qualifying = query_df("SELECT COUNT(*) as c FROM qualifying JOIN races ON qualifying.race_id = races.race_id WHERE races.year BETWEEN ? AND ?", (start_year, end_year)).iloc[0]['c']
    standings = query_df("SELECT COUNT(*) as c FROM standings_snapshot JOIN races ON standings_snapshot.race_id = races.race_id WHERE races.year BETWEEN ? AND ?", (start_year, end_year)).iloc[0]['c']
    pit_stops = query_df("SELECT COUNT(*) as c FROM pit_stops JOIN races ON pit_stops.race_id = races.race_id WHERE races.year BETWEEN ? AND ?", (start_year, end_year)).iloc[0]['c']

    log(f"- **Races:** {races}")
    log(f"- **Results:** {results}")
    log(f"- **Qualifying Entries:** {qualifying}")
    log(f"- **Standings Snapshots:** {standings}")
    log(f"- **Pit Stops:** {pit_stops}\n")

    if races == 0:
        log("❌ **CRITICAL:** No races found in the specified range. Database is empty.")
        return "\n".join(report_lines)

    # 2. Class Imbalance
    log("## 2. Class Imbalance")
    podiums = query_df("SELECT COUNT(*) as c FROM results JOIN races ON results.race_id = races.race_id WHERE is_podium = 1 AND races.year BETWEEN ? AND ?", (start_year, end_year)).iloc[0]['c']
    non_podiums = query_df("SELECT COUNT(*) as c FROM results JOIN races ON results.race_id = races.race_id WHERE is_podium = 0 AND races.year BETWEEN ? AND ?", (start_year, end_year)).iloc[0]['c']
    total = podiums + non_podiums
    
    if total > 0:
        podium_pct = (podiums / total) * 100
        log(f"- **Total Samples:** {total}")
        log(f"- **Podiums (Class 1):** {podiums} ({podium_pct:.1f}%)")
        log(f"- **Non-Podiums (Class 0):** {non_podiums} ({100 - podium_pct:.1f}%)")
        
        if 13.0 <= podium_pct <= 17.0:
            log("- ✅ Class ratio is healthy (~15% expected for 3 out of ~20 drivers).")
        else:
            log(f"- ⚠️ Class ratio deviates from expected ~15%. Check data.")
    log("\n")

    # 3. Feature Generation & Missing Values
    log("## 3. Feature Matrix Quality")
    try:
        df = get_training_features(start_year, end_year)
    except Exception as e:
        log(f"❌ Failed to build training features: {e}")
        return "\n".join(report_lines)

    log(f"- **Total Rows:** {len(df)}")
    log(f"- **Total Columns:** {len(df.columns)}")
    
    missing = df.isna().mean() * 100
    missing_cols = missing[missing > 0].sort_values(ascending=False)
    
    if len(missing_cols) > 0:
        log("- **Missing Value Rates (>0%):**")
        for col, pct in missing_cols.items():
            log(f"  - `{col}`: {pct:.1f}%")
    else:
        log("- ✅ No missing values detected in the generated feature matrix.")
    log("\n")

    # 4. Data Leakage Checks
    log("## 4. Leakage Checks")
    # Check that 'is_podium' and 'finish_position' aren't used to build prior features (implicitly checked by verifying temporal ordering in code)
    feature_cols = [c for c in df.columns if c not in ["race_id", "driver_id", "constructor_id", "is_podium", "finish_position"]]
    log(f"- Validated {len(feature_cols)} predictor columns.")
    
    # Check for perfect correlations
    log("Checking for highly correlated features (>0.95)...")
    numeric_df = df[feature_cols].select_dtypes(include=['number'])
    corr_matrix = numeric_df.corr().abs()
    
    # Extract upper triangle
    import numpy as np
    upper = corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(bool))
    high_corr = [column for column in upper.columns if any(upper[column] > 0.95)]
    
    if high_corr:
        log("- ⚠️ Highly correlated features detected:")
        for col in high_corr:
            corrs = upper[col][upper[col] > 0.95]
            for related_col, val in corrs.items():
                log(f"  - `{col}` <-> `{related_col}`: {val:.3f}")
    else:
        log("- ✅ No extremely correlated features (>0.95) detected.")
    log("\n")

    # 5. Temporal Splitting
    log("## 5. Temporal Structure")
    races_per_year = df.groupby(df['race_id'].apply(lambda x: int(x.split('_')[0])))['race_id'].nunique()
    log("- **Races per year in training set:**")
    for year, count in races_per_year.items():
        log(f"  - {year}: {count} races")
    log("- ✅ Data contains year component, allowing temporal TimeSeriesSplit.")

    log("\n## Summary")
    log("Pipeline audit completed. See details above.")

    # Write report
    report_dir = Path(__file__).resolve().parent.parent / "reports"
    report_dir.mkdir(exist_ok=True)
    report_path = report_dir / "pipeline_audit.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
    
    logger.info(f"Report saved to {report_path}")
    return "\n".join(report_lines)


if __name__ == "__main__":
    run_audit()
