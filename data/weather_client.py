"""Open-Meteo weather client — fetches forecast for circuit locations."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import settings

logger = logging.getLogger(__name__)

_CIRCUITS_PATH = Path(__file__).resolve().parent.parent / "config" / "circuits.json"


def _load_circuits() -> dict[str, dict]:
    """Load circuit metadata from circuits.json."""
    with open(_CIRCUITS_PATH) as f:
        return json.load(f).get("circuits", {})


@dataclass
class WeatherClient:
    """Client for Open-Meteo free weather API."""

    base_url: str = field(default_factory=lambda: settings.openmeteo_base_url)
    _client: httpx.Client | None = field(default=None, init=False, repr=False)
    _circuits: dict[str, dict] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        self._circuits = _load_circuits()

    def _get_client(self) -> httpx.Client:
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(timeout=15.0)
        return self._client

    def close(self) -> None:
        if self._client and not self._client.is_closed:
            self._client.close()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    def _get(self, params: dict[str, Any]) -> dict:
        resp = self._get_client().get(self.base_url, params=params)
        resp.raise_for_status()
        return resp.json()

    def get_forecast(
        self,
        circuit_key: str,
        race_date: str,
    ) -> dict[str, float | str | None]:
        """Get weather forecast for a circuit on a specific date.

        Args:
            circuit_key: Key from circuits.json (e.g. "silverstone").
            race_date: ISO date string (e.g. "2024-07-07").

        Returns:
            Dict with keys: temperature, precipitation_prob, wind_speed,
            humidity, weather_code, condition.
        """
        circuit = self._circuits.get(circuit_key)
        if circuit is None:
            logger.warning("Unknown circuit key: %s", circuit_key)
            return {
                "temperature": None,
                "precipitation_prob": None,
                "wind_speed": None,
                "humidity": None,
                "weather_code": None,
                "condition": "unknown",
            }

        params = {
            "latitude": circuit["lat"],
            "longitude": circuit["lon"],
            "daily": "temperature_2m_max,precipitation_probability_max,windspeed_10m_max,relative_humidity_2m_max,weathercode",
            "start_date": race_date,
            "end_date": race_date,
            "timezone": "auto",
        }

        data = self._get(params)
        daily = data.get("daily", {})

        # Extract first (only) day
        weather_code = _safe_first(daily.get("weathercode"))
        return {
            "temperature": _safe_first(daily.get("temperature_2m_max")),
            "precipitation_prob": _safe_first(daily.get("precipitation_probability_max")),
            "wind_speed": _safe_first(daily.get("windspeed_10m_max")),
            "humidity": _safe_first(daily.get("relative_humidity_2m_max")),
            "weather_code": weather_code,
            "condition": _weather_code_to_condition(weather_code),
        }

    def get_circuit_info(self, circuit_key: str) -> dict | None:
        """Return metadata (lat, lon, type, overtake_difficulty) for a circuit."""
        return self._circuits.get(circuit_key)


def _safe_first(lst: list | None) -> float | int | None:
    """Safely extract first element from a list."""
    if lst and len(lst) > 0:
        return lst[0]
    return None


def _weather_code_to_condition(code: int | None) -> str:
    """Convert WMO weather code to simple condition label."""
    if code is None:
        return "unknown"
    if code <= 3:
        return "dry"
    if code <= 49:
        return "cloudy"
    if code <= 69:
        return "rain"
    if code <= 79:
        return "snow"
    if code <= 99:
        return "storm"
    return "unknown"
