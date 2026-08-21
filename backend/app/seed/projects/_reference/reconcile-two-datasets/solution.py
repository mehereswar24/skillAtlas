def reconcile(source: list[dict], target: list[dict], key: str) -> dict:
    """Diff two exports of the same entity, keyed by `key`."""
    src = {row[key]: row for row in source}
    tgt = {row[key]: row for row in target}

    removed = sorted(k for k in src if k not in tgt)
    added = sorted(k for k in tgt if k not in src)

    changed = {}
    for k in src:
        if k not in tgt:
            continue
        old, new = src[k], tgt[k]
        shared = set(old) & set(new)
        diffs = {f: [old[f], new[f]] for f in shared if old[f] != new[f]}
        if diffs:
            changed[k] = diffs

    return {"added": added, "removed": removed, "changed": changed}
