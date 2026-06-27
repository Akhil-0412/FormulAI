"""Redis-based caching for API."""

import json
import logging
from typing import Any, Optional
import redis
from config.settings import settings

logger = logging.getLogger(__name__)

class Cache:
    def __init__(self):
        try:
            self.redis = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                decode_responses=True
            )
            self.redis.ping()
        except redis.ConnectionError:
            logger.warning("Redis not available. Running without cache.")
            self.redis = None

    def get(self, key: str) -> Optional[Any]:
        if not self.redis:
            return None
        val = self.redis.get(key)
        if val:
            return json.loads(val)
        return None

    def set(self, key: str, value: Any, ttl: int = 3600):
        if not self.redis:
            return
        self.redis.set(key, json.dumps(value), ex=ttl)

cache = Cache()
