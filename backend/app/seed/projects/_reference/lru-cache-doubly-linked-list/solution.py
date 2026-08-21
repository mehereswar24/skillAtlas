class Node:
    """A doubly linked list node holding one cache entry."""
    __slots__ = ("key", "value", "prev", "next")

    def __init__(self, key=None, value=None):
        self.key = key
        self.value = value
        self.prev = None
        self.next = None


class LRUCache:
    """Fixed-capacity cache, O(1) get/put, evicting least-recently-used.

    Backed by a real doubly linked list (most-recently-used right after the
    head sentinel, least-recently-used right before the tail sentinel) plus
    a dict for O(1) node lookup by key.
    """

    def __init__(self, capacity: int):
        self.capacity = capacity
        self._map = {}
        self._head = Node()
        self._tail = Node()
        self._head.next = self._tail
        self._tail.prev = self._head

    def _remove(self, node):
        node.prev.next = node.next
        node.next.prev = node.prev

    def _push_front(self, node):
        node.next = self._head.next
        node.prev = self._head
        self._head.next.prev = node
        self._head.next = node

    def get(self, key):
        node = self._map.get(key)
        if node is None:
            return -1
        self._remove(node)
        self._push_front(node)
        return node.value

    def put(self, key, value) -> None:
        node = self._map.get(key)
        if node is not None:
            node.value = value
            self._remove(node)
            self._push_front(node)
            return

        node = Node(key, value)
        self._map[key] = node
        self._push_front(node)

        if len(self._map) > self.capacity:
            lru = self._tail.prev
            self._remove(lru)
            del self._map[lru.key]
