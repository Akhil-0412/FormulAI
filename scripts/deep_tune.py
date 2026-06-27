import argparse
import logging
import json
import yaml
from pathlib import Path

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

def load_data():
    logger.info("Loading full historical dataset...")
    df = get_training_features(start_year=2014, end_year=2024)
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

def objective(trial, df_train, df_val, base_feature_cols, dnf_head, pace_head):
    # Suggest LTR-specific hyperparameters
    params = {
        "n_estimators": trial.suggest_int("n_estimators", 50, 300),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
        "max_depth": trial.suggest_int("max_depth", 3, 8),
        "subsample": trial.suggest_float("subsample", 0.6, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
        "min_child_weight": trial.suggest_int("min_child_weight", 1, 10),
        # LambdaMART specific
        "lambdarank_num_pair_per_sample": trial.suggest_int("lambdarank_num_pair_per_sample", 1, 10),
    }

    # Optional: adjust blending weights
    blend_weight_xgb = trial.suggest_float("blend_weight_xgb", 0.2, 0.8)
    
    # Initialize model with trial params
    ranker = F1LTRRanker(xgb_params=params, lgb_params=params, blend_weight_xgb=blend_weight_xgb)
    
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
    args = parser.parse_args()

    df = load_data()
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
        
    config["models"]["ltr_ranker"]["best_params"] = study.best_trial.params
    
    with open(config_path, "w") as f:
        yaml.safe_dump(config, f)
        
    logger.info(f"Saved best parameters to {config_path}")

if __name__ == "__main__":
    main()
