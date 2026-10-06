"""In-memory token-bucket rate limiting.

Good enough for a single API process. Behind multiple replicas, swap ``RateLimiter`` for a
Redis-backed implementation or enforce limits at the gateway (Zeabur/Cloudflare/nginx).
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

MAX_TRACKED_CLIENTS = 10_000


@dataclass
class _Bucket:
    tokens: float
    updated: float


class RateLimiter:
    def __init__(self, per_minute: int) -> None:
        self.capacity = float(per_minute)
        self.refill_per_second = per_minute / 60.0
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return self.capacity > 0

    def allow(self, client: str) -> bool:
        if not self.enabled:
            return True
        now = time.monotonic()
        with self._lock:
            if len(self._buckets) > MAX_TRACKED_CLIENTS:
                self._buckets.clear()
            bucket = self._buckets.get(client)
            if bucket is None:
                bucket = self._buckets[client] = _Bucket(self.capacity, now)
            bucket.tokens = min(
                self.capacity, bucket.tokens + (now - bucket.updated) * self.refill_per_second
            )
            bucket.updated = now
            if bucket.tokens < 1.0:
                return False
            bucket.tokens -= 1.0
            return True
