"""Production podium predictor (FormulAI v4).

Wraps the v4 feature engine and the models in `models_v2.podium_model` into
one artifact that serves both prediction regimes:

* post — qualifying is known: grid/quali features available.
* pre  — before qualifying: the model never sees this weekend's grid.

Each regime is a blend of members (equal-weight mean of per-race z-scored
scores; members chosen by the walk-forward lab, see `scripts/model_lab.py`
and `config/training_config.yaml: podium_model`). Scores become probabilities
through an exact Plackett-Luce layer whose temperature is fitted on
out-of-sample races, so P(podium) is calibrated and sums to 3 per race.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from config.settings import settings
from features.fast_features import ALL_FEATURES, PREQUALI_FEATURES, build_training_frame
from models_v2.podium_model import (
    LGBBinaryModel,
    LGBRankModel,
    PLLinearModel,
    PLNeuralModel,
    RankHeuristic,
    XGBRankModel,
    fit_temperature,
    pl_position_probs,
)

logger = logging.getLogger(__name__)

ARTIFACT_NAME = "podium_predictor.joblib"

MEMBER_FACTORY = {
    "lgb_rank_top10": lambda f: LGBRankModel(f, label="top10"),
    "lgb_rank_points": lambda f: LGBRankModel(f, label="points"),
    "xgb_rank_top10": lambda f: XGBRankModel(f, label="top10"),
    "lgb_podium_clf": lambda f: LGBBinaryModel(f),
    "pl_linear": lambda f: PLLinearModel(f),
    "pl_neural": lambda f: PLNeuralModel(f),
    "base_grid": lambda f: RankHeuristic("grid_pos", ascending=True),
    "base_season_points": lambda f: RankHeuristic("d_season_pts", ascending=False),
}

# Chosen by scripts/model_lab.py on 2022-2024 (lowest podium log-loss with
# podium hits no worse than the regime's baseline), confirmed on 2025-2026.
DEFAULT_MEMBERS = {
    "post": ["xgb_rank_top10", "lgb_podium_clf", "base_grid"],
    "pre": ["xgb_rank_top10", "base_season_points"],
}

REGIME_FEATURES = {"post": ALL_FEATURES, "pre": PREQUALI_FEATURES}


def _blend(members: list, race: pd.DataFrame) -> np.ndarray:
    out = np.zeros(len(race))
    for m in members:
        s = np.asarray(m.predict(race), dtype=float)
        out += (s - s.mean()) / (s.std() + 1e-9)
    return out / len(members)


@dataclass
class PodiumPredictor:
    members: dict[str, list[str]] = field(default_factory=lambda: dict(DEFAULT_MEMBERS))
    train_start: int = 2014
    calibration_races: int = 44

    fitted: dict[str, list] = field(default_factory=dict, repr=False)
    tau: dict[str, float] = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)

    # ── training ────────────────────────────────────────────────────────

    def _fit_members(self, regime: str, train: pd.DataFrame) -> list:
        feats = REGIME_FEATURES[regime]
        return [MEMBER_FACTORY[name](feats).fit(train) for name in self.members[regime]]

    def _calibrate(self, regime: str, frame: pd.DataFrame) -> float:
        """Fit tau on races the members did not train on.

        Members are refit at a few cut-offs inside the last
        `calibration_races` races and score the block after each cut-off —
        a coarse walk-forward that keeps the scores out-of-sample.
        """
        seqs = np.sort(frame["seq"].unique())
        calib = seqs[-self.calibration_races:]
        blocks = np.array_split(calib, 4)
        score_groups, podium_groups = [], []
        for block in blocks:
            members = self._fit_members(regime, frame[frame["seq"] < block[0]])
            for s in block:
                race = frame[frame["seq"] == s].reset_index(drop=True)
                score_groups.append(_blend(members, race))
                podium_groups.append((race["finish_position"].to_numpy() <= 3).astype(float))
        return fit_temperature(score_groups, podium_groups)

    def fit(self, frame: pd.DataFrame | None = None, calibrate: bool = True) -> "PodiumPredictor":
        if frame is None:
            frame = build_training_frame(self.train_start)
        frame = frame[frame["year"] >= self.train_start]
        for regime in ("post", "pre"):
            if calibrate:
                self.tau[regime] = self._calibrate(regime, frame)
            self.tau.setdefault(regime, 1.0)
            self.fitted[regime] = self._fit_members(regime, frame)
            logger.info("Fitted %s regime (%s), tau=%.3f",
                        regime, ", ".join(self.members[regime]), self.tau[regime])
        last = frame.sort_values("seq").iloc[-1]
        self.metadata = {
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "train_rows": int(len(frame)),
            "train_races": int(frame["race_id"].nunique()),
            "trained_through": str(last["race_id"]),
            "members": self.members,
            "tau": self.tau,
            "model_version": "4.0.0",
        }
        return self

    # ── inference ───────────────────────────────────────────────────────

    @staticmethod
    def detect_regime(race: pd.DataFrame) -> str:
        """`post` once most of the field has a grid slot or quali time."""
        known = race.get("grid_pos", pd.Series(np.nan, index=race.index)).notna()
        return "post" if known.mean() >= 0.5 else "pre"

    def predict(self, race: pd.DataFrame, regime: str | None = None) -> pd.DataFrame:
        """Per-driver probabilities for one race, best first.

        `race` is the output of `features.fast_features.build_features` for a
        single race_id.
        """
        regime = regime or self.detect_regime(race)
        race = race.reset_index(drop=True)
        scores = _blend(self.fitted[regime], race)
        p1, p2, p3 = pl_position_probs(scores, self.tau[regime])
        out = pd.DataFrame({
            "driver_id": race["driver_id"],
            "constructor_id": race.get("constructor_id"),
            "score": scores,
            "p_win": p1, "p_p2": p2, "p_p3": p3,
            "p_podium": np.clip(p1 + p2 + p3, 0, 1),
        })
        out = out.sort_values("score", ascending=False, kind="stable").reset_index(drop=True)
        out["predicted_rank"] = np.arange(1, len(out) + 1)
        out.attrs["regime"] = regime
        return out

    # ── persistence ─────────────────────────────────────────────────────

    def save(self, path: Path | None = None) -> Path:
        path = path or settings.abs_model_dir / ARTIFACT_NAME
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)
        logger.info("Saved PodiumPredictor to %s", path)
        return path

    @classmethod
    def load(cls, path: Path | None = None) -> "PodiumPredictor":
        return joblib.load(path or settings.abs_model_dir / ARTIFACT_NAME)


def members_from_config(config: dict) -> dict[str, list[str]]:
    cfg = (config or {}).get("podium_model", {}).get("members", {})
    return {r: list(cfg.get(r, DEFAULT_MEMBERS[r])) for r in ("post", "pre")}


if __name__ == "__main__":
    import argparse

    from models_v2.training import _load_config

    parser = argparse.ArgumentParser(description="Train and save the v4 PodiumPredictor on all completed races")
    parser.add_argument("--train-start", type=int, default=None, help="First training season (default: config)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")

    config = _load_config()
    start = args.train_start or config.get("podium_model", {}).get("train_start_year", 2014)
    model = PodiumPredictor(members=members_from_config(config), train_start=start).fit()
    path = model.save()
    print(f"Saved {path}  (trained through {model.metadata['trained_through']}, tau={model.tau})")
