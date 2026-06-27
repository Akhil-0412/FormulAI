"""Reliability features — Computed from actual race status data."""

import pandas as pd
from data.db import query_df


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
        """SELECT status FROM results
           WHERE driver_id = ? AND race_id < ?
           ORDER BY race_id DESC LIMIT 5""",
        (driver_id, race_id),
    )
    if not recent.empty:
        dnfs = recent["status"].apply(lambda s: not (s == "Finished" or (s and str(s).startswith("+")))).sum()
        features["driver_dnf_rate_rolling5"] = dnfs / len(recent)
    else:
        features["driver_dnf_rate_rolling5"] = 0.0

    # constructor_dnf_rate_rolling10 (using 10 entries = 5 races × 2 drivers)
    rel_recent = query_df(
        """SELECT status FROM results
           WHERE constructor_id = ? AND race_id < ?
           ORDER BY race_id DESC LIMIT 10""",
        (constructor_id, race_id),
    )
    if not rel_recent.empty:
        dnfs = rel_recent["status"].apply(lambda s: not (s == "Finished" or (s and str(s).startswith("+")))).sum()
        features["constructor_dnf_rate_rolling5"] = dnfs / len(rel_recent)
    else:
        features["constructor_dnf_rate_rolling5"] = 0.0

    # Constructor reliability trend: compare last 5 vs previous 5 races
    older = query_df(
        """SELECT status FROM results
           WHERE constructor_id = ? AND race_id < ?
           ORDER BY race_id DESC LIMIT 10 OFFSET 10""",
        (constructor_id, race_id),
    )
    if not older.empty and not rel_recent.empty:
        recent_dnf = rel_recent["status"].apply(lambda s: not (s == "Finished" or (s and str(s).startswith("+")))).mean()
        older_dnf = older["status"].apply(lambda s: not (s == "Finished" or (s and str(s).startswith("+")))).mean()
        features["constructor_reliability_trend"] = float(older_dnf - recent_dnf)  # Positive = improving
    else:
        features["constructor_reliability_trend"] = 0.0

    # Driver mechanical DNFs this season (non-crash retirements)
    season_status = query_df(
        """SELECT status FROM results
           WHERE driver_id = ? AND race_id < ? AND race_id LIKE ?""",
        (driver_id, race_id, f"{year}_%"),
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
