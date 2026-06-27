from data.db import query_df
from api.main import get_ensemble_predictions
from features.pre_race import build_pre_race_features
from models_v2.stage3_ensemble import enforce_podium_constraints

# Get the latest completed race with podium data
res = query_df("""
    SELECT r.race_id, r.year, r.round
    FROM races r
    JOIN results rs ON r.race_id = rs.race_id
    WHERE rs.position <= 3
    GROUP BY r.race_id
    ORDER BY r.year DESC, r.round DESC
    LIMIT 1
""")

if res.empty:
    print("No recent completed races found.")
    exit()

race_id = res.iloc[0]['race_id']
year = int(res.iloc[0]['year'])
round_number = int(res.iloc[0]['round'])

print(f"Testing on Latest Completed Race: {year} {race_id} (Round {round_number})")

# Get actual podium
actual = query_df(
    "SELECT position, driver_id FROM results WHERE race_id = ? AND position <= 3 ORDER BY position ASC",
    (race_id,)
)
print("\nACTUAL PODIUM:")
for _, row in actual.iterrows():
    print(f"P{int(row['position'])}: {row['driver_id']}")

# Generate Prediction
import api.main as api_main
from models_v2.ltr_ranker import F1LTRRanker
from config.settings import settings

api_main._ltr_model = F1LTRRanker.load(settings.abs_model_dir / "ltr_ranker.joblib")

race_df = build_pre_race_features(year, round_number)
prob_dict, pos_dict, _ = get_ensemble_predictions(race_df)
result = enforce_podium_constraints(prob_dict, pos_dict)

print("\nNEW MODEL PREDICTED PODIUM:")
for i, p in enumerate(result.podium):
    print(f"P{i+1}: {p.driver_id} ({p.probability*100:.1f}%)")

