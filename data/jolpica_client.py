"""Jolpica API client — drop-in Ergast replacement for historical F1 data."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
from tenacity import RetryError, retry, stop_after_attempt, wait_exponential

from config.settings import settings

logger = logging.getLogger(__name__)

# Jolpica rate limit: 4 requests/second. Pagination means a single season now
# issues many more calls than before, so this client paces its own requests
# rather than relying on retry/backoff alone — sustained bursts trip a
# longer server-side cooldown that per-request retries can't out-wait.
_CLIENT_TIMEOUT = 15.0
_MIN_REQUEST_INTERVAL = 0.3  # ~3.3 req/s, under the stated 4/s limit
_BREAKER_THRESHOLD = 3       # consecutive exhausted-retry calls before failing fast


class RateLimitExhausted(RuntimeError):
    """Jolpica keeps refusing requests; stop for this run and resume later."""


@dataclass
class JolpicaClient:
    """REST client for the Jolpica (Ergast-compatible) F1 API."""

    base_url: str = field(default_factory=lambda: settings.jolpica_base_url)
    _client: httpx.Client | None = field(default=None, init=False, repr=False)
    _last_request_time: float = field(default=0.0, init=False, repr=False)
    _consecutive_failures: int = field(default=0, init=False, repr=False)

    def _get_client(self) -> httpx.Client:
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(
                base_url=self.base_url,
                timeout=_CLIENT_TIMEOUT,
                headers={"Accept": "application/json"},
            )
        return self._client

    def close(self) -> None:
        if self._client and not self._client.is_closed:
            self._client.close()

    # ── Core request ────────────────────────────────────────────────────

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < _MIN_REQUEST_INTERVAL:
            time.sleep(_MIN_REQUEST_INTERVAL - elapsed)
        self._last_request_time = time.monotonic()

    @retry(stop=stop_after_attempt(6), wait=wait_exponential(min=1, max=30))
    def _get_with_retry(self, path: str, params: dict[str, Any] | None = None) -> dict:
        self._throttle()
        resp = self._get_client().get(path, params=params)
        resp.raise_for_status()
        data = resp.json()
        return data.get("MRData", data)

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict:
        """Make a GET request and return the MRData dict.

        Circuit breaker: once several calls in a row have exhausted their
        retries, Jolpica's sustained (hourly) limit has been reached and
        further calls would each burn ~1 minute of backoff before failing.
        Fail fast instead; the ingest is resumed on the next run.
        """
        if self._consecutive_failures >= _BREAKER_THRESHOLD:
            raise RateLimitExhausted(f"Jolpica rate limit exhausted; skipped {path}")
        try:
            data = self._get_with_retry(path, params)
        except RetryError:
            self._consecutive_failures += 1
            raise
        self._consecutive_failures = 0
        return data

    def _get_all_races(self, path: str, page_size: int = 100) -> list[dict]:
        """Fetch every page of a season-level Races endpoint and merge them.

        Jolpica silently caps `limit` at 100 server-side regardless of what's
        requested, and reports the real row count via `total`. Season-level
        results/qualifying calls return far more than 100 rows (~20/race), so
        without paging through `offset` only the first ~5 races ever come
        back. Result rows for a single race can also land on either side of a
        page boundary, so races are merged by round number across pages.
        """
        merged: dict[str, dict] = {}
        order: list[str] = []
        offset = 0
        while True:
            data = self._get(path, params={"limit": str(page_size), "offset": str(offset)})
            races = data.get("RaceTable", {}).get("Races", [])
            for race in races:
                round_num = race.get("round")
                if round_num not in merged:
                    merged[round_num] = race
                    order.append(round_num)
                else:
                    for key in ("Results", "QualifyingResults", "SprintResults"):
                        if key in race:
                            merged[round_num].setdefault(key, [])
                            merged[round_num][key].extend(race[key])

            total = int(data.get("total", len(races)) or 0)
            offset += page_size
            if offset >= total or not races:
                break

        return [merged[r] for r in order]

    # ── Race results ────────────────────────────────────────────────────

    def get_race_results(self, year: int, round_number: int | None = None) -> list[dict]:
        """Get race result(s) for a season or specific round.

        Returns a list of race result dicts, each containing RaceTable data.
        """
        if round_number is None:
            return self._get_all_races(f"/{year}/results.json")
        data = self._get(f"/{year}/{round_number}/results.json", params={"limit": "1000"})
        return data.get("RaceTable", {}).get("Races", [])

    def get_all_season_results(self, year: int) -> list[dict]:
        """Get results for every race in a season."""
        return self.get_race_results(year)

    # ── Qualifying ──────────────────────────────────────────────────────

    def get_qualifying(self, year: int, round_number: int | None = None) -> list[dict]:
        """Get qualifying results."""
        if round_number is None:
            return self._get_all_races(f"/{year}/qualifying.json")
        data = self._get(f"/{year}/{round_number}/qualifying.json", params={"limit": "1000"})
        return data.get("RaceTable", {}).get("Races", [])

    # ── Sprints ─────────────────────────────────────────────────────────

    def get_sprint_results(self, year: int, round_number: int | None = None) -> list[dict]:
        """Sprint race results (Races[].SprintResults); empty for non-sprint rounds."""
        if round_number is None:
            return self._get_all_races(f"/{year}/sprint.json")
        data = self._get(f"/{year}/{round_number}/sprint.json", params={"limit": "100"})
        return data.get("RaceTable", {}).get("Races", [])

    # ── Standings ───────────────────────────────────────────────────────

    def get_driver_standings(self, year: int, round_number: int | None = None) -> list[dict]:
        """Get driver championship standings."""
        if round_number:
            path = f"/{year}/{round_number}/driverStandings.json"
        else:
            path = f"/{year}/driverStandings.json"
        data = self._get(path)
        standings_lists = data.get("StandingsTable", {}).get("StandingsLists", [])
        if standings_lists:
            return standings_lists[0].get("DriverStandings", [])
        return []

    def get_constructor_standings(self, year: int, round_number: int | None = None) -> list[dict]:
        """Get constructor championship standings."""
        if round_number:
            path = f"/{year}/{round_number}/constructorStandings.json"
        else:
            path = f"/{year}/constructorStandings.json"
        data = self._get(path)
        standings_lists = data.get("StandingsTable", {}).get("StandingsLists", [])
        if standings_lists:
            return standings_lists[0].get("ConstructorStandings", [])
        return []

    # ── Pit stops ───────────────────────────────────────────────────────

    def get_pit_stops(self, year: int, round_number: int) -> list[dict]:
        """Get pit stop data for a specific race."""
        path = f"/{year}/{round_number}/pitstops.json"
        data = self._get(path, params={"limit": "1000"})
        races = data.get("RaceTable", {}).get("Races", [])
        if races:
            return races[0].get("PitStops", [])
        return []

    # ── Schedule ────────────────────────────────────────────────────────

    def get_schedule(self, year: int) -> list[dict]:
        """Get race schedule for a season."""
        path = f"/{year}.json"
        data = self._get(path, params={"limit": "50"})
        return data.get("RaceTable", {}).get("Races", [])

    # ── Drivers & Constructors ──────────────────────────────────────────

    def get_drivers(self, year: int) -> list[dict]:
        """Get driver list for a season."""
        path = f"/{year}/drivers.json"
        data = self._get(path, params={"limit": "50"})
        return data.get("DriverTable", {}).get("Drivers", [])

    def get_constructors(self, year: int) -> list[dict]:
        """Get constructor list for a season."""
        path = f"/{year}/constructors.json"
        data = self._get(path, params={"limit": "50"})
        return data.get("ConstructorTable", {}).get("Constructors", [])
