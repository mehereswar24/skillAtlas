import bisect
import hashlib


def hash_key(value: str) -> int:
    digest = hashlib.md5(value.encode()).hexdigest()
    return int(digest[:8], 16)


class HashRing:
    """Consistent hashing with virtual nodes."""

    def __init__(self, nodes: list[str] | None = None, replicas: int = 100):
        self.replicas = replicas
        self._positions: list[int] = []
        self._nodes: dict[int, str] = {}
        for node in nodes or []:
            self.add_node(node)

    def add_node(self, node: str) -> None:
        for i in range(self.replicas):
            position = hash_key(f"{node}:{i}")
            if position in self._nodes:
                continue
            bisect.insort(self._positions, position)
            self._nodes[position] = node

    def remove_node(self, node: str) -> None:
        for i in range(self.replicas):
            position = hash_key(f"{node}:{i}")
            if self._nodes.get(position) != node:
                continue
            del self._nodes[position]
            index = bisect.bisect_left(self._positions, position)
            self._positions.pop(index)

    def get_node(self, key: str):
        if not self._positions:
            return None
        index = bisect.bisect_left(self._positions, hash_key(key))
        if index == len(self._positions):
            index = 0
        return self._nodes[self._positions[index]]
