class FenwickTree:
    """A Fenwick (binary indexed) tree over `size` zero-initialised slots."""

    def __init__(self, size: int):
        self.size = size
        self.tree = [0] * (size + 1)

    def update(self, index: int, delta: int) -> None:
        i = index + 1  # internal storage is 1-indexed
        while i <= self.size:
            self.tree[i] += delta
            i += i & (-i)

    def prefix_sum(self, index: int) -> int:
        i = index + 1
        total = 0
        while i > 0:
            total += self.tree[i]
            i -= i & (-i)
        return total

    def range_sum(self, left: int, right: int) -> int:
        if left == 0:
            return self.prefix_sum(right)
        return self.prefix_sum(right) - self.prefix_sum(left - 1)
