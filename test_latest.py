import asyncio
import pandas as pd
from api.main import lifespan, app, predict_full_race
from data.db import query_df

async def test_latest_race():
    # Fetch actual results for 2026 Round 4 (Miami)
    actual_results = query_df(
        "SELECT driver_id, constructor_id, position, status FROM results WHERE race_id = '2026_4' ORDER BY CAST(position AS INTEGER) ASC"
    )
    
    print("=== ACTUAL MIAMI 2026 RESULTS ===")
    for _, row in actual_results.head(5).iterrows():
        print(f"P{row['position']}: {row['driver_id']} ({row['constructor_id']}) - {row['status']}")

    print("\n=== MODEL PREDICTION FOR MIAMI 2026 ===")
    async with lifespan(app):
        res = predict_full_race(2026, 4)
        
        print("\nPredicted Grid Order:")
        for idx, d in enumerate(res.full_grid[:5]):
            print(f"P{idx+1}: {d.driver_id} ({d.constructor_id}) | Win Prob: {d.p1_probability*100:.1f}%")

asyncio.run(test_latest_race())
