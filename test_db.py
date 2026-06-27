from data.db import query_df
df = query_df("SELECT race_id, year, round, circuit_id FROM races WHERE year=2026")
print(df)
