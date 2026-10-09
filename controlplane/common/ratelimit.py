"""Per-key counters in Redis with a window. `hit` raises RateLimited once the key passed `limit` inside the window."""
from __future__ import annotations

import redis_store


class RateLimited(Exception):
    pass


def hit(key: str, limit: int, window_s: int) -> None:
    r = redis_store.get_redis()
    k = f"rl:{key}"
    r.set(k, 0, ex=window_s, nx=True)   # creates the key WITH its expiry; INCR keeps it, so a crash cannot leave one forever
    if r.incr(k) > limit:
        raise RateLimited("too many requests; try again in a few minutes")
