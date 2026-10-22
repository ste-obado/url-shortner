"""Redis when REDIS_URL is set, otherwise an in-memory fallback.

Same interface either way, so the app (and the tests) run without Redis.
Cache problems must never take the site down, so Redis errors are swallowed.
"""
import math
import time
import uuid
from collections import defaultdict

import redis

from .config import settings


class MemoryCache:
    def __init__(self):
        self.store: dict[str, tuple[str, float | None]] = {}
        self.windows: dict[str, list[float]] = defaultdict(list)

    def get(self, key):
        item = self.store.get(key)
        if not item:
            return None
        value, exp = item
        if exp is not None and exp < time.time():
            self.store.pop(key, None)
            return None
        return value

    def set(self, key, value, ex=None):
        self.store[key] = (value, time.time() + ex if ex else None)

    def delete(self, key):
        self.store.pop(key, None)
        self.windows.pop(key, None)

    def incr(self, key, ttl):
        current = self.get(key)
        n = int(current) + 1 if current else 1
        exp = self.store[key][1] if current else time.time() + ttl
        self.store[key] = (str(n), exp)
        return n

    def window_hit(self, key, limit, window):
        now = time.time()
        hits = [t for t in self.windows[key] if t > now - window]
        if len(hits) >= limit:
            self.windows[key] = hits
            return False, max(1, math.ceil(hits[0] + window - now))
        hits.append(now)
        self.windows[key] = hits
        return True, 0

    def flush(self):
        self.store.clear()
        self.windows.clear()


class RedisCache:
    def __init__(self, url):
        self.r = redis.Redis.from_url(url, decode_responses=True)

    def get(self, key):
        try:
            return self.r.get(key)
        except redis.RedisError:
            return None

    def set(self, key, value, ex=None):
        try:
            self.r.set(key, value, ex=ex)
        except redis.RedisError:
            pass

    def delete(self, key):
        try:
            self.r.delete(key)
        except redis.RedisError:
            pass

    def incr(self, key, ttl):
        try:
            n = self.r.incr(key)
            if n == 1:
                self.r.expire(key, ttl)  # TTL only on the first failure => fixed window
            return n
        except redis.RedisError:
            return 0

    def window_hit(self, key, limit, window):
        """Sliding window log: a sorted set of request timestamps per key."""
        now = time.time()
        member = f"{now}-{uuid.uuid4()}"
        try:
            pipe = self.r.pipeline()
            pipe.zremrangebyscore(key, 0, now - window)  # forget old requests
            pipe.zadd(key, {member: now})                # record this one
            pipe.zcard(key)                              # count the window
            pipe.expire(key, window + 1)                 # clean up idle keys
            _, _, count, _ = pipe.execute()
            if count > limit:
                self.r.zrem(key, member)                 # rejected requests don't count
                oldest = self.r.zrange(key, 0, 0, withscores=True)
                retry = math.ceil(oldest[0][1] + window - now) if oldest else window
                return False, max(1, retry)
            return True, 0
        except redis.RedisError:
            return True, 0  # fail open: a Redis outage shouldn't block users


cache = RedisCache(settings.REDIS_URL) if settings.REDIS_URL else MemoryCache()
