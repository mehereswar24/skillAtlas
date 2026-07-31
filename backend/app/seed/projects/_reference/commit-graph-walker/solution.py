def ancestors(graph: dict, commit: str) -> set:
    seen, stack = set(), [commit]
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        stack.extend(graph.get(node, []))
    return seen


def merge_base(graph: dict, a: str, b: str):
    common = ancestors(graph, a) & ancestors(graph, b)
    if not common:
        return None
    for candidate in common:
        # Lowest = not a strict ancestor of any other common ancestor.
        if not any(
            candidate in ancestors(graph, other) - {other}
            for other in common
            if other != candidate
        ):
            return candidate
    return None
