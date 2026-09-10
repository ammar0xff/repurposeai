"""In-memory token-bucket rate limiter (no Redis required).
Per-IP + per-path buckets. Distributed deployments should front with a proxy."""
import time


class RateLimiter:
    def __init__(self, per_minute: int = 120, burst: int = 30):
        self.per_minute, self.burst = per_minute, burst
        self._buckets: dict[str, list] = {}

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        window, cap = 60.0, self.burst
        hits = [t for t in self._buckets.get(key, []) if now - t < window]
        rate = self.per_minute / 60.0
        # token bucket approximated over the window
        allowed = len(hits) < max(cap, int(rate * window))
        if allowed:
            hits.append(now)
        self._buckets[key] = hits[-cap * 2:]
        # periodic prune
        if len(self._buckets) > 10000:
            self._buckets = {k: v for k, v in self._buckets.items() if v and now - v[-1] < window}
        return allowed


LIMITER = RateLimiter()
