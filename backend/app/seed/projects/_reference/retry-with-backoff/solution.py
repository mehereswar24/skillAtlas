import functools
import time


def sleep(seconds: float) -> None:
    time.sleep(seconds)


def retry(attempts: int = 3, base_delay: float = 0.5, retry_on=(Exception,)):
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            for attempt in range(1, attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except retry_on:
                    if attempt == attempts:
                        raise
                    # Resolved from module globals at call time, which is what
                    # lets a test swap `sleep` out without waiting for real time.
                    sleep(base_delay * 2 ** (attempt - 1))

        return wrapper

    return decorator
