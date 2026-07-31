def schedule(jobs: dict[str, list[str]]) -> list[list[str]]:
    remaining = {name: set(deps) for name, deps in jobs.items()}
    waves: list[list[str]] = []
    done: set[str] = set()

    while remaining:
        ready = sorted(name for name, deps in remaining.items() if deps <= done)
        if not ready:
            raise ValueError("cycle detected")
        waves.append(ready)
        done.update(ready)
        for name in ready:
            del remaining[name]

    return waves
