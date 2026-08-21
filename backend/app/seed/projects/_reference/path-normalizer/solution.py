def normalize_path(*parts: str) -> str:
    """Join and normalise POSIX-style path segments, from scratch."""
    absolute = bool(parts) and parts[0].startswith("/")
    segments = "/".join(parts).split("/")

    stack = []
    for segment in segments:
        if segment in ("", "."):
            continue
        if segment == "..":
            if stack and stack[-1] != "..":
                stack.pop()
            elif not absolute:
                stack.append("..")
            # else: absolute and nothing to cancel — drop it, can't go
            # above root.
        else:
            stack.append(segment)

    path = "/".join(stack)
    if absolute:
        return "/" + path
    return path or "."
