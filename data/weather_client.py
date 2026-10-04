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

# Past weather lives on a different host from the forecast endpoint — the
# forecast API only reaches back a few days, so historical backfill must use
# the archive service.
_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

# Hours around the local start time treated as "the race": one hour before
# (formation lap, grid) through three after (a GP runs ~2h including delays).
_RACE_WINDOW_BEFORE = 1
_RACE_WINDOW_AFTER = 3

# Hourly precipitation above this (mm) counts as a wet hour.
_WET_HOUR_MM = 0.1


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
    def _get(self, params: dict[str, Any], url: str | None = None) -> dict:
        resp = self._get_client().get(url or self.base_url, params=params)
        resp.raise_for_status()
        return resp.json()

    def get_historical(
        self,
        circuit_key: str,
        race_date: str,
    ) -> dict[str, float | str | None]:
        """Get *observed* weather over the race window for a past race.

        `get_forecast` cannot serve historical dates, so backfilling training
        data has to come from the archive service. Values are aggregated over
        the local race window rather than the whole day — overnight rain at a
        circuit says nothing about a dry afternoon race.

        `precipitation_prob` is returned on the same 0–1 scale the forecast
        path uses, here meaning "fraction of race-window hours with rain".

        Args:
            circuit_key: Key from circuits.json (e.g. "silverstone").
            race_date: ISO date string (e.g. "2024-07-07").
        """
        circuit = self._circuits.get(circuit_key)
        if circuit is None:
            logger.warning("Unknown circuit key: %s", circuit_key)
            return _empty_weather()

        params = {
            "latitude": circuit["lat"],
            "longitude": circuit["lon"],
            "start_date": race_date,
            "end_date": race_date,
            "hourly": ("temperature_2m,precipitation,relative_humidity_2m,"
                       "wind_speed_10m,weather_code"),
            "timezone": "auto",
        }

        data = self._get(params, url=_ARCHIVE_URL)
        hourly = data.get("hourly", {})
        times = hourly.get("time") or []
        if not times:
            logger.warning("No hourly archive data for %s on %s", circuit_key, race_date)
            return _empty_weather()

        start_hour = int(circuit.get("race_start_hour_local", 14))
        lo = start_hour - _RACE_WINDOW_BEFORE
        hi = start_hour + _RACE_WINDOW_AFTER

        idx = [
            i for i, t in enumerate(times)
            if lo <= int(str(t)[11:13]) <= hi
        ]
        if not idx:  # fall back to the whole day rather than returning nothing
            idx = list(range(len(times)))

        def window(field: str) -> list[float]:
            series = hourly.get(field) or []
            return [series[i] for i in idx
                    if i < len(series) and series[i] is not None]

        temps = window("temperature_2m")
        precip = window("precipitation")
        humid = window("relative_humidity_2m")
        wind = window("wind_speed_10m")
        codes = window("weather_code")

        wet_fraction = (
            sum(1 for p in precip if p >= _WET_HOUR_MM) / len(precip)
            if precip else 0.0
        )
        worst_code = max(codes) if codes else None

        return {
            "temperature": max(temps) if temps else None,
            "precipitation_prob": round(wet_fraction, 4),
            "wind_speed": max(wind) if wind else None,
            "humidity": max(humid) if humid else None,
            "weather_code": worst_code,
            "condition": _weather_code_to_condition(
                int(worst_code) if worst_code is not None else None
            ),
        }

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
        # Open-Meteo reports this as a percentage. Consumers (and the archive
        # path) treat precipitation_prob as 0–1 — `form_features` tests
        # `> 0.5` — so a raw percentage would mark almost every race wet.
        precip_pct = _safe_first(daily.get("precipitation_probability_max"))
        return {
            "temperature": _safe_first(daily.get("temperature_2m_max")),
            "precipitation_prob": None if precip_pct is None else precip_pct / 100.0,
            "wind_speed": _safe_first(daily.get("windspeed_10m_max")),
            "humidity": _safe_first(daily.get("relative_humidity_2m_max")),
            "weather_code": weather_code,
            "condition": _weather_code_to_condition(weather_code),
        }

    def get_circuit_info(self, circuit_key: str) -> dict | None:
        """Return metadata (lat, lon, type, overtake_difficulty) for a circuit."""
        return self._circuits.get(circuit_key)


def _empty_weather() -> dict[str, float | str | None]:
    """Placeholder row used when a circuit or its data can't be resolved."""
    return {
        "temperature": None,
        "precipitation_prob": None,
        "wind_speed": None,
        "humidity": None,
        "weather_code": None,
        "condition": "unknown",
    }


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
