"""Podium models over the v4 feature set + Plackett-Luce probability layer.

All models expose the same two-call interface used by the walk-forward lab
and by production:

    model.fit(train_df)        # rows of completed races, any order
    model.predict(race_df)     # one race -> 1-D array of scores (higher = better)

Scores are turned into probabilities with a Plackett-Luce (PL) model: driver
i wins with probability w_i / sum(w), then 2nd is drawn from the rest, and so
on, with w = exp(score / tau). P(podium) is the exact probability of landing
in the first three draws — it sums to 3 across the field, unlike the old
softmax output (which was a P(win) and summed to 1). `tau` is fitted on
out-of-sample predictions by podium log-loss.

Models
------
* LGBRankModel / XGBRankModel — LambdaMART rankers (the production family).
  `label="top10"` uses linear-gain relevance 10..1 for P1..P10. The old
  F1-points labels (25, 18, 15, ...) with LightGBM/XGBoost's default
  *exponential* gain (2^rel - 1) make a win worth ~128x a P2, so the ranker
  effectively only learns who wins.
* LGBBinaryModel — pointwise P(podium) classifier.
* PLLinearModel — rank-ordered logit: linear scorer trained on the PL
  likelihood of the top-10 finishing order (the statistical baseline from
  the F1 literature).
* PLNeuralModel — the same likelihood with an MLP scorer (ListMLE), i.e. the
  deep-learning variant.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ── Probability layer ─────────────────────────────────────────────────────

def pl_position_probs(scores: np.ndarray, tau: float = 1.0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Exact Plackett-Luce P(P1), P(P2), P(P3) for every driver.

    Enumerates ordered (1st, 2nd, 3rd) triples — n^3 terms, ~10k for a
    22-car field — so there is no Monte Carlo noise.
    """
    s = np.asarray(scores, dtype=float) / max(tau, 1e-6)
    s = s - s.max()
    w = np.exp(s)
    n = len(w)
    p1 = w / w.sum()

    # Remaining-field masses are summed directly rather than computed as
    # total - w_a - w_b: at small tau that subtraction cancels to ~0 while
    # the remaining weights don't, which blew conditional probabilities up.
    not_a = ~np.eye(n, dtype=bool)
    w_b = np.where(not_a, w[None, :], 0.0)                         # (a, b)
    pair = p1[:, None] * w_b / np.clip(w_b.sum(axis=1, keepdims=True), 1e-300, None)
    p2 = pair.sum(axis=0)                                          # P(a 1st, b 2nd)

    w_c = np.broadcast_to(w, (n, n, n)).copy()                     # (a, b, c)
    idx = np.arange(n)
    w_c[idx, :, idx] = 0.0  # c == a
    w_c[:, idx, idx] = 0.0  # c == b
    triple = pair[:, :, None] * w_c / np.clip(w_c.sum(axis=2, keepdims=True), 1e-300, None)
    p3 = triple.sum(axis=(0, 1))
    return p1, p2, p3


def pl_top3_probs(scores: np.ndarray, tau: float = 1.0) -> np.ndarray:
    p1, p2, p3 = pl_position_probs(scores, tau)
    return np.clip(p1 + p2 + p3, 0.0, 1.0)


def fit_temperature(score_groups: list[np.ndarray], podium_groups: list[np.ndarray]) -> float:
    """Temperature minimising podium log-loss over out-of-sample races."""
    taus = np.geomspace(0.05, 20.0, 80)

    def loss(tau: float) -> float:
        total = 0.0
        for s, y in zip(score_groups, podium_groups):
            p = np.clip(pl_top3_probs(s, tau), 1e-6, 1 - 1e-6)
            total -= (y * np.log(p) + (1 - y) * np.log(1 - p)).sum()
        return total

    return float(taus[int(np.argmin([loss(t) for t in taus]))])


# ── Shared helpers ────────────────────────────────────────────────────────

def _sorted_groups(train: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray]:
    """Rows grouped by race (chronological), finishing order within each."""
    t = train.sort_values(["seq", "finish_position"], kind="stable").reset_index(drop=True)
    groups = t.groupby("seq", sort=False).size().to_numpy()
    return t, groups


def _labels(t: pd.DataFrame, scheme: str) -> np.ndarray:
    pos = t["finish_position"].to_numpy(dtype=float)
    if scheme == "points":
        return t["relevance"].to_numpy(dtype=float)
    if scheme == "top10":
        return np.clip(11.0 - pos, 0.0, 10.0)
    if scheme == "podium":
        return np.clip(4.0 - pos, 0.0, 3.0)
    raise ValueError(scheme)


class _Base:
    def __init__(self, features: list[str]):
        self.features = list(features)

    def _X(self, df: pd.DataFrame) -> pd.DataFrame:
        X = df.reindex(columns=self.features).astype(float)
        return X


# ── Heuristic anchor ──────────────────────────────────────────────────────

class RankHeuristic(_Base):
    """Order the field by one column (e.g. grid slot, championship points).

    Used as a blend member that anchors the learned models to the obvious
    signal for the regime; the walk-forward lab found that anchoring improves
    out-of-sample log-loss. Scores are -rank, so the scale matches the other
    members once z-scored. Ties fall back to the car's form.
    """

    def __init__(self, column: str, ascending: bool = True):
        super().__init__([column, "t_finish_ewm"])
        self.column, self.ascending = column, ascending

    def fit(self, train: pd.DataFrame) -> "RankHeuristic":
        return self

    def predict(self, race: pd.DataFrame) -> np.ndarray:
        v = race[self.column].astype(float)
        if v.isna().all():
            v = pd.Series(0.0, index=race.index)
        v = v if self.ascending else -v
        v = v.fillna(v.max() + 1)
        tie_break = race["t_finish_ewm"].astype(float).fillna(30.0) * 1e-3
        return -(v + tie_break).rank(method="average").to_numpy()


# ── Gradient-boosted models ───────────────────────────────────────────────

class LGBRankModel(_Base):
    def __init__(self, features: list[str], label: str = "top10", seed: int = 42, **params):
        super().__init__(features)
        self.label = label
        self.params = dict(
            objective="lambdarank", n_estimators=300, learning_rate=0.03,
            num_leaves=15, min_child_samples=30, subsample=0.8, subsample_freq=1,
            colsample_bytree=0.8, reg_lambda=1.0, lambdarank_truncation_level=10,
            random_state=seed, n_jobs=2, verbose=-1,
        )
        if label != "points":
            self.params["label_gain"] = list(range(32))  # linear gain
        self.params.update(params)

    def fit(self, train: pd.DataFrame) -> "LGBRankModel":
        import lightgbm as lgb
        t, groups = _sorted_groups(train)
        self.model = lgb.LGBMRanker(**self.params)
        self.model.fit(self._X(t), _labels(t, self.label), group=groups)
        return self

    def predict(self, race: pd.DataFrame) -> np.ndarray:
        return self.model.predict(self._X(race))


class XGBRankModel(_Base):
    def __init__(self, features: list[str], label: str = "top10", seed: int = 42, **params):
        super().__init__(features)
        self.label = label
        self.params = dict(
            objective="rank:ndcg", ndcg_exp_gain=(label == "points"),
            lambdarank_pair_method="topk", lambdarank_num_pair_per_sample=10,
            n_estimators=300, learning_rate=0.03, max_depth=4, min_child_weight=5,
            subsample=0.8, colsample_bytree=0.8, reg_lambda=1.0, tree_method="hist",
            random_state=seed, n_jobs=2,
        )
        self.params.update(params)

    def fit(self, train: pd.DataFrame) -> "XGBRankModel":
        import xgboost as xgb
        t, groups = _sorted_groups(train)
        qid = np.repeat(np.arange(len(groups)), groups)
        self.model = xgb.XGBRanker(**self.params)
        self.model.fit(self._X(t), _labels(t, self.label), qid=qid)
        return self

    def predict(self, race: pd.DataFrame) -> np.ndarray:
        return self.model.predict(self._X(race))


class LGBBinaryModel(_Base):
    def __init__(self, features: list[str], seed: int = 42, **params):
        super().__init__(features)
        self.params = dict(
            n_estimators=300, learning_rate=0.03, num_leaves=15, min_child_samples=30,
            subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0,
            random_state=seed, n_jobs=2, verbose=-1,
        )
        self.params.update(params)

    def fit(self, train: pd.DataFrame) -> "LGBBinaryModel":
        import lightgbm as lgb
        self.model = lgb.LGBMClassifier(**self.params)
        self.model.fit(self._X(train), (train["finish_position"] <= 3).astype(int))
        return self

    def predict(self, race: pd.DataFrame) -> np.ndarray:
        p = np.clip(self.model.predict_proba(self._X(race))[:, 1], 1e-6, 1 - 1e-6)
        return np.log(p / (1 - p))


# ── Plackett-Luce models (torch) ──────────────────────────────────────────

class _Standardiser:
    def fit(self, X: pd.DataFrame) -> "_Standardiser":
        self.median = X.median()
        filled = X.fillna(self.median).fillna(0.0)
        self.mean = filled.mean()
        self.std = filled.std().replace(0, 1.0).fillna(1.0)
        return self

    def transform(self, X: pd.DataFrame) -> np.ndarray:
        Z = (X.fillna(self.median).fillna(0.0) - self.mean) / self.std
        return np.clip(Z.to_numpy(dtype=np.float32), -5, 5)


def _padded(Z: np.ndarray, groups: np.ndarray):
    import torch
    n_max = int(groups.max())
    G, F = len(groups), Z.shape[1]
    Xp = np.zeros((G, n_max, F), dtype=np.float32)
    mask = np.zeros((G, n_max), dtype=bool)
    start = 0
    for g, size in enumerate(groups):
        Xp[g, :size] = Z[start:start + size]
        mask[g, :size] = True
        start += size
    return torch.from_numpy(Xp), torch.from_numpy(mask)


def _pl_nll(scores, mask, top_k: int):
    """Negative PL log-likelihood of each race's top-k finishing order.

    Rows are already in finishing order, so position j's "remaining field" is
    rows j..end — a reversed cumulative logsumexp.
    """
    import torch
    s = scores.masked_fill(~mask, float("-inf"))
    tail_lse = torch.logcumsumexp(s.flip(-1), dim=-1).flip(-1)
    k = min(top_k, s.shape[1])
    terms = (s - tail_lse)[:, :k]
    valid = mask[:, :k]
    return -(terms.masked_fill(~valid, 0.0).sum(dim=1)).mean()


class PLLinearModel(_Base):
    """Rank-ordered logit with an L2-penalised linear scorer."""

    def __init__(self, features: list[str], l2: float = 0.02, top_k: int = 10):
        super().__init__(features)
        self.l2, self.top_k = l2, top_k

    def fit(self, train: pd.DataFrame) -> "PLLinearModel":
        import torch
        torch.set_num_threads(2)
        t, groups = _sorted_groups(train)
        self.scaler = _Standardiser().fit(self._X(t))
        X, mask = _padded(self.scaler.transform(self._X(t)), groups)
        beta = torch.zeros(X.shape[-1], requires_grad=True)
        opt = torch.optim.LBFGS([beta], lr=0.5, max_iter=200, line_search_fn="strong_wolfe")

        def closure():
            opt.zero_grad()
            loss = _pl_nll(X @ beta, mask, self.top_k) + self.l2 * (beta ** 2).sum()
            loss.backward()
            return loss

        opt.step(closure)
        self.beta = beta.detach().numpy()
        return self

    def predict(self, race: pd.DataFrame) -> np.ndarray:
        return self.scaler.transform(self._X(race)) @ self.beta

    def coefficients(self) -> pd.Series:
        return pd.Series(self.beta, index=self.features).sort_values(key=np.abs, ascending=False)


class PLNeuralModel(_Base):
    """ListMLE: MLP scorer trained on the same PL likelihood (seed-averaged)."""

    def __init__(self, features: list[str], hidden: tuple[int, ...] = (64, 32), dropout: float = 0.1,
                 weight_decay: float = 1e-3, epochs: int = 200, lr: float = 3e-3,
                 top_k: int = 10, n_seeds: int = 3):
        super().__init__(features)
        self.hidden, self.dropout, self.wd = hidden, dropout, weight_decay
        self.epochs, self.lr, self.top_k, self.n_seeds = epochs, lr, top_k, n_seeds

    def _net(self, n_in: int):
        import torch.nn as nn
        layers, d = [], n_in
        for h in self.hidden:
            layers += [nn.Linear(d, h), nn.ReLU(), nn.Dropout(self.dropout)]
            d = h
        layers.append(nn.Linear(d, 1))
        return nn.Sequential(*layers)

    def fit(self, train: pd.DataFrame) -> "PLNeuralModel":
        import torch
        torch.set_num_threads(2)
        t, groups = _sorted_groups(train)
        self.scaler = _Standardiser().fit(self._X(t))
        X, mask = _padded(self.scaler.transform(self._X(t)), groups)
        self.nets = []
        for seed in range(self.n_seeds):
            torch.manual_seed(seed)
            net = self._net(X.shape[-1])
            opt = torch.optim.AdamW(net.parameters(), lr=self.lr, weight_decay=self.wd)
            net.train()
            for _ in range(self.epochs):
                opt.zero_grad()
                loss = _pl_nll(net(X).squeeze(-1), mask, self.top_k)
                loss.backward()
                opt.step()
            net.eval()
            self.nets.append(net)
        return self

    def predict(self, race: pd.DataFrame) -> np.ndarray:
        import torch
        Z = torch.from_numpy(self.scaler.transform(self._X(race)))
        with torch.no_grad():
            return np.mean([net(Z).squeeze(-1).numpy() for net in self.nets], axis=0)
