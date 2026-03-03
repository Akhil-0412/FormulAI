"""Jolpica API client — drop-in Ergast replacement for historical F1 data."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import settings

logger = logging.getLogger(__name__)

# Jolpica rate limit: 4 requests/second
_CLIENT_TIMEOUT = 15.0


@dataclass
class JolpicaClient:
    """REST client for the Jolpica (Ergast-compatible) F1 API."""

    base_url: str = field(default_factory=lambda: settings.jolpica_base_url)
    _client: httpx.Client | None = field(default=None, init=False, repr=False)

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

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict:
        """Make a GET request and return the MRData dict."""
        resp = self._get_client().get(path, params=params)
        resp.raise_for_status()
        data = resp.json()
        return data.get("MRData", data)

    # ── Race results ────────────────────────────────────────────────────

    def get_race_results(self, year: int, round_number: int | None = None) -> list[dict]:
        """Get race result(s) for a season or specific round.

        Returns a list of race result dicts, each containing RaceTable data.
        """
        path = f"/{year}/results.json" if round_number is None else f"/{year}/{round_number}/results.json"
        data = self._get(path, params={"limit": "1000"})
        races = data.get("RaceTable", {}).get("Races", [])
        return races

    def get_all_season_results(self, year: int) -> list[dict]:
        """Get results for every race in a season."""
        return self.get_race_results(year)

    # ── Qualifying ──────────────────────────────────────────────────────

    def get_qualifying(self, year: int, round_number: int | None = None) -> list[dict]:
        """Get qualifying results."""
        path = f"/{year}/qualifying.json" if round_number is None else f"/{year}/{round_number}/qualifying.json"
        data = self._get(path, params={"limit": "1000"})
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
