from collections import OrderedDict


class LRUCache:
    """Least-recently-used eviction with per-entry expiry."""

    def __init__(self, capacity: int, ttl: float):
        self.capacity = capacity
        self.ttl = ttl
        self.hits = 0
        self.misses = 0
        self._entries: OrderedDict = OrderedDict()

    def get(self, key, now: float):
        entry = self._entries.get(key)
        if entry is None:
            self.misses += 1
            return None

        value, stored_at = entry
        if now - stored_at >= self.ttl:
            del self._entries[key]
            self.misses += 1
            return None

        self._entries.move_to_end(key)
        self.hits += 1
        return value

    def set(self, key, value, now: float) -> None:
        self._entries[key] = (value, now)
        self._entries.move_to_end(key)
        while len(self._entries) > self.capacity:
            self._entries.popitem(last=False)
