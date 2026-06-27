"""Experimental client for The Odds API to get pre-race odds."""

import logging
from typing import Any

import httpx

from config.settings import settings

logger = logging.getLogger(__name__)

class OddsClient:
    """Client for pulling pre-race odds from the-odds-api.com."""

    def __init__(self) -> None:
        self.api_key = settings.odds_api_key
        self.base_url = "https://api.the-odds-api.com/v4"
        self._client = httpx.Client(base_url=self.base_url, timeout=10.0)

    def get_f1_odds(self, market: str = "outrights") -> list[dict[str, Any]]:
        """Get pre-race odds for F1."""
        if not self.api_key or not settings.enable_odds_feature:
            logger.info("Odds feature is disabled or API key is missing.")
            return []
        
        try:
            response = self._client.get(
                "/sports/motoracing_formula_1/odds",
                params={
                    "apiKey": self.api_key,
                    "regions": "eu,uk",
                    "markets": market,
                    "oddsFormat": "decimal"
                }
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.warning(f"Failed to fetch odds: {e}")
            return []
