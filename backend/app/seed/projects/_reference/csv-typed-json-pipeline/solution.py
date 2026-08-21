def infer(value):
    if value == "":
        return None
    if value.lower() in ("true", "false"):
        return value.lower() == "true"
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


def typed_rows(lines):
    """Yield each data row as a dict with inferred types.

    `lines` is an iterable: the first item is the comma-separated
    header, the rest are data rows. Must be a generator function —
    consuming only the first result must not touch the rest of
    `lines`.
    """
    iterator = iter(lines)
    header = next(iterator).split(",")
    for line in iterator:
        values = line.split(",")
        yield {name: infer(value) for name, value in zip(header, values)}
