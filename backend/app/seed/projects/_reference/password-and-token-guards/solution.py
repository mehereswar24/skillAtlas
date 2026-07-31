import hashlib
import hmac


class AuthError(Exception):
    """Raised for any token we refuse to accept."""


def _signature(data: str, secret: str) -> str:
    return hmac.new(secret.encode(), data.encode(), hashlib.sha256).hexdigest()


def sign(payload: dict, secret: str) -> str:
    data = "&".join(f"{key}={value}" for key, value in sorted(payload.items()))
    return f"{data}.{_signature(data, secret)}"


def constant_time_equal(a: str, b: str) -> bool:
    if len(a) != len(b):
        return False
    difference = 0
    for x, y in zip(a, b):
        difference |= ord(x) ^ ord(y)
    return difference == 0


def verify(token: str, secret: str, now: int) -> dict:
    data, separator, signature = token.partition(".")
    if not separator or "." in signature:
        raise AuthError("invalid token")

    if not constant_time_equal(signature, _signature(data, secret)):
        raise AuthError("invalid token")

    payload = dict(pair.split("=", 1) for pair in data.split("&") if "=" in pair)
    if int(payload.get("exp", 0)) <= now:
        raise AuthError("token expired")
    return payload
