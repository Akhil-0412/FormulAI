import pandas as pd
from data.db import query_df

# Fetch the starting grid (qualifying results) for Miami 2026 (Round 4)
grid = query_df(
    "SELECT driver_id, constructor_id, grid FROM results WHERE race_id = '2026_4' ORDER BY CAST(grid AS INTEGER) ASC LIMIT 5"
)
print("=== MIAMI 2026 QUALIFYING GRID ===")
print(grid)
