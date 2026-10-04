"""v4 feature engine — temporal integrity and semantics, on synthetic tables."""

import numpy as np
import pandas as pd
import pytest

import features.fast_features as ff
from data.db import is_finished_status

DRIVERS = ("a", "b", "c", "d")
TEAMS = ("t1", "t1", "t2", "t2")


def _tables(n_races: int = 6) -> dict[str, pd.DataFrame]:
    """Three 2025 rounds then three 2026 rounds, random finishing orders."""
    rng = np.random.default_rng(0)
    races, results, quali = [], [], []
    for i in range(1, n_races + 1):
        year, rnd = (2025, i) if i <= 3 else (2026, i - 3)
        rid = f"{year}_{rnd}"
        races.append(dict(race_id=rid, year=year, round=rnd,
                          circuit_id="monza" if i % 2 else "monaco", race_date=""))
        for pos, idx in enumerate(rng.permutation(len(DRIVERS)), start=1):
            results.append(dict(race_id=rid, driver_id=DRIVERS[idx], constructor_id=TEAMS[idx],
                                grid=pos, position=pos, points=0.0,
                                status="Finished" if pos < 4 else "Lapped"))
            quali.append(dict(race_id=rid, driver_id=DRIVERS[idx], constructor_id=TEAMS[idx],
                              quali_pos=pos, q1_sec=80 + pos * 0.1, q2_sec=np.nan, q3_sec=np.nan))
    races = pd.DataFrame(races)
    races["seq"] = races["year"] * 100 + races["round"]
    return {
        "races": races,
        "results": pd.DataFrame(results),
        "quali": pd.DataFrame(quali),
        "weather": pd.DataFrame(columns=["race_id", "precipitation_prob"]),
    }


@pytest.fixture
def use_tables(monkeypatch):
    def apply(tables):
        states = ff.states_from_tables(tables)
        monkeypatch.setattr(ff, "_states", lambda: states)
        return states
    return apply


def _entries(tables, race_id):
    res = tables["results"]
    return res[res["race_id"] == race_id][["race_id", "driver_id", "constructor_id", "grid"]]


def test_features_never_see_the_target_race_or_later(use_tables):
    tables = _tables()
    use_tables(tables)
    target = _entries(tables, "2026_2")
    before = ff.build_features(target).set_index("driver_id")[ff.ALL_FEATURES].sort_index()

    scrambled = {k: v.copy() for k, v in tables.items()}
    seq = scrambled["races"].set_index("race_id")["seq"]
    later = scrambled["results"]["race_id"].map(seq) >= 202602
    scrambled["results"].loc[later, "position"] = (
        scrambled["results"].loc[later, "position"].iloc[::-1].to_numpy()
    )
    use_tables(scrambled)
    after = ff.build_features(target).set_index("driver_id")[ff.ALL_FEATURES].sort_index()

    pd.testing.assert_frame_equal(before, after)


def test_in_season_form_resets_but_career_history_carries(use_tables):
    tables = _tables()
    use_tables(tables)
    f = ff.build_features(_entries(tables, "2026_1"))
    assert (f["d_season_pts"] == 0).all()
    assert (f["d_season_races"] == 0).all()
    assert (f["d_races"] == 3).all()


def test_upcoming_race_without_and_with_qualifying(use_tables):
    tables = _tables()
    use_tables(tables)
    entries = pd.DataFrame({
        "race_id": "2026_9", "driver_id": ["a", "b"], "constructor_id": ["t1", "t1"],
        "circuit_id": "monza", "grid": np.nan,
    })
    pre = ff.build_features(entries)
    assert pre["d_races"].tolist() == [6, 6]
    assert pre["grid_pos"].isna().all()

    quali = pd.DataFrame({
        "race_id": "2026_9", "driver_id": ["a", "b"], "constructor_id": ["t1", "t1"],
        "quali_pos": [2, 1], "q1_sec": [80.5, 80.0], "q2_sec": np.nan, "q3_sec": np.nan,
    })
    post = ff.build_features(entries, extra_quali=quali).set_index("driver_id")
    assert post.loc["b", "grid_pos"] == 1
    assert post.loc["a", "q_gap_pct"] > 0
    assert post.loc["a", "teammate_grid_delta"] == 1


def test_lapped_cars_are_finishers_not_dnfs(use_tables):
    assert is_finished_status("Lapped")
    assert is_finished_status("+2 Laps")
    assert is_finished_status("Finished")
    assert not is_finished_status("Retired")
    assert not is_finished_status("Did not start")
    assert not is_finished_status(None)

    tables = _tables()
    use_tables(tables)
    f = ff.build_features(_entries(tables, "2026_3"))
    assert (f["d_dnf_ewm"] == 0).all()
