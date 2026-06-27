import logging
import numpy as np
import pandas as pd
import torch
from pytorch_tabnet.tab_model import TabNetClassifier
from sklearn.metrics import roc_auc_score, f1_score

from models_v2.stage1_prerace import PreRacePredictor
from features.feature_store import get_training_features, get_X_y

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger(__name__)

def evaluate_2026_chunks():
    logger.info("Rebuilding feature cache for 2018-2026...")
    df = get_training_features(start_year=2018, end_year=2026, force_rebuild=True)
    
    if "year" not in df.columns:
        df["year"] = df["race_id"].str.split("_").str[0].astype(int)

    # 1. Identify 2026 races and split chronologically
    df_2026 = df[df["year"] == 2026]
    races_2026 = sorted(df_2026["race_id"].unique())
    
    N = len(races_2026)
    if N < 3:
        logger.error(f"Not enough 2026 races to split into 3 chunks. Found: {N} races.")
        return

    chunk_size = N // 3
    train_races = races_2026[:chunk_size]
    val_races = races_2026[chunk_size: 2 * chunk_size]
    test_races = races_2026[2 * chunk_size:]

    logger.info(f"2026 Races found: {N}")
    logger.info(f"Included in Training (2018-2025 + {len(train_races)} races): {train_races}")
    logger.info(f"Included in Validation ({len(val_races)} races): {val_races}")
    logger.info(f"Included in Testing ({len(test_races)} races): {test_races}")

    # 2. Build Datasets
    train_df = df[(df["year"] <= 2025) | (df["race_id"].isin(train_races))]
    val_df = df[df["race_id"].isin(val_races)]
    test_df = df[df["race_id"].isin(test_races)]

    X_train, y_train_position = get_X_y(train_df, "finish_position")
    y_train_position = y_train_position.fillna(20) / 20.0
    y_train_dnf = train_df.get("is_dnf", pd.Series([0]*len(train_df)))
    y_train_stops = train_df.get("pit_stops", pd.Series([1]*len(train_df)))
    y_train_pace = train_df.get("pace_delta", pd.Series([0.0]*len(train_df)))

    X_val, y_val_position = get_X_y(val_df, "finish_position")
    y_val_position = y_val_position.fillna(20) / 20.0
    
    X_test, y_test_position = get_X_y(test_df, "finish_position")
    y_test_position = y_test_position.fillna(20) / 20.0

    # 3. Train Stage 1
    logger.info("Training Stage 1 (XGBoost Heads) on Training Set...")
    stage1 = PreRacePredictor()
    stage1.fit(X_train, y_train_dnf, y_train_stops, y_train_pace, optimize=False)

    # 4. Generate Stage 1 Predictions for Stage 2
    logger.info("Generating Stage 1 features for Meta-Learner...")
    train_s1 = stage1.predict_batch(X_train)
    val_s1 = stage1.predict_batch(X_val)
    test_s1 = stage1.predict_batch(X_test)

    # Enrich X with Stage 1 predictions
    def enrich_features(X_base, s1_preds):
        X_en = X_base.copy()
        X_en["pred_dnf"] = np.asarray(s1_preds["p_dnf"])
        X_en["pred_stops"] = np.asarray(s1_preds["expected_stops"])
        X_en["pred_pace"] = np.asarray(s1_preds["pace_delta"])
        # Filter to numeric columns only
        num_cols = X_en.select_dtypes(include=["number"]).columns
        X_num = X_en[num_cols].replace([np.inf, -np.inf], np.nan)
        return X_num.fillna(X_num.median()).fillna(0)

    X_train_en = enrich_features(X_train, train_s1)
    X_val_en = enrich_features(X_val, val_s1)
    X_test_en = enrich_features(X_test, test_s1)

    # 5. Train Stage 2 (XGBoost)
    from models_v2.stage2_xgb import Stage2XGB
    
    logger.info(f"Training Stage 2 (XGBoost Meta-Learner) on Val Set ({len(X_train_en.columns)} features)...")
    tabnet = Stage2XGB()
    tabnet.fit(X_train=X_train_en, y_train=y_train_position, X_valid=X_val_en, y_valid=y_val_position)

    # 6. Test on Test Set
    logger.info("Testing ensemble on Test Chunk...")
    test_preds_position = tabnet.predict(X_test_en)
    
    test_df = test_df.copy()
    test_df["pred_position"] = test_preds_position

    print(" === 2026 RACE PERFORMANCE (TEST CHUNK) ===")
    print("="*50)
    
    total_correct = 0
    race_ids = test_df["race_id"].unique()
    
    for race_id in sorted(race_ids):
        race_df = test_df[test_df["race_id"] == race_id]
        
        actual_podium = race_df[race_df["is_podium"] == 1]["driver_id"].tolist()
        predicted_podium = race_df.sort_values("pred_position", ascending=True).head(3)["driver_id"].tolist()
        
        correct = len(set(actual_podium) & set(predicted_podium))
        total_correct += correct
        
        print(f"Race: {race_id}")
        print(f"  Actual Podium:    {', '.join(actual_podium)}")
        print(f"  Predicted Podium: {', '.join(predicted_podium)}")
        print(f"  Correctly Guessed: {correct}/3\n")
        
    print(f"Average Correct Podium Predictions per Race: {total_correct / len(race_ids):.2f} / 3")
    print("="*50)

if __name__ == "__main__":
    evaluate_2026_chunks()
