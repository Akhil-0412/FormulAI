"""Development features — In-season team and driver progression."""

from data.db import query_df


def compute_development_features(driver_id: str, constructor_id: str, race_id: str) -> dict:
    """Compute development and in-season progression features from actual DB data."""
    features = {}

    year = race_id.split("_")[0]
    round_num = int(race_id.split("_")[1])

    # 1. Team Performance Delta vs R1 (actual average finish vs round 1)
    r1_id = f"{year}_1"
    r1_result = query_df(
        """SELECT AVG(position) as avg_pos FROM results
           WHERE constructor_id = ? AND race_id = ? AND position IS NOT NULL""",
        (constructor_id, r1_id),
    )
    recent_result = query_df(
        """SELECT AVG(position) as avg_pos FROM results
           WHERE constructor_id = ? AND race_id < ? AND position IS NOT NULL
           AND race_id LIKE ?
           ORDER BY race_id DESC LIMIT 10""",
        (constructor_id, race_id, f"{year}_%"),
    )

    r1_avg = r1_result.iloc[0]["avg_pos"] if not r1_result.empty and r1_result.iloc[0]["avg_pos"] else None
    recent_avg = recent_result.iloc[0]["avg_pos"] if not recent_result.empty and recent_result.iloc[0]["avg_pos"] else None

    if r1_avg is not None and recent_avg is not None:
        features["team_perf_delta_vs_r1"] = float(r1_avg - recent_avg)  # Positive = improving
    else:
        features["team_perf_delta_vs_r1"] = 0.0

    # 2. Team Rolling Pace Rank (constructor rank by avg points over last 3 races)
    constructor_points = query_df(
        """SELECT constructor_id, AVG(points) as avg_pts
           FROM results
           WHERE race_id < ? AND race_id IN (
               SELECT race_id FROM races WHERE race_id < ?
               ORDER BY year DESC, round DESC LIMIT 3
           )
           GROUP BY constructor_id
           ORDER BY avg_pts DESC""",
        (race_id, race_id),
    )
    if not constructor_points.empty:
        rank_list = constructor_points["constructor_id"].tolist()
        if constructor_id in rank_list:
            features["team_rolling_pace_rank"] = rank_list.index(constructor_id) + 1
        else:
            features["team_rolling_pace_rank"] = len(rank_list) + 1
    else:
        features["team_rolling_pace_rank"] = 5

    # 3. Driver Performance Delta vs R1
    d_r1 = query_df(
        """SELECT position FROM results
           WHERE driver_id = ? AND race_id = ? AND position IS NOT NULL""",
        (driver_id, r1_id),
    )
    d_recent = query_df(
        """SELECT AVG(position) as avg_pos FROM results
           WHERE driver_id = ? AND race_id < ? AND position IS NOT NULL
           AND race_id LIKE ?""",
        (driver_id, race_id, f"{year}_%"),
    )

    d_r1_pos = d_r1.iloc[0]["position"] if not d_r1.empty else None
    d_recent_avg = d_recent.iloc[0]["avg_pos"] if not d_recent.empty and d_recent.iloc[0]["avg_pos"] else None

    if d_r1_pos is not None and d_recent_avg is not None:
        features["driver_perf_delta_vs_r1"] = float(d_r1_pos - d_recent_avg)  # Positive = improving
    else:
        features["driver_perf_delta_vs_r1"] = 0.0

    # 4. Season progress (what fraction of the season has elapsed)
    features["season_round"] = round_num
    features["season_progress"] = round_num / 24.0  # Approximate max rounds

    return features
