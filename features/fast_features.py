"""Vectorised, leak-free pre-race features (feature set v4).

The legacy builder in `features.pre_race` issues ~25 SQL queries per driver
and replays the whole Elo history once per race, so a 2014-2026 rebuild takes
~40 minutes. This module loads each table once and computes the same kind of
signal with pandas group/ewm/merge_asof, so the full history builds in
seconds — which is what makes walk-forward model selection affordable.

Temporal integrity is structural rather than per-query: every rolling
quantity is stored as a "state after race" table and joined onto a target
race with `merge_asof(..., allow_exact_matches=False)`, i.e. strictly from
races before it. The same code path serves training rows and an upcoming
race that has no results yet, so there is no train/serve skew.

Feature groups
--------------
* quali     — grid slot, quali position, gap to pole (%), teammate grid gap.
              Only known after qualifying; `PREQUALI_FEATURES` excludes them.
* driver    — exponentially-weighted finish/points/podium/grid/DNF form,
              in-season points, circuit history, Elo.
* team      — the same for the constructor (both cars), in-season form, Elo.
              F1 results are dominated by the car (van Kesteren & Bergkamp
              2023 put it at ~88% of the driver/constructor variance), and in
              a regulation-reset year only in-season team form reflects it.
* field     — within-race ranks of the key form signals: a ranker sees one
              row at a time, so "best car in this field" has to be explicit.
* context   — round, regulation-reset flags, street circuit, rain.
"""

from __future__ import annotations

import logging
from functools import lru_cache

import numpy as np
import pandas as pd

from data.db import is_finished_status, query_df

logger = logging.getLogger(__name__)

# Seasons that opened a new technical regulation set. Cross-season priors
# (Elo, last-season form) say much less about the first races of these years.
REG_RESET_YEARS = (2014, 2017, 2022, 2026)

# Constructor lineage, so cross-season team form survives a rebrand.
TEAM_LINEAGE = {
    "toro_rosso": "rb", "alphatauri": "rb",
    "force_india": "aston_martin", "racing_point": "aston_martin",
    "lotus_f1": "alpine", "renault": "alpine",
    "sauber": "audi", "alfa": "audi",
    "marussia": "manor",
}

STREET_CIRCUITS = {
    "monaco", "baku", "singapore", "marina_bay", "jeddah", "miami", "vegas",
    "las_vegas", "madring", "albert_park", "montreal", "sochi",
}

F1_POINTS = {1: 25, 2: 18, 3: 15, 4: 12, 5: 10, 6: 8, 7: 6, 8: 4, 9: 2, 10: 1}

_EWM_HALFLIFE = 4.0  # races

QUALI_FEATURES = [
    "grid_pos", "quali_pos", "q_gap_pct", "q1_gap_pct",
    "teammate_grid_delta", "grid_rank_in_field",
]

DRIVER_FEATURES = [
    "d_finish_ewm", "d_points_ewm", "d_podium_ewm", "d_win_ewm", "d_grid_ewm",
    "d_gain_ewm", "d_dnf_ewm", "d_races", "d_elo",
    "d_season_pts", "d_season_avg_finish", "d_season_avg_grid", "d_season_podiums",
    "d_season_races", "d_circuit_avg_finish", "d_circuit_n", "d_last_finish",
    "d_vs_teammate_ewm",
]

TEAM_FEATURES = [
    "t_finish_ewm", "t_best_finish_ewm", "t_points_ewm", "t_grid_ewm", "t_dnf_ewm",
    "t_elo", "t_season_pts", "t_season_avg_finish", "t_season_avg_grid",
    "t_season_races", "t_circuit_avg_finish",
]

FIELD_FEATURES = [
    "rank_t_finish_ewm", "rank_t_grid_ewm", "rank_d_finish_ewm", "rank_d_grid_ewm",
    "rank_d_elo", "rank_t_elo", "rank_d_season_pts", "rank_t_season_pts",
    "gap_t_finish_ewm", "gap_t_grid_ewm",
]

CONTEXT_FEATURES = [
    "season_round", "is_reg_reset_year", "era_season", "is_street", "rain_prob",
]

# Saturday sprint finishing position on sprint weekends (NaN otherwise).
# Known before the Grand Prix, like qualifying, so excluded pre-qualifying.
SPRINT_FEATURES = ["sprint_pos"]

ALL_FEATURES = QUALI_FEATURES + DRIVER_FEATURES + TEAM_FEATURES + FIELD_FEATURES + CONTEXT_FEATURES
PREQUALI_FEATURES = [f for f in ALL_FEATURES if f not in QUALI_FEATURES]

LABEL_COLUMNS = ["finish_position", "relevance", "is_podium", "is_dnf"]


# ── Table loading ────────────────────────────────────────────────────────

def _seq(year: pd.Series, rnd: pd.Series) -> pd.Series:
    return year.astype(int) * 100 + rnd.astype(int)


def load_tables() -> dict[str, pd.DataFrame]:
    races = query_df("SELECT race_id, year, round, circuit_id, race_date FROM races")
    races["seq"] = _seq(races["year"], races["round"])

    results = query_df(
        "SELECT race_id, driver_id, constructor_id, grid, position, status, points FROM results"
    )
    # Placeholder rows written for an upcoming race are not outcomes.
    results = results[results["status"].fillna("") != "Pending"].copy()

    quali = query_df(
        "SELECT race_id, driver_id, constructor_id, position AS quali_pos, "
        "q1_sec, q2_sec, q3_sec FROM qualifying"
    )
    weather = query_df("SELECT race_id, precipitation_prob FROM weather")
    try:
        sprint = query_df("SELECT race_id, driver_id, position AS sprint_pos FROM sprint_results")
    except Exception:  # DB created before the sprint table existed
        sprint = pd.DataFrame(columns=["race_id", "driver_id", "sprint_pos"])
    return {"races": races, "results": results, "quali": quali, "weather": weather, "sprint": sprint}


# ── History ("state after race") tables ──────────────────────────────────

def _history(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """One row per completed (race, driver) with per-race outcome measures."""
    res = tables["results"].merge(tables["races"], on="race_id", how="inner")
    res = res.dropna(subset=["position"]).copy()
    res["position"] = res["position"].astype(float)
    res["team"] = res["constructor_id"].map(lambda c: TEAM_LINEAGE.get(c, c))
    n_entries = res.groupby("race_id")["driver_id"].transform("count")
    res["grid_clean"] = np.where(res["grid"].fillna(0) > 0, res["grid"], n_entries)
    res["finished"] = res["status"].map(is_finished_status).astype(float)
    res["dnf"] = 1.0 - res["finished"]
    res["pts_std"] = res["position"].map(lambda p: F1_POINTS.get(int(p), 0)).astype(float)
    res["podium"] = (res["position"] <= 3).astype(float)
    res["win"] = (res["position"] == 1).astype(float)
    res["gain"] = np.where(res["finished"] == 1, res["grid_clean"] - res["position"], np.nan)

    # Finish relative to teammate(s): positive = beat the other car.
    team_mean = res.groupby(["race_id", "constructor_id"])["position"].transform("mean")
    team_n = res.groupby(["race_id", "constructor_id"])["position"].transform("count")
    mate_mean = (team_mean * team_n - res["position"]) / (team_n - 1).replace(0, np.nan)
    res["vs_mate"] = mate_mean - res["position"]
    return res.sort_values(["seq", "position"], kind="stable").reset_index(drop=True)


def _ewm_state(df: pd.DataFrame, key: str, cols: dict[str, str]) -> pd.DataFrame:
    """Per-key exponentially weighted state *after* each race.

    `df` must already be in chronological order; every assignment below is
    index-aligned, so rows sharing a race can never be shuffled against each
    other.
    """
    out = df[[key, "seq", "year"]].copy()
    g = df.groupby(key, sort=False)
    for src, dst in cols.items():
        out[dst] = g[src].transform(
            lambda s: s.ewm(halflife=_EWM_HALFLIFE, ignore_na=True).mean()
        )
    return out


def _driver_states(hist: pd.DataFrame) -> dict[str, pd.DataFrame]:
    ewm = _ewm_state(hist, "driver_id", {
        "position": "d_finish_ewm", "pts_std": "d_points_ewm", "podium": "d_podium_ewm",
        "win": "d_win_ewm", "grid_clean": "d_grid_ewm", "gain": "d_gain_ewm",
        "dnf": "d_dnf_ewm", "vs_mate": "d_vs_teammate_ewm",
    })
    h = hist
    ewm["d_races"] = h.groupby("driver_id").cumcount() + 1
    ewm["d_last_finish"] = h["position"]

    season = h[["driver_id", "year", "seq"]].copy()
    gs = h.groupby(["driver_id", "year"], sort=False)
    season["d_season_pts"] = gs["pts_std"].cumsum()
    season["d_season_podiums"] = gs["podium"].cumsum()
    season["d_season_races"] = gs.cumcount() + 1
    season["d_season_avg_finish"] = gs["position"].cumsum() / season["d_season_races"]
    season["d_season_avg_grid"] = gs["grid_clean"].cumsum() / season["d_season_races"]

    circ = h[["driver_id", "circuit_id", "seq"]].copy()
    gc = h.groupby(["driver_id", "circuit_id"], sort=False)
    circ["d_circuit_n"] = gc.cumcount() + 1
    circ["d_circuit_avg_finish"] = gc["position"].cumsum() / circ["d_circuit_n"]
    return {"ewm": ewm, "season": season, "circuit": circ}


def _team_states(hist: pd.DataFrame) -> dict[str, pd.DataFrame]:
    per_race = (
        hist.groupby(["race_id", "team"], as_index=False)
        .agg(seq=("seq", "first"), year=("year", "first"), circuit_id=("circuit_id", "first"),
             t_pos=("position", "mean"), t_best=("position", "min"),
             t_pts=("pts_std", "sum"), t_grid=("grid_clean", "mean"), t_dnf=("dnf", "mean"))
        .sort_values("seq", kind="stable")
        .reset_index(drop=True)
    )
    ewm = _ewm_state(per_race, "team", {
        "t_pos": "t_finish_ewm", "t_best": "t_best_finish_ewm", "t_pts": "t_points_ewm",
        "t_grid": "t_grid_ewm", "t_dnf": "t_dnf_ewm",
    })

    season = per_race[["team", "year", "seq"]].copy()
    gs = per_race.groupby(["team", "year"], sort=False)
    season["t_season_pts"] = gs["t_pts"].cumsum()
    season["t_season_races"] = gs.cumcount() + 1
    season["t_season_avg_finish"] = gs["t_pos"].cumsum() / season["t_season_races"]
    season["t_season_avg_grid"] = gs["t_grid"].cumsum() / season["t_season_races"]

    circ = per_race[["team", "circuit_id", "seq"]].copy()
    gc = per_race.groupby(["team", "circuit_id"], sort=False)
    circ["t_circuit_avg_finish"] = gc["t_pos"].cumsum() / (gc.cumcount() + 1)
    return {"ewm": ewm, "season": season, "circuit": circ}


def _elo_states(hist: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Pairwise Elo for drivers and teams, with between-season regression.

    Same pairwise update as `features.elo` (K decays with experience, update
    averaged over opponents), plus regression to the mean at each new season
    — strongest for teams after a regulation reset, when last year's car
    rating is mostly obsolete.
    """
    d_elo: dict[str, float] = {}
    t_elo: dict[str, float] = {}
    d_n: dict[str, int] = {}
    t_n: dict[str, int] = {}
    d_rows, t_rows = [], []
    last_year = None

    for (seq, year), race in hist.groupby(["seq", "year"], sort=True):
        if last_year is not None and year != last_year:
            t_keep = 0.35 if year in REG_RESET_YEARS else 0.7
            t_elo = {k: 1500 + (v - 1500) * t_keep for k, v in t_elo.items()}
            d_elo = {k: 1500 + (v - 1500) * 0.85 for k, v in d_elo.items()}
        last_year = year

        drivers = race["driver_id"].to_numpy()
        teams = race["team"].to_numpy()
        pos = race["position"].to_numpy(dtype=float)
        n = len(drivers)
        if n < 2:
            continue

        actual = (pos[:, None] < pos[None, :]).astype(float) + 0.5 * (pos[:, None] == pos[None, :])
        np.fill_diagonal(actual, 0.0)

        def update(ratings: np.ndarray, counts: np.ndarray) -> np.ndarray:
            expected = 1.0 / (1.0 + 10 ** ((ratings[None, :] - ratings[:, None]) / 400.0))
            np.fill_diagonal(expected, 0.0)
            k = 48.0 - np.minimum(counts / 40.0, 1.0) * 32.0
            return k * (actual - expected).sum(axis=1) / (n - 1)

        dr = np.array([d_elo.get(d, 1500.0) for d in drivers])
        dc = np.array([d_n.get(d, 0) for d in drivers], dtype=float)
        d_upd = update(dr, dc)
        for d, r, u in zip(drivers, dr, d_upd):
            d_elo[d] = r + u
            d_n[d] = d_n.get(d, 0) + 1
            d_rows.append((d, seq, year, d_elo[d]))

        tr = np.array([t_elo.get(t, 1500.0) for t in teams])
        tc = np.array([t_n.get(t, 0) for t in teams], dtype=float)
        t_upd = pd.Series(update(tr, tc)).groupby(teams).mean()
        for t, u in t_upd.items():
            t_elo[t] = t_elo.get(t, 1500.0) + u
            t_n[t] = t_n.get(t, 0) + 1
            t_rows.append((t, seq, year, t_elo[t]))

    d_state = pd.DataFrame(d_rows, columns=["driver_id", "seq", "year", "d_elo"])
    t_state = pd.DataFrame(t_rows, columns=["team", "seq", "year", "t_elo"])
    return d_state, t_state


def states_from_tables(tables: dict[str, pd.DataFrame]) -> dict:
    """All history states for a set of tables (DB-free; used by tests too)."""
    hist = _history(tables)
    d_elo, t_elo = _elo_states(hist)
    return {
        "tables": tables,
        "hist": hist,
        "driver": _driver_states(hist),
        "team": _team_states(hist),
        "d_elo": d_elo,
        "t_elo": t_elo,
    }


@lru_cache(maxsize=4)
def _cached_states(cache_key: tuple) -> dict:
    return states_from_tables(load_tables())


def _states() -> dict:
    """History states, rebuilt whenever the results/qualifying tables change."""
    key = query_df(
        "SELECT (SELECT COUNT(*) FROM results) AS n_res, "
        "(SELECT COUNT(*) FROM qualifying) AS n_q, "
        "(SELECT COUNT(*) FROM races) AS n_races, "
        "(SELECT COUNT(*) FROM sqlite_master WHERE name = 'sprint_results') AS has_sprint, "
        "(SELECT COALESCE(SUM(position), 0) FROM results) AS s_pos"
    ).iloc[0]
    return _cached_states(tuple(int(v) for v in key))


def clear_cache() -> None:
    _cached_states.cache_clear()


# ── Joining state onto target entries ────────────────────────────────────

def _asof(target: pd.DataFrame, state: pd.DataFrame, by: list[str], cols: list[str]) -> pd.DataFrame:
    """Attach the latest state strictly before each target race."""
    left = target[["_row", "seq"] + by].sort_values("seq")
    right = state[["seq"] + by + cols].sort_values("seq")
    merged = pd.merge_asof(
        left, right, on="seq", by=by, allow_exact_matches=False, direction="backward"
    )
    return merged.set_index("_row")[cols]


def build_features(
    entries: pd.DataFrame,
    extra_quali: pd.DataFrame | None = None,
    extra_sprint: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Compute v4 features for arbitrary (race, driver) entries.

    Args:
        entries: columns race_id, driver_id, constructor_id and optionally
            `grid` (actual starting slot; 0 = pit lane) and `circuit_id`
            (required for a race not in the DB). Races may be completed or
            upcoming; only strictly-earlier races feed history.
        extra_quali: qualifying rows for races not in the DB yet (same
            columns as the qualifying table, with `quali_pos`), e.g. fetched
            live for this weekend.
        extra_sprint: sprint rows (race_id, driver_id, sprint_pos) for races
            not in the DB yet.

    Returns:
        `entries` plus every column in ALL_FEATURES (NaN where unknown).
    """
    st = _states()
    races = st["tables"]["races"]

    tgt = entries.copy().reset_index(drop=True)
    tgt["_row"] = np.arange(len(tgt))
    if "grid" not in tgt.columns:
        tgt["grid"] = np.nan
    meta = races.set_index("race_id")[["year", "round", "seq", "circuit_id"]]
    missing = sorted(set(tgt["race_id"]) - set(meta.index))
    if missing:
        # An upcoming race that isn't in the DB yet: the caller supplies the
        # circuit, year/round come from the id.
        if "circuit_id" not in tgt.columns:
            raise ValueError(f"circuit_id required for races not in the DB: {missing}")
        extra = tgt[tgt["race_id"].isin(missing)].drop_duplicates("race_id")[["race_id", "circuit_id"]]
        parts = extra["race_id"].str.split("_")
        extra = extra.assign(year=parts.str[0].astype(int), round=parts.str[1].astype(int))
        extra["seq"] = _seq(extra["year"], extra["round"])
        meta = pd.concat([meta, extra.set_index("race_id")[meta.columns]])
    for col in ("year", "round", "seq", "circuit_id"):
        tgt[col] = tgt["race_id"].map(meta[col])
    tgt["seq"] = tgt["seq"].astype("int64")
    tgt["team"] = tgt["constructor_id"].map(lambda c: TEAM_LINEAGE.get(c, c))

    # ── driver / team history ────────────────────────────────────────
    drv, team = st["driver"], st["team"]
    pieces = [
        _asof(tgt, drv["ewm"], ["driver_id"],
              ["d_finish_ewm", "d_points_ewm", "d_podium_ewm", "d_win_ewm", "d_grid_ewm",
               "d_gain_ewm", "d_dnf_ewm", "d_vs_teammate_ewm", "d_races", "d_last_finish"]),
        _asof(tgt, drv["season"], ["driver_id", "year"],
              ["d_season_pts", "d_season_podiums", "d_season_races",
               "d_season_avg_finish", "d_season_avg_grid"]),
        _asof(tgt, drv["circuit"], ["driver_id", "circuit_id"],
              ["d_circuit_n", "d_circuit_avg_finish"]),
        _asof(tgt, st["d_elo"], ["driver_id"], ["d_elo"]),
        _asof(tgt, team["ewm"], ["team"],
              ["t_finish_ewm", "t_best_finish_ewm", "t_points_ewm", "t_grid_ewm", "t_dnf_ewm"]),
        _asof(tgt, team["season"], ["team", "year"],
              ["t_season_pts", "t_season_races", "t_season_avg_finish", "t_season_avg_grid"]),
        _asof(tgt, team["circuit"], ["team", "circuit_id"], ["t_circuit_avg_finish"]),
        _asof(tgt, st["t_elo"], ["team"], ["t_elo"]),
    ]
    feats = pd.concat(pieces, axis=1).reindex(tgt["_row"])
    feats.index = tgt.index
    tgt = pd.concat([tgt, feats], axis=1)

    # Elo carries over between seasons with regression; mirror that for a
    # driver/team whose last rating predates this season's reset.
    tgt["d_elo"] = tgt["d_elo"].fillna(1500.0)
    tgt["t_elo"] = tgt["t_elo"].fillna(1500.0)
    for col in ("d_races", "d_season_pts", "d_season_podiums", "d_season_races",
                "d_circuit_n", "t_season_pts", "t_season_races"):
        tgt[col] = tgt[col].fillna(0.0)

    # ── qualifying (this race) ───────────────────────────────────────
    q = st["tables"]["quali"]
    if extra_quali is not None and not extra_quali.empty:
        q = pd.concat([q[~q["race_id"].isin(extra_quali["race_id"])], extra_quali], ignore_index=True)
    q = q[q["race_id"].isin(tgt["race_id"])].copy()
    if not q.empty:
        q["q_best"] = q[["q1_sec", "q2_sec", "q3_sec"]].min(axis=1)
        pole = q.groupby("race_id")["q_best"].transform("min")
        q["q_gap_pct"] = (q["q_best"] / pole - 1.0) * 100.0
        q1_best = q.groupby("race_id")["q1_sec"].transform("min")
        q["q1_gap_pct"] = (q["q1_sec"] / q1_best - 1.0) * 100.0
        tgt = tgt.merge(
            q[["race_id", "driver_id", "quali_pos", "q_gap_pct", "q1_gap_pct"]],
            on=["race_id", "driver_id"], how="left",
        )
    else:
        tgt[["quali_pos", "q_gap_pct", "q1_gap_pct"]] = np.nan

    n_field = tgt.groupby("race_id")["driver_id"].transform("count")
    grid = pd.to_numeric(tgt["grid"], errors="coerce")
    grid = np.where(grid == 0, n_field, grid)  # pit-lane start
    tgt["grid_pos"] = pd.Series(grid, index=tgt.index).fillna(tgt["quali_pos"])
    mate_grid = tgt.groupby(["race_id", "constructor_id"])["grid_pos"].transform("sum")
    mate_n = tgt.groupby(["race_id", "constructor_id"])["grid_pos"].transform("count")
    tgt["teammate_grid_delta"] = tgt["grid_pos"] - (mate_grid - tgt["grid_pos"]) / (mate_n - 1).replace(0, np.nan)
    tgt["grid_rank_in_field"] = tgt.groupby("race_id")["grid_pos"].rank(method="min")

    # ── sprint (this weekend) ────────────────────────────────────────
    sp = st["tables"].get("sprint", pd.DataFrame(columns=["race_id", "driver_id", "sprint_pos"]))
    if extra_sprint is not None and not extra_sprint.empty:
        sp = pd.concat([sp[~sp["race_id"].isin(extra_sprint["race_id"])],
                        extra_sprint[["race_id", "driver_id", "sprint_pos"]]], ignore_index=True)
    sp = sp[sp["race_id"].isin(tgt["race_id"])].drop_duplicates(["race_id", "driver_id"])
    tgt = tgt.merge(sp, on=["race_id", "driver_id"], how="left")
    tgt["sprint_pos"] = pd.to_numeric(tgt["sprint_pos"], errors="coerce")

    # ── field-relative ───────────────────────────────────────────────
    by_race = tgt.groupby("race_id")
    for col, ascending in [
        ("t_finish_ewm", True), ("t_grid_ewm", True), ("d_finish_ewm", True),
        ("d_grid_ewm", True), ("d_elo", False), ("t_elo", False),
        ("d_season_pts", False), ("t_season_pts", False),
    ]:
        tgt[f"rank_{col}"] = by_race[col].rank(ascending=ascending, method="min")
    tgt["gap_t_finish_ewm"] = tgt["t_finish_ewm"] - by_race["t_finish_ewm"].transform("min")
    tgt["gap_t_grid_ewm"] = tgt["t_grid_ewm"] - by_race["t_grid_ewm"].transform("min")

    # ── context ──────────────────────────────────────────────────────
    tgt["season_round"] = tgt["round"].astype(float)
    tgt["is_reg_reset_year"] = tgt["year"].isin(REG_RESET_YEARS).astype(float)
    tgt["era_season"] = tgt["year"].map(lambda y: y - max(r for r in REG_RESET_YEARS if r <= y))
    tgt["is_street"] = tgt["circuit_id"].isin(STREET_CIRCUITS).astype(float)
    rain = st["tables"]["weather"].set_index("race_id")["precipitation_prob"]
    tgt["rain_prob"] = tgt["race_id"].map(rain)

    return tgt.drop(columns=["_row"])


def build_training_frame(start_year: int = 2014, end_year: int = 2100) -> pd.DataFrame:
    """Features + labels for every completed race in [start_year, end_year]."""
    st = _states()
    hist = st["hist"]
    hist = hist[(hist["year"] >= start_year) & (hist["year"] <= end_year)]
    entries = hist[["race_id", "driver_id", "constructor_id", "grid"]].copy()
    df = build_features(entries)
    labels = hist.set_index(["race_id", "driver_id"])
    key = pd.MultiIndex.from_frame(df[["race_id", "driver_id"]])
    df["finish_position"] = labels["position"].reindex(key).values
    df["relevance"] = df["finish_position"].map(lambda p: F1_POINTS.get(int(p), 0)).astype(float)
    df["is_podium"] = (df["finish_position"] <= 3).astype(int)
    df["is_dnf"] = labels["dnf"].reindex(key).values
    # Driver order, NOT finishing order: anything that later breaks a score
    # tie by row position must not be able to read the result off the row.
    return df.sort_values(["seq", "driver_id"]).reset_index(drop=True)


def race_entries(race_id: str) -> pd.DataFrame:
    """The field for one race in the DB: results if raced, else qualifying."""
    st = _states()
    res = st["tables"]["results"]
    rows = res[res["race_id"] == race_id]
    if not rows.empty:
        return rows[["race_id", "driver_id", "constructor_id", "grid"]].reset_index(drop=True)
    q = st["tables"]["quali"]
    rows = q[q["race_id"] == race_id]
    return rows[["race_id", "driver_id", "constructor_id"]].assign(grid=np.nan).reset_index(drop=True)


def build_race_features(race_id: str) -> pd.DataFrame:
    """v4 features for one race already in the DB (completed or quali-only)."""
    entries = race_entries(race_id)
    if entries.empty:
        return pd.DataFrame()
    return build_features(entries)
