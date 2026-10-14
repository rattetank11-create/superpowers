"""Простой rate limit по IP: фиксированное окно, Redis или память процесса."""

from __future__ import annotations

import threading
import time

from .config import Settings


class RateLimiter:
    def __init__(self, limit: int, window_seconds: int, redis_client=None):
        self.limit = limit
        self.window = window_seconds
        self.redis = redis_client
        self._mem: dict[str, tuple[int, float]] = {}
        self._lock = threading.Lock()

    def hit(self, key: str) -> bool:
        """Учитывает попытку. True — можно, False — лимит исчерпан."""
        if self.limit <= 0:
            return True
        if self.redis is not None:
            bucket = f"rl:{key}:{int(time.time() // self.window)}"
            count = self.redis.incr(bucket)
            if count == 1:
                self.redis.expire(bucket, self.window)
            return count <= self.limit
        with self._lock:
            now = time.time()
            count, start = self._mem.get(key, (0, now))
            if now - start >= self.window:
                count, start = 0, now
            count += 1
            self._mem[key] = (count, start)
            return count <= self.limit


def make_upload_limiter(settings: Settings) -> RateLimiter:
    client = None
    if settings.task_mode == "rq":
        from redis import Redis

        client = Redis.from_url(settings.redis_url)
    return RateLimiter(settings.rate_limit_uploads_per_hour, 3600, client)
