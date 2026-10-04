"""Reliability features — Computed from actual race status data."""

import pandas as pd
from data.db import is_finished_status, query_df, race_seq, race_seq_sql


def compute_reliability_features(
    constructor_id: str,
    driver_id: str,
    race_id: str
) -> dict:
    """Compute reliability features from actual DB data."""
    features = {}

    year = race_id.split("_")[0]

    # driver_dnf_rate_rolling5
    recent = query_df(
        f"""SELECT status FROM results
           WHERE driver_id = ? AND {race_seq_sql()} < ?
           ORDER BY {race_seq_sql()} DESC LIMIT 5""",
        (driver_id, race_seq(race_id)),
    )
    if not recent.empty:
        dnfs = recent["status"].apply(lambda s: not is_finished_status(s)).sum()
        features["driver_dnf_rate_rolling5"] = dnfs / len(recent)
    else:
        features["driver_dnf_rate_rolling5"] = 0.0

    # constructor_dnf_rate_rolling10 (using 10 entries = 5 races × 2 drivers)
    rel_recent = query_df(
        f"""SELECT status FROM results
           WHERE constructor_id = ? AND {race_seq_sql()} < ?
           ORDER BY {race_seq_sql()} DESC LIMIT 10""",
        (constructor_id, race_seq(race_id)),
    )
    if not rel_recent.empty:
        dnfs = rel_recent["status"].apply(lambda s: not is_finished_status(s)).sum()
        features["constructor_dnf_rate_rolling5"] = dnfs / len(rel_recent)
    else:
        features["constructor_dnf_rate_rolling5"] = 0.0

    # Constructor reliability trend: compare last 5 vs previous 5 races
    older = query_df(
        f"""SELECT status FROM results
           WHERE constructor_id = ? AND {race_seq_sql()} < ?
           ORDER BY {race_seq_sql()} DESC LIMIT 10 OFFSET 10""",
        (constructor_id, race_seq(race_id)),
    )
    if not older.empty and not rel_recent.empty:
        recent_dnf = rel_recent["status"].apply(lambda s: not is_finished_status(s)).mean()
        older_dnf = older["status"].apply(lambda s: not is_finished_status(s)).mean()
        features["constructor_reliability_trend"] = float(older_dnf - recent_dnf)  # Positive = improving
    else:
        features["constructor_reliability_trend"] = 0.0

    # Driver mechanical DNFs this season (non-crash retirements)
    season_status = query_df(
        f"""SELECT status FROM results
           WHERE driver_id = ? AND {race_seq_sql()} < ? AND race_id LIKE ?""",
        (driver_id, race_seq(race_id), f"{year}_%"),
    )
    if not season_status.empty:
        mechanical_keywords = ["Engine", "Gearbox", "Hydraulic", "Electrical",
                               "Power Unit", "Brakes", "Suspension", "Overheating",
                               "Oil", "Water", "Fuel"]
        mechanical_dnfs = season_status["status"].apply(
            lambda s: any(kw.lower() in str(s).lower() for kw in mechanical_keywords)
        ).sum()
        features["driver_car_issues_this_season"] = int(mechanical_dnfs)
    else:
        features["driver_car_issues_this_season"] = 0

    # Composite Survival Probability P(Finish)
    features["constructor_survival_prob"] = 1.0 - features["constructor_dnf_rate_rolling5"]

    return features
