import contextlib


class PoolExhausted(Exception):
    """Raised when no connection is free and the pool is at capacity."""


class ConnectionPool:
    """A fixed-size pool of connections, checked out via `with`."""

    def __init__(self, create, max_size: int):
        self._create = create
        self._max_size = max_size
        self._free = []
        self._in_use = 0

    @contextlib.contextmanager
    def acquire(self):
        """Return a context manager yielding one checked-out connection."""
        if self._free:
            conn = self._free.pop()
        elif self._in_use < self._max_size:
            conn = self._create()
        else:
            raise PoolExhausted(f"all {self._max_size} connections are checked out")

        self._in_use += 1
        try:
            yield conn
        finally:
            self._in_use -= 1
            self._free.append(conn)
