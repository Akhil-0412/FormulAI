"""Podium models and the Plackett-Luce probability layer."""

import numpy as np
import pandas as pd
import pytest

from models_v2.podium_model import (
    LGBRankModel,
    PLLinearModel,
    fit_temperature,
    pl_position_probs,
    pl_top3_probs,
)


def test_pl_position_probabilities_are_distributions_and_match_simulation():
    rng = np.random.default_rng(0)
    scores = rng.normal(size=20)
    p1, p2, p3 = pl_position_probs(scores, tau=0.7)
    for p in (p1, p2, p3):
        assert p.sum() == pytest.approx(1.0, abs=1e-9)

    sims = 100_000
    order = np.argsort(-(scores / 0.7 + rng.gumbel(size=(sims, 20))), axis=1)
    top3 = np.bincount(order[:, :3].ravel(), minlength=20) / sims
    assert np.abs(top3 - (p1 + p2 + p3)).max() < 0.01


def test_podium_probability_is_monotone_in_score():
    p = pl_top3_probs(np.linspace(3, -3, 15), tau=1.0)
    assert np.all(np.diff(p) < 0)
    assert p.sum() == pytest.approx(3.0)


def test_temperature_fit_prefers_sharper_probs_when_scores_are_right():
    rng = np.random.default_rng(1)
    groups, ys = [], []
    for _ in range(30):
        s = rng.normal(size=12)
        y = np.zeros(12)
        y[np.argsort(-s)[:3]] = 1  # scores rank the podium perfectly
        groups.append(s)
        ys.append(y)
    assert fit_temperature(groups, ys) < 0.5


def _synthetic_frame(n_races=60, n_drivers=10, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for r in range(n_races):
        skill = rng.normal(size=n_drivers)
        order = np.argsort(-(skill + rng.normal(scale=0.3, size=n_drivers)))
        pos = np.empty(n_drivers)
        pos[order] = np.arange(1, n_drivers + 1)
        for d in range(n_drivers):
            rows.append(dict(seq=r, race_id=str(r), driver_id=f"d{d}", skill=skill[d],
                             noise=rng.normal(), finish_position=pos[d],
                             relevance=max(0, 11 - pos[d])))
    return pd.DataFrame(rows)


@pytest.mark.parametrize("model_cls", [PLLinearModel, LGBRankModel])
def test_models_learn_an_obvious_signal(model_cls):
    df = _synthetic_frame()
    train, test = df[df["seq"] < 50], df[df["seq"] >= 50]
    model = model_cls(["skill", "noise"]).fit(train)
    hits = []
    for _, race in test.groupby("seq"):
        scores = model.predict(race)
        picks = race.assign(s=scores).nlargest(3, "s")
        hits.append((picks["finish_position"] <= 3).sum())
    assert np.mean(hits) >= 2.5
