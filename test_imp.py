from models_v2.stage2_xgb import Stage2XGB
from config.settings import settings

model = Stage2XGB.load(settings.abs_model_dir / "stage2_xgb.joblib")
imp = model.model.feature_importances_
cols = model.feature_columns
importances = sorted(zip(cols, imp), key=lambda x: x[1], reverse=True)

print("TOP 10 FEATURE IMPORTANCES:")
for f, v in importances[:10]:
    print(f"{f}: {v:.4f}")
