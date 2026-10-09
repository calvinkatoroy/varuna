"""Minimal in-memory Redis stand-in for offline tests (decode_responses semantics)."""
from __future__ import annotations


class FakeRedis:
    def __init__(self):
        self.kv: dict = {}
        self.lists: dict = {}
        self.sets: dict = {}

    def get(self, k):
        return self.kv.get(k)

    def set(self, k, v, ex=None, nx=False):
        if nx and k in self.kv:
            return None
        self.kv[k] = v if isinstance(v, str) else str(v)
        return True

    def delete(self, *ks):
        for k in ks:
            self.kv.pop(k, None)
            self.lists.pop(k, None)
            self.sets.pop(k, None)

    def sadd(self, k, v):
        self.sets.setdefault(k, set()).add(v)

    def srem(self, k, v):
        self.sets.get(k, set()).discard(v)

    def smembers(self, k):
        return set(self.sets.get(k, set()))

    def scan_iter(self, match="*"):
        import fnmatch
        keys = set(self.kv) | set(self.lists) | set(self.sets)
        return [k for k in keys if fnmatch.fnmatch(k, match)]

    def incr(self, k):
        n = int(self.kv.get(k, 0)) + 1
        self.kv[k] = str(n)
        return n

    def expire(self, k, seconds):
        return True

    def lpush(self, k, v):
        self.lists.setdefault(k, []).insert(0, v)

    def rpush(self, k, v):
        self.lists.setdefault(k, []).append(v)

    def rpop(self, k):
        lst = self.lists.get(k) or []
        return lst.pop() if lst else None

    def lrem(self, k, count, v):
        self.lists[k] = [x for x in self.lists.get(k, []) if x != v]

    def lrange(self, k, a, b):
        lst = self.lists.get(k, [])
        return lst[a:] if b == -1 else lst[a: b + 1]

    def ltrim(self, k, a, b):
        lst = self.lists.get(k, [])
        self.lists[k] = lst[a:] if b == -1 else lst[a: b + 1]
