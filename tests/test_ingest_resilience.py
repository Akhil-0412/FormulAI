"""Rate-limit handling: incomplete ingests must be detected, never published."""

import json

import pandas as pd
import pytest
from tenacity import RetryError

import data.db as db
from data.ingest import IncompleteSeasonError, ingest_season
from data.jolpica_client import JolpicaClient, RateLimitExhausted


def test_circuit_breaker_fails_fast_after_repeated_exhausted_retries(monkeypatch):
    client = JolpicaClient()
    calls = []

    def always_429(path, params=None):
        calls.append(path)
        raise RetryError(last_attempt=None)

    monkeypatch.setattr(client, "_get_with_retry", always_429)
    for _ in range(3):
        with pytest.raises(RetryError):
            client._get("/x")
    with pytest.raises(RateLimitExhausted):
        client._get("/y")
    assert calls == ["/x", "/x", "/x"]  # the 4th call never reached the network


class _HalfBrokenClient:
    """Season results succeed; every per-race follow-up call is rate-limited."""

    def get_all_season_results(self, year):
        return [{
            "round": "1", "raceName": "Test GP", "date": "2026-03-01",
            "Circuit": {"circuitId": "monza", "circuitName": "Monza", "Location": {"country": "Italy"}},
            "Results": [{"position": "1", "positionText": "1", "grid": "1", "status": "Finished",
                         "points": "25", "laps": "53",
                         "Driver": {"driverId": "a", "code": "AAA", "givenName": "A", "familyName": "A"},
                         "Constructor": {"constructorId": "t1", "name": "T1"}}],
        }]

    def _fail(self, *args, **kwargs):
        raise RateLimitExhausted("limit")

    get_qualifying = get_driver_standings = get_constructor_standings = _fail
    get_pit_stops = get_sprint_results = _fail


def test_season_with_failed_calls_is_reported_incomplete(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_db_path", lambda: tmp_path / "test.db")
    with pytest.raises(IncompleteSeasonError) as info:
        ingest_season(2026, _HalfBrokenClient())
    assert info.value.failures >= 2
    # What did succeed is kept, so the retry only has to fill the gaps.
    assert len(db.query_df("SELECT * FROM results")) == 1


def test_backtest_refuses_to_publish_from_partial_data(tmp_path, monkeypatch):
    import scripts.rolling_backtest as rb

    monkeypatch.setattr(rb, "OUTPUT_DIRS", [tmp_path])
    (tmp_path / "rolling_backtest_2026.json").write_text(
        json.dumps([{"round": r, "correct": 2} for r in range(1, 16)])
    )
    frame = pd.DataFrame({"year": [2014, 2015, 2016, 2017, 2018, 2019]})

    with pytest.raises(SystemExit):  # 2020-2025 missing
        rb._check_inputs(frame, 2014, 2026, [{"round": 1, "correct": 2}])

    full = pd.DataFrame({"year": list(range(2014, 2027))})
    with pytest.raises(SystemExit):  # 3 scored races vs 15 published
        rb._check_inputs(full, 2014, 2026, [{"round": r, "correct": 1} for r in (1, 2, 3)])

    rb._check_inputs(full, 2014, 2026, [{"round": r, "correct": 1} for r in range(1, 17)])
