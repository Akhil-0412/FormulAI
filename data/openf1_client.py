"""OpenF1 API client — real-time and historical F1 telemetry data."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import settings

logger = logging.getLogger(__name__)

_CLIENT_TIMEOUT = 20.0


@dataclass
class OpenF1Client:
    """REST client for the OpenF1 API (https://api.openf1.org/v1).

    Supports both historical queries (free) and polling-based live data.
    For live data, call methods with ``session_key`` from the current session.
    """

    base_url: str = field(default_factory=lambda: settings.openf1_base_url)
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

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    def _get(self, endpoint: str, params: dict[str, Any] | None = None) -> list[dict]:
        """Make a GET request and return the JSON list."""
        resp = self._get_client().get(endpoint, params=params)
        resp.raise_for_status()
        return resp.json()

    # ── Sessions ────────────────────────────────────────────────────────

    def get_sessions(self, **filters: Any) -> list[dict]:
        """List sessions. Filters: year, country_name, session_type, etc."""
        return self._get("/sessions", params=filters)

    def get_session_key(self, year: int, round_name: str, session_type: str = "Race") -> int | None:
        """Resolve a session key for a specific race weekend session.

        Args:
            year: e.g. 2024
            round_name: Country or GP name substring, e.g. "Bahrain"
            session_type: "Practice 1" / "Practice 2" / "Practice 3" / "Qualifying" / "Race"

        Returns:
            The session_key integer, or None if not found.
        """
        sessions = self.get_sessions(year=year, session_type=session_type)
        for s in sessions:
            if round_name.lower() in (s.get("country_name", "") + s.get("meeting_name", "")).lower():
                return s.get("session_key")
        return None

    # ── Intervals / gaps ────────────────────────────────────────────────

    def get_intervals(self, session_key: int, driver_number: int | None = None) -> list[dict]:
        """Get interval data (gap to leader, interval to car ahead).

        Updated every ~4 seconds during races.
        """
        params: dict[str, Any] = {"session_key": session_key}
        if driver_number is not None:
            params["driver_number"] = driver_number
        return self._get("/intervals", params=params)

    # ── Positions ───────────────────────────────────────────────────────

    def get_positions(self, session_key: int, driver_number: int | None = None) -> list[dict]:
        """Get position changes during a session."""
        params: dict[str, Any] = {"session_key": session_key}
        if driver_number is not None:
            params["driver_number"] = driver_number
        return self._get("/position", params=params)

    # ── Lap data ────────────────────────────────────────────────────────

    def get_laps(self, session_key: int, driver_number: int | None = None) -> list[dict]:
        """Get lap times, sector times, speed traps."""
        params: dict[str, Any] = {"session_key": session_key}
        if driver_number is not None:
            params["driver_number"] = driver_number
        return self._get("/laps", params=params)

    # ── Car telemetry ───────────────────────────────────────────────────

    def get_car_data(
        self,
        session_key: int,
        driver_number: int,
        speed_gte: int | None = None,
    ) -> list[dict]:
        """Get car telemetry (speed, throttle, brake, RPM, gear, DRS).

        Sampling rate ~3.7 Hz. Use speed_gte to filter high-speed data.
        """
        params: dict[str, Any] = {"session_key": session_key, "driver_number": driver_number}
        if speed_gte is not None:
            params["speed>="] = speed_gte
        return self._get("/car_data", params=params)

    # ── Pit stops ───────────────────────────────────────────────────────

    def get_pit_stops(self, session_key: int, driver_number: int | None = None) -> list[dict]:
        """Get pit stop data for a session."""
        params: dict[str, Any] = {"session_key": session_key}
        if driver_number is not None:
            params["driver_number"] = driver_number
        return self._get("/pit", params=params)

    # ── Race control ────────────────────────────────────────────────────

    def get_race_control(self, session_key: int) -> list[dict]:
        """Get race control messages (safety cars, flags, penalties)."""
        return self._get("/race_control", params={"session_key": session_key})

    # ── Weather ─────────────────────────────────────────────────────────

    def get_weather(self, session_key: int) -> list[dict]:
        """Get weather data for a session (track temp, air temp, rain, humidity, wind)."""
        return self._get("/weather", params={"session_key": session_key})

    # ── Drivers ─────────────────────────────────────────────────────────

    def get_drivers(self, session_key: int) -> list[dict]:
        """Get driver info for a session (number, name, team, colour)."""
        return self._get("/drivers", params={"session_key": session_key})

    # ── Stints ──────────────────────────────────────────────────────────

    def get_stints(self, session_key: int, driver_number: int | None = None) -> list[dict]:
        """Get stint data (compound, tyre age, stint number)."""
        params: dict[str, Any] = {"session_key": session_key}
        if driver_number is not None:
            params["driver_number"] = driver_number
        return self._get("/stints", params=params)
