class Result:
    """Base class — construct Ok(value) or Err(error), never Result() itself."""

    def is_ok(self) -> bool:
        raise NotImplementedError

    def map(self, fn):
        raise NotImplementedError

    def and_then(self, fn):
        raise NotImplementedError

    def unwrap_or(self, default):
        raise NotImplementedError


class Ok(Result):
    def __init__(self, value):
        self.value = value

    def is_ok(self):
        return True

    def map(self, fn):
        return Ok(fn(self.value))

    def and_then(self, fn):
        return fn(self.value)

    def unwrap_or(self, default):
        return self.value

    def __eq__(self, other):
        return isinstance(other, Ok) and self.value == other.value

    def __repr__(self):
        return f"Ok({self.value!r})"


class Err(Result):
    def __init__(self, error):
        self.error = error

    def is_ok(self):
        return False

    def map(self, fn):
        return self

    def and_then(self, fn):
        return self

    def unwrap_or(self, default):
        return default

    def __eq__(self, other):
        return isinstance(other, Err) and self.error == other.error

    def __repr__(self):
        return f"Err({self.error!r})"
