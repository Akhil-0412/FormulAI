from data.db import query_df
print("RESULTS SCHEMA:")
print(query_df("PRAGMA table_info(results)"))
print("\nQUALIFYING SCHEMA:")
print(query_df("PRAGMA table_info(qualifying)"))
