import functools
import time


class RateLimitExceeded(Exception):
    """Raised when a call is refused because the bucket is empty."""


def rate_limited(rate: float, capacity: float, clock=time.monotonic):
    """Return a decorator enforcing `rate` tokens/second, capped at `capacity`."""

    def decorator(fn):
        state = {"tokens": capacity, "last": clock()}

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            now = clock()
            elapsed = now - state["last"]
            state["tokens"] = min(capacity, state["tokens"] + elapsed * rate)
            state["last"] = now

            if state["tokens"] < 1:
                raise RateLimitExceeded(
                    f"no tokens available ({state['tokens']:.2f} < 1)"
                )
            state["tokens"] -= 1
            return fn(*args, **kwargs)

        return wrapper

    return decorator
