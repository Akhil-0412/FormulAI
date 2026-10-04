import argparse
import logging
import json
import sys
import yaml
from pathlib import Path

# Add project root to path (matches the other scripts, so this runs directly
# and not only when the package is pip-installed into the environment).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import optuna

from config.settings import settings
from data.db import get_connection, query_df
from features.feature_store import get_training_features, get_X_y, get_feature_columns
from models_v2.training import _inject_auxiliary_features
from models_v2.ltr_ranker import F1LTRRanker
def evaluate_ndcg(y_true, y_score, k=3):
    pred_order = np.argsort(-y_score)[:k]
    ideal_order = np.argsort(-y_true)[:k]
    
    pred_rel = y_true[pred_order]
    ideal_rel = y_true[ideal_order]
    
    positions = np.arange(1, len(pred_rel) + 1)
    dcg = np.sum(pred_rel / np.log2(positions + 1))
    
    ideal_positions = np.arange(1, len(ideal_rel) + 1)
    idcg = np.sum(ideal_rel / np.log2(ideal_positions + 1))
    
    return float(dcg / idcg) if idcg > 0 else 0.0

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_data(start_year: int = 2022, end_year: int = 2024):
    """Load the training window.

    Defaults to 2022+ (ground-effect regulation era) to match
    training_config.yaml — tuning on pre-2022 seasons optimises for a
    different formula and measurably hurts current-season accuracy.
    """
    logger.info("Loading dataset %d-%d...", start_year, end_year)
    df = get_training_features(start_year=start_year, end_year=end_year)
    logger.info(f"Loaded {len(df)} rows.")
    return df

def create_temporal_split(df: pd.DataFrame, train_end_year: int = 2023):
    """
    Creates a group-aware temporal validation split.
    Train: 2014 to `train_end_year`
    Val: `train_end_year + 1`
    """
    if "year" not in df.columns and "race_id" in df.columns:
        df["year"] = df["race_id"].apply(lambda x: int(str(x).split("_")[0]))
        
    df_train = df[df["year"] <= train_end_year].copy()
    df_val = df[df["year"] == train_end_year + 1].copy()
    
    return df_train, df_val

def suggest_params(trial):
    """Separate search spaces per library.

    XGBoost and LightGBM do not share a hyperparameter vocabulary. Tuning one
    dict and handing it to both meant LightGBM-only knobs (min_child_samples,
    num_leaves) were never searched, while XGBoost-only ones
    (lambdarank_*) leaked into LightGBM and were discarded with a warning.
    """
    xgb_params = {
        "n_estimators": trial.suggest_int("xgb_n_estimators", 50, 300),
        "learning_rate": trial.suggest_float("xgb_learning_rate", 0.01, 0.2, log=True),
        "max_depth": trial.suggest_int("xgb_max_depth", 3, 8),
        "subsample": trial.suggest_float("xgb_subsample", 0.6, 1.0),
        "colsample_bytree": trial.suggest_float("xgb_colsample_bytree", 0.6, 1.0),
        "min_child_weight": trial.suggest_int("xgb_min_child_weight", 1, 10),
        "reg_alpha": trial.suggest_float("xgb_reg_alpha", 1e-3, 10.0, log=True),
        "reg_lambda": trial.suggest_float("xgb_reg_lambda", 1e-3, 10.0, log=True),
        "lambdarank_num_pair_per_sample": trial.suggest_int(
            "xgb_lambdarank_num_pair_per_sample", 1, 10),
    }
    lgb_params = {
        "n_estimators": trial.suggest_int("lgb_n_estimators", 50, 300),
        "learning_rate": trial.suggest_float("lgb_learning_rate", 0.01, 0.2, log=True),
        "max_depth": trial.suggest_int("lgb_max_depth", 3, 8),
        "num_leaves": trial.suggest_int("lgb_num_leaves", 8, 64),
        "subsample": trial.suggest_float("lgb_subsample", 0.6, 1.0),
        "colsample_bytree": trial.suggest_float("lgb_colsample_bytree", 0.6, 1.0),
        "min_child_samples": trial.suggest_int("lgb_min_child_samples", 5, 40),
        "reg_alpha": trial.suggest_float("lgb_reg_alpha", 1e-3, 10.0, log=True),
        "reg_lambda": trial.suggest_float("lgb_reg_lambda", 1e-3, 10.0, log=True),
    }
    return xgb_params, lgb_params


def objective(trial, df_train, df_val, base_feature_cols, dnf_head, pace_head):
    xgb_params, lgb_params = suggest_params(trial)

    # Optional: adjust blending weights
    blend_weight_xgb = trial.suggest_float("blend_weight_xgb", 0.2, 0.8)

    # Initialize model with trial params
    ranker = F1LTRRanker(xgb_params=xgb_params, lgb_params=lgb_params,
                         blend_weight_xgb=blend_weight_xgb)
    
    # Train
    try:
        from features.feature_store import get_X_y_grouped
        X_train, y_train, group_train, _ = get_X_y_grouped(df_train, target="relevance")
        X_val, y_val, group_val, _ = get_X_y_grouped(df_val, target="relevance")
        
        # Fit model (optimize=False because we are doing outer Optuna loop here)
        ranker.fit(X_train, y_train, group_train, X_val, y_val, group_val, optimize=False)
    except Exception as e:
        logger.warning(f"Trial failed during fit: {e}")
        return 0.0

    # Evaluate on Validation Set (NDCG@3)
    val_qids = df_val["race_id"].values
    
    # Score predictions
    scores = ranker.predict_scores(X_val)
    df_eval = df_val.copy()
    df_eval["score"] = scores
    
    # NDCG calculation requires iterating over groups
    ndcg_scores = []
    for qid in np.unique(val_qids):
        group_df = df_eval[df_eval["race_id"] == qid]
        if len(group_df) < 3:
            continue
            
        y_true = group_df["relevance"].values
        y_pred = group_df["score"].values
        
        ndcg = evaluate_ndcg(y_true, y_pred, k=3)
        ndcg_scores.append(ndcg)
        
    return np.mean(ndcg_scores)

def main():
    parser = argparse.ArgumentParser(description="Deep Hyperparameter Tuning for FormulAI LTR Model")
    parser.add_argument("--trials", type=int, default=200, help="Number of Optuna trials")
    parser.add_argument("--train_end_year", type=int, default=2023, help="Year to split train/val")
    parser.add_argument("--start_year", type=int, default=2022,
                        help="First season to tune on (2022 = ground-effect era)")
    args = parser.parse_args()

    df = load_data(start_year=args.start_year, end_year=args.train_end_year + 1)
    df_train, df_val = create_temporal_split(df, args.train_end_year)
    
    logger.info(f"Train races: {df_train['race_id'].nunique()} ({df_train['year'].min()}-{df_train['year'].max()})")
    logger.info(f"Val races: {df_val['race_id'].nunique()} ({df_val['year'].unique()})")

    import joblib
    from models_v2.training import _train_auxiliary_heads
    
    # Load or train auxiliary heads
    dnf_path = settings.abs_model_dir / "aux_dnf_head.joblib"
    pace_path = settings.abs_model_dir / "aux_pace_head.joblib"
    
    base_feature_cols = [
        c for c in get_feature_columns(df)
        if c in df.columns and df[c].dtype != object
    ]
    
    if not dnf_path.exists() or not pace_path.exists():
        logger.info("Auxiliary heads not found. Training them now...")
        dnf_head, pace_head = _train_auxiliary_heads(df_train, base_feature_cols)
        # Save them for the future
        if dnf_head is not None:
            joblib.dump(dnf_head, dnf_path)
        if pace_head is not None:
            joblib.dump(pace_head, pace_path)
    else:
        dnf_head = joblib.load(dnf_path)
        pace_head = joblib.load(pace_path)
    
    logger.info("Injecting auxiliary features...")
    df_train = _inject_auxiliary_features(df_train, base_feature_cols, dnf_head, pace_head)
    df_val = _inject_auxiliary_features(df_val, base_feature_cols, dnf_head, pace_head)

    study = optuna.create_study(direction="maximize", study_name="f1_ltr_tuning")
    
    logger.info(f"Starting optimization for {args.trials} trials...")
    study.optimize(lambda trial: objective(trial, df_train, df_val, base_feature_cols, dnf_head, pace_head), n_trials=args.trials)

    logger.info("Optimization finished.")
    logger.info(f"Best trial: {study.best_trial.number}")
    logger.info(f"Best NDCG@3: {study.best_trial.value:.4f}")
    logger.info("Best parameters:")
    for key, value in study.best_trial.params.items():
        logger.info(f"  {key}: {value}")
        
    # Save to config
    config_path = settings.project_root / "config" / "training_config.yaml"
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
        
    if "models" not in config:
        config["models"] = {}
    if "ltr_ranker" not in config["models"]:
        config["models"]["ltr_ranker"] = {}
        
    # Persist the two param sets separately, keyed by the library's own
    # parameter names, so training can hand each ranker its own tuned values.
    best = study.best_trial.params
    best_xgb = {k[len("xgb_"):]: v for k, v in best.items() if k.startswith("xgb_")}
    best_lgb = {k[len("lgb_"):]: v for k, v in best.items() if k.startswith("lgb_")}

    config["models"]["ltr_ranker"]["best_params_xgb"] = best_xgb
    config["models"]["ltr_ranker"]["best_params_lgb"] = best_lgb
    config["models"]["ltr_ranker"]["blend_weight_xgb"] = best.get("blend_weight_xgb", 0.5)
    # Drop the old shared dict so training doesn't fall back to it.
    config["models"]["ltr_ranker"].pop("best_params", None)

    with open(config_path, "w") as f:
        yaml.safe_dump(config, f)

    logger.info(f"Saved best parameters to {config_path}")
    logger.info(f"  xgb: {best_xgb}")
    logger.info(f"  lgb: {best_lgb}")

if __name__ == "__main__":
    main()
