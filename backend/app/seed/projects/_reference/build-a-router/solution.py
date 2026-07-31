class Router:
    """A method + path router, the way a web framework does it."""

    def __init__(self):
        self.routes = []

    def route(self, method: str, path: str):
        def decorator(fn):
            self.routes.append((method, path.strip("/").split("/"), fn))
            return fn

        return decorator

    def dispatch(self, method: str, path: str):
        segments = path.strip("/").split("/")
        path_matched = False
        best = None

        for route_method, pattern, fn in self.routes:
            params = _match(pattern, segments)
            if params is None:
                continue
            path_matched = True
            if route_method != method:
                continue
            # Fewer parameters means a more specific route.
            if best is None or len(params) < len(best[1]):
                best = (fn, params)

        if best is not None:
            fn, params = best
            return fn(**params)
        if path_matched:
            return 405, {"error": "Method Not Allowed"}
        return 404, {"error": "Not Found"}


def _match(pattern: list[str], segments: list[str]) -> dict | None:
    if len(pattern) != len(segments):
        return None
    params = {}
    for part, value in zip(pattern, segments):
        if part.startswith("{") and part.endswith("}"):
            params[part[1:-1]] = value
        elif part != value:
            return None
    return params
