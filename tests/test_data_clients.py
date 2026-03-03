"""Tests for data client modules."""

import pytest


class TestJolpicaClient:
    """Tests for the Jolpica API client."""

    def test_client_initializes(self):
        from data.jolpica_client import JolpicaClient
        client = JolpicaClient()
        assert client.base_url.startswith("https://")
        client.close()

    def test_schedule_returns_list(self):
        from data.jolpica_client import JolpicaClient
        client = JolpicaClient()
        try:
            # Test fetching schedule for an upcoming future season
            schedule = client.get_schedule(2026)
            assert isinstance(schedule, list)
            assert len(schedule) > 0
            # Each race should have a round number
            assert "round" in schedule[0]
        finally:
            client.close()

    def test_race_results_structure(self):
        from data.jolpica_client import JolpicaClient
        client = JolpicaClient()
        try:
            races = client.get_race_results(2023, 1)
            assert isinstance(races, list)
            if races:
                assert "Results" in races[0]
                results = races[0]["Results"]
                assert len(results) > 0
                assert "Driver" in results[0]
        finally:
            client.close()

    def test_driver_standings(self):
        from data.jolpica_client import JolpicaClient
        client = JolpicaClient()
        try:
            standings = client.get_driver_standings(2023)
            assert isinstance(standings, list)
            assert len(standings) > 0
            assert "Driver" in standings[0]
            assert "points" in standings[0]
        finally:
            client.close()


class TestOpenF1Client:
    """Tests for the OpenF1 API client."""

    def test_client_initializes(self):
        from data.openf1_client import OpenF1Client
        client = OpenF1Client()
        assert client.base_url.startswith("https://")
        client.close()

    def test_sessions_returns_list(self):
        from data.openf1_client import OpenF1Client
        client = OpenF1Client()
        try:
            sessions = client.get_sessions(year=2023, session_type="Race")
            assert isinstance(sessions, list)
            assert len(sessions) > 0
        finally:
            client.close()

    def test_future_sessions_returns_empty(self):
        from data.openf1_client import OpenF1Client
        client = OpenF1Client()
        try:
            # OpenF1 should gracefully return an empty list for sessions that don't exist yet
            sessions = client.get_sessions(year=2026, session_type="Race")
            assert isinstance(sessions, list)
            assert len(sessions) == 0
        finally:
            client.close()


class TestWeatherClient:
    """Tests for the Open-Meteo weather client."""

    def test_circuit_lookup(self):
        from data.weather_client import WeatherClient
        client = WeatherClient()
        info = client.get_circuit_info("silverstone")
        assert info is not None
        assert "lat" in info
        assert "lon" in info

    def test_unknown_circuit(self):
        from data.weather_client import WeatherClient
        client = WeatherClient()
        info = client.get_circuit_info("nonexistent")
        assert info is None
