import pandas as pd
from data.db import query_df
df = query_df("SELECT race_id, COUNT(driver_id) FROM results WHERE race_id LIKE '2026_%' GROUP BY race_id")
print(df)
