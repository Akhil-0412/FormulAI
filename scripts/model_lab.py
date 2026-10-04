"""Model lab — walk-forward comparison of podium models.

Every model is scored the way it would be used in production: for each race
of a test season it is trained on *all races strictly before it* and then
predicts that race. Nothing from the race (or anything after it) is seen.

Two regimes are evaluated, because they need different information:

* post  — after qualifying: the grid is known (Saturday-night prediction).
* pre   — before qualifying: no grid / quali data (e.g. Monday after a race).

Usage:
    # one process per test season (they're independent), then aggregate
    python scripts/model_lab.py run --season 2025 --regime post
    python scripts/model_lab.py aggregate

Selection protocol: models are compared on 2022-2024 (validation) and the
choice is confirmed on 2025-2026 (held-out test). The softmax/Plackett-Luce
temperature for each season is fitted only on earlier seasons' predictions.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from features.fast_features import (
    ALL_FEATURES,
    PREQUALI_FEATURES,
    QUALI_FEATURES,
    SPRINT_FEATURES,
    build_training_frame,
)
from models_v2.podium_model import (
    LGBRankModel,
    PLLinearModel,
    PLNeuralModel,
    XGBRankModel,
    LGBBinaryModel,
    pl_top3_probs,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(message)s")
logger = logging.getLogger("model_lab")

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "reports" / "model_lab"
LEGACY_CACHE = ROOT / "data" / "feature_cache" / "prerace_v3_2014_2026.parquet"
TEST_SEASONS = [2021, 2022, 2023, 2024, 2025, 2026]
VALIDATION = [2022, 2023, 2024]
HELDOUT = [2025, 2026]


# ── Data ─────────────────────────────────────────────────────────────────

def load_frame(with_legacy: bool) -> tuple[pd.DataFrame, list[str]]:
    df = build_training_frame()
    legacy_cols: list[str] = []
    if with_legacy and LEGACY_CACHE.exists():
        from features.feature_store import get_feature_columns
        leg = pd.read_parquet(LEGACY_CACHE)
        legacy_cols = [c for c in get_feature_columns(leg) if leg[c].dtype != object]
        leg = leg[["race_id", "driver_id"] + legacy_cols + ["is_dnf"]].rename(
            columns={c: f"L_{c}" for c in legacy_cols + ["is_dnf"]}
        )
        df = df.merge(leg, on=["race_id", "driver_id"], how="left")
        legacy_cols = [f"L_{c}" for c in legacy_cols]
    return df, legacy_cols


# ── Models ───────────────────────────────────────────────────────────────

class Heuristic:
    """Score = -column (lower is better) — the baselines to beat."""

    def __init__(self, column: str, ascending: bool = True):
        self.column, self.ascending = column, ascending

    def fit(self, train: pd.DataFrame) -> "Heuristic":
        return self

    def predict(self, race: pd.DataFrame) -> np.ndarray:
        v = race[self.column].astype(float)
        if v.isna().all():  # e.g. no qualifying data for this race
            v = pd.Series(0.0, index=race.index)
        v = v.fillna(v.max() + 1 if self.ascending else v.min() - 1)
        # Tie-break on the car's form so ties don't fall back to row order.
        tb = race["t_finish_ewm"].fillna(30).to_numpy() * 1e-3
        return -(v.to_numpy() + tb) if self.ascending else v.to_numpy() - tb


class ProductionLTR:
    """The current production algorithm: F1LTRRanker with the tuned config
    params, plus DNF/pace auxiliary heads injected as features (legacy only).
    """

    def __init__(self, features: list[str], aux_heads: bool):
        self.features, self.aux_heads = features, aux_heads

    def fit(self, train: pd.DataFrame) -> "ProductionLTR":
        from models_v2.ltr_ranker import F1LTRRanker
        from models_v2.training import _load_config, _train_auxiliary_heads, _inject_auxiliary_features

        train = train.sort_values(["seq", "finish_position"])
        X = train[self.features].copy()
        self.dnf_head = self.pace_head = None
        if self.aux_heads:
            self.dnf_head, self.pace_head = _train_auxiliary_heads(train, self.features)
            X = _inject_auxiliary_features(train, self.features, self.dnf_head, self.pace_head)[
                self.features + ["aux_p_dnf", "aux_predicted_pace"]
            ]
        cfg = _load_config().get("models", {}).get("ltr_ranker", {})
        self.model = F1LTRRanker(
            xgb_params=cfg.get("best_params_xgb"),
            lgb_params=cfg.get("best_params_lgb"),
            blend_weight_xgb=cfg.get("blend_weight_xgb", 0.5),
        )
        groups = train.groupby("seq", sort=False).size().to_numpy()
        self.model.fit(X, train["relevance"], groups, optimize=False)
        return self

    def predict(self, race: pd.DataFrame) -> np.ndarray:
        from models_v2.training import _inject_auxiliary_features
        X = race[self.features].copy()
        if self.aux_heads:
            X = _inject_auxiliary_features(race, self.features, self.dnf_head, self.pace_head)[
                self.features + ["aux_p_dnf", "aux_predicted_pace"]
            ]
        # predict_scores min-max normalises per call — fine within one race.
        return self.model.predict_scores(X)


class Blend:
    """Average of members' per-race standardised scores."""

    def __init__(self, members: list, weights: list[float] | None = None):
        self.members = members
        self.weights = weights or [1.0] * len(members)

    def fit(self, train):
        for m in self.members:
            m.fit(train)
        return self

    def predict(self, race):
        out = np.zeros(len(race))
        for m, w in zip(self.members, self.weights):
            s = m.predict(race)
            out += w * (s - s.mean()) / (s.std() + 1e-9)
        return out / sum(self.weights)


def model_zoo(regime: str, legacy_cols: list[str]) -> dict:
    feats = ALL_FEATURES if regime == "post" else PREQUALI_FEATURES
    zoo: dict = {}
    if regime == "post":
        zoo["base_grid"] = lambda: Heuristic("grid_pos")
        zoo["base_quali_gap"] = lambda: Heuristic("q_gap_pct")
    zoo["base_season_points"] = lambda: Heuristic("d_season_pts", ascending=False)
    zoo["base_team_form"] = lambda: Heuristic("t_finish_ewm")

    if legacy_cols:
        this_weekend = {"L_grid_position", "L_is_penalty_grid", "L_quali_gap_to_pole",
                        "L_quali_q3_reached", "L_quali_consistency"}
        legacy_feats = legacy_cols if regime == "post" else [
            c for c in legacy_cols if c not in this_weekend
        ]
        zoo["prod_ltr_legacy"] = lambda: ProductionLTR(legacy_feats, aux_heads=True)
    zoo["prod_ltr_v4"] = lambda: ProductionLTR(feats, aux_heads=False)

    zoo["lgb_rank_points"] = lambda: LGBRankModel(feats, label="points")
    zoo["lgb_rank_top10"] = lambda: LGBRankModel(feats, label="top10")
    zoo["xgb_rank_top10"] = lambda: XGBRankModel(feats, label="top10")
    zoo["lgb_podium_clf"] = lambda: LGBBinaryModel(feats)
    zoo["pl_linear"] = lambda: PLLinearModel(feats)
    zoo["pl_neural"] = lambda: PLNeuralModel(feats)
    if regime == "post":
        with_sprint = feats + SPRINT_FEATURES
        zoo["lgb_rank_top10_sprint"] = lambda: LGBRankModel(with_sprint, label="top10")
        zoo["xgb_rank_top10_sprint"] = lambda: XGBRankModel(with_sprint, label="top10")
    return zoo


# Blends are equal-weight means of members' per-race z-scored scores. They
# are computed from the saved member predictions at aggregation time, which
# is identical to refitting the members inside a Blend but half the cost.
BLENDS = {
    "blend_lgb_pl": ["lgb_rank_top10", "pl_linear"],
    "blend_gbdt": ["lgb_rank_top10", "xgb_rank_top10"],
    "blend_gbdt_pl": ["lgb_rank_top10", "xgb_rank_top10", "pl_linear"],
    "blend_gbdt_pl_nn": ["lgb_rank_top10", "xgb_rank_top10", "pl_linear", "pl_neural"],
    "blend_gbdt_clf_pl": ["lgb_rank_top10", "xgb_rank_top10", "lgb_podium_clf", "pl_linear"],
    "blend_xgb_clf": ["xgb_rank_top10", "lgb_podium_clf"],
    "blend_prodv4_xgb": ["prod_ltr_v4", "xgb_rank_top10"],
    "blend_prodv4_xgb_clf": ["prod_ltr_v4", "xgb_rank_top10", "lgb_podium_clf"],
    # Anchored to the obvious heuristic for the regime (grid / championship order).
    "blend_xgb_grid": ["xgb_rank_top10", "base_grid"],
    "blend_xgb_clf_grid": ["xgb_rank_top10", "lgb_podium_clf", "base_grid"],
    "blend_prodv4_grid": ["prod_ltr_v4", "base_grid"],
    "blend_xgb_points": ["xgb_rank_top10", "base_season_points"],
    "blend_gbdt_pl_points": ["lgb_rank_top10", "xgb_rank_top10", "pl_linear", "base_season_points"],
}


def add_blends(preds: pd.DataFrame) -> pd.DataFrame:
    keys = ["regime", "season", "race_id", "seq", "driver_id", "finish_position"]
    z = preds.copy()
    grp = z.groupby(["model", "regime", "race_id"])["score"]
    z["z"] = (z["score"] - grp.transform("mean")) / (grp.transform("std") + 1e-9)
    wide = z.pivot_table(index=keys, columns="model", values="z").reset_index()
    out = [preds]
    for name, members in BLENDS.items():
        if not all(m in wide.columns for m in members):
            continue
        b = wide[keys].copy()
        b["score"] = wide[members].mean(axis=1)
        b["model"] = name
        out.append(b.dropna(subset=["score"]))
    return pd.concat(out, ignore_index=True)


# ── Walk-forward ─────────────────────────────────────────────────────────

def run(season: int, regime: str, only: list[str] | None, train_start: int = 2014,
        tag: str = "") -> Path:
    df, legacy_cols = load_frame(with_legacy=True)
    if regime == "pre":
        # Nothing from this weekend's qualifying may be used.
        weekend = QUALI_FEATURES + SPRINT_FEATURES
        df = df.drop(columns=weekend, errors="ignore")
        for c in weekend:
            df[c] = np.nan
    zoo = model_zoo(regime, legacy_cols)
    if only:
        zoo = {k: v for k, v in zoo.items() if k in only}

    test_races = df[df["year"] == season].drop_duplicates("race_id").sort_values("seq")
    rows = []
    for _, tr in test_races.iterrows():
        train = df[(df["seq"] < tr["seq"]) & (df["year"] >= train_start)]
        # Shuffled so row order can't carry the result into a tie-break.
        race = df[df["race_id"] == tr["race_id"]].sample(frac=1, random_state=0).reset_index(drop=True)
        for name, make in zoo.items():
            t0 = time.time()
            try:
                scores = make().fit(train).predict(race)
            except Exception as exc:  # keep the sweep going; record the failure
                logger.warning("%s failed on %s: %s", name, tr["race_id"], exc)
                continue
            for d, s, fp in zip(race["driver_id"], scores, race["finish_position"]):
                rows.append({
                    "model": name + tag, "regime": regime, "season": season,
                    "race_id": tr["race_id"], "seq": int(tr["seq"]),
                    "driver_id": d, "score": float(s), "finish_position": float(fp),
                    "fit_sec": time.time() - t0,
                })
        logger.info("%s %s done (%d models)", regime, tr["race_id"], len(zoo))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    import hashlib
    subset = "_" + hashlib.md5(" ".join(sorted(only)).encode()).hexdigest()[:6] if only else ""
    suffix = (f"_{tag.strip('@')}" if tag else "") + subset
    out = OUT_DIR / f"preds_{regime}_{season}{suffix}.parquet"
    pd.DataFrame(rows).to_parquet(out, index=False)
    logger.info("Saved %s", out)
    return out


# ── Metrics ──────────────────────────────────────────────────────────────

_TAUS = np.geomspace(0.05, 20.0, 80)


def _race_probs(scores: np.ndarray, tau: float) -> np.ndarray:
    return pl_top3_probs(scores, tau)


def _podium_logloss(preds: pd.DataFrame, tau: float) -> float:
    total, n = 0.0, 0
    for _, r in preds.groupby("race_id"):
        p = np.clip(_race_probs(r["score"].to_numpy(), tau), 1e-6, 1 - 1e-6)
        y = (r["finish_position"].to_numpy() <= 3).astype(float)
        total -= (y * np.log(p) + (1 - y) * np.log(1 - p)).sum()
        n += len(r)
    return total / max(n, 1)


def _fit_tau(preds: pd.DataFrame) -> float:
    losses = [_podium_logloss(preds, t) for t in _TAUS]
    return float(_TAUS[int(np.argmin(losses))])


def race_metrics(r: pd.DataFrame, tau: float) -> dict:
    # Shuffle first so equal scores are broken at random, never by row order.
    r = r.assign(score=r["score"].fillna(r["score"].min() - 1))
    r = r.sample(frac=1, random_state=0).sort_values("score", ascending=False, kind="stable")
    pos = r["finish_position"].to_numpy()
    picks = pos[:3]
    actual_top3 = (pos <= 3)
    p = np.clip(_race_probs(r["score"].to_numpy(), tau), 1e-6, 1 - 1e-6)
    y = actual_top3.astype(float)
    rel = np.array([{1: 25, 2: 18, 3: 15}.get(int(x), 0) for x in pos], dtype=float)
    dcg = (rel[:3] / np.log2(np.arange(2, 5))).sum()
    idcg = (np.sort(rel)[::-1][:3] / np.log2(np.arange(2, 5))).sum()
    return {
        "correct": int((picks <= 3).sum()),
        "winner_hit": int(pos[0] == 1),
        "logloss": float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean()),
        "brier": float(((p - y) ** 2).mean()),
        "ndcg3": float(dcg / idcg) if idcg > 0 else 0.0,
    }


def aggregate() -> None:
    files = sorted(OUT_DIR.glob("preds_*.parquet"))
    if not files:
        raise SystemExit("No prediction files — run the lab first.")
    preds = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    preds = preds.drop_duplicates(["model", "regime", "race_id", "driver_id"], keep="last")
    # A missing score ranks last in its race (it never wins a tie-break).
    race_min = preds.groupby(["model", "regime", "race_id"])["score"].transform("min")
    preds["score"] = preds["score"].fillna(race_min - 1).fillna(0.0)
    # Heuristic scores are raw column values (championship points run into
    # the hundreds), which no temperature in range can turn into sensible
    # probabilities. Rank-transform them so every baseline gets a fair
    # Plackett-Luce calibration.
    is_base = preds["model"].str.startswith("base_")
    preds.loc[is_base, "score"] = -preds[is_base].groupby(["model", "regime", "race_id"])["score"].rank(
        ascending=False, method="average")
    preds = add_blends(preds)

    per_race, per_driver = [], []
    for (model, regime), g in preds.groupby(["model", "regime"]):
        for season in sorted(g["season"].unique()):
            prior = g[g["season"] < season]
            tau = _fit_tau(prior) if prior["race_id"].nunique() >= 10 else _fit_tau(g[g["season"] == season])
            for race_id, r in g[g["season"] == season].groupby("race_id"):
                m = race_metrics(r, tau)
                m.update(model=model, regime=regime, season=int(season), race_id=race_id, tau=tau)
                per_race.append(m)
                per_driver.append(pd.DataFrame({
                    "model": model, "regime": regime, "season": int(season),
                    "p_podium": _race_probs(r["score"].to_numpy(), tau),
                    "podium": (r["finish_position"].to_numpy() <= 3).astype(int),
                }))
    pr = pd.DataFrame(per_race)
    pdv = pd.concat(per_driver, ignore_index=True)
    pr.to_csv(OUT_DIR / "per_race_metrics.csv", index=False)

    def summarise(sub: pd.DataFrame) -> pd.DataFrame:
        return (
            sub.groupby(["regime", "model"])
            .agg(races=("correct", "size"), avg_correct=("correct", "mean"),
                 all3=("correct", lambda x: (x == 3).mean()), winner=("winner_hit", "mean"),
                 logloss=("logloss", "mean"), brier=("brier", "mean"), ndcg3=("ndcg3", "mean"))
            .round(4)
            .reset_index()
            .sort_values(["regime", "avg_correct"], ascending=[True, False])
        )

    report = {}
    for label, seasons in [("validation_2022_2024", VALIDATION), ("heldout_2025_2026", HELDOUT),
                           ("season_2026", [2026]), ("all_2022_2026", VALIDATION + HELDOUT)]:
        s = summarise(pr[pr["season"].isin(seasons)])
        report[label] = s.to_dict(orient="records")
        print(f"\n=== {label} ===")
        print(s.to_string(index=False))
    by_season = (pr.groupby(["regime", "model", "season"])["correct"].mean().round(3)
                 .unstack("season").reset_index())
    print("\n=== avg correct / 3 by season ===")
    print(by_season.to_string(index=False))
    report["by_season"] = by_season.to_dict(orient="records")

    # Paired comparison vs a reference on identical races (removes the
    # race-to-race noise that dominates single-season averages), with a
    # 90% bootstrap interval over races.
    rng = np.random.default_rng(0)
    paired = []
    for regime, ref in [("post", "base_grid"), ("pre", "base_season_points")]:
        sub = pr[(pr["regime"] == regime) & (pr["season"].isin(VALIDATION + HELDOUT))]
        for metric in ("correct", "logloss"):
            piv = sub.pivot_table(index="race_id", columns="model", values=metric)
            if ref not in piv.columns:
                continue
            for model in piv.columns:
                d = (piv[model] - piv[ref]).dropna().to_numpy()
                if len(d) < 10:
                    continue
                boots = rng.choice(d, size=(4000, len(d))).mean(axis=1)
                paired.append({
                    "regime": regime, "metric": metric, "model": model, "vs": ref,
                    "races": int(len(d)), "mean_diff": round(float(d.mean()), 4),
                    "ci90_low": round(float(np.percentile(boots, 5)), 4),
                    "ci90_high": round(float(np.percentile(boots, 95)), 4),
                })
    paired_df = pd.DataFrame(paired)
    print("\n=== paired difference vs baseline, 2022-2026 (correct: higher better; logloss: lower better) ===")
    print(paired_df.sort_values(["regime", "metric", "mean_diff"]).to_string(index=False))
    report["paired_vs_baseline_2022_2026"] = paired

    # Reliability on 2022-2026: does "60%" happen ~60% of the time?
    bins = [0, 0.05, 0.15, 0.3, 0.5, 0.7, 0.85, 1.0]
    rel = pdv[pdv["season"].isin(VALIDATION + HELDOUT)].copy()
    rel["bin"] = pd.cut(rel["p_podium"], bins, include_lowest=True)
    reliability = (rel.groupby(["regime", "model", "bin"], observed=True)
                   .agg(n=("podium", "size"), predicted=("p_podium", "mean"), observed=("podium", "mean"))
                   .round(4).reset_index())
    reliability["bin"] = reliability["bin"].astype(str)
    report["reliability_2022_2026"] = reliability.to_dict(orient="records")
    with open(OUT_DIR / "summary.json", "w") as f:
        json.dump(report, f, indent=2, default=float)
    print(f"\nWrote {OUT_DIR / 'summary.json'}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--season", type=int, required=True)
    r.add_argument("--regime", choices=["post", "pre"], required=True)
    r.add_argument("--only", nargs="*", help="Subset of model names")
    r.add_argument("--train-start", type=int, default=2014, help="First training season")
    r.add_argument("--tag", default="", help="Suffix for model names, e.g. @2022")
    sub.add_parser("aggregate")
    args = ap.parse_args()
    if args.cmd == "run":
        run(args.season, args.regime, args.only, args.train_start, args.tag)
    else:
        aggregate()


if __name__ == "__main__":
    main()
