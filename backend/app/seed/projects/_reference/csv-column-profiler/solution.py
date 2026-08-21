def profile(rows: list[dict]) -> dict:
    """Return per-column null/type/distinct stats for a CSV export."""
    columns = {col: [] for row in rows for col in row}
    for col in columns:
        columns[col] = [row.get(col, "") for row in rows]

    result = {}
    for col, values in columns.items():
        null_count = int_count = float_count = text_count = 0
        distinct = set()
        for raw in values:
            value = raw.strip()
            if value.lower() in {"", "null", "n/a"}:
                null_count += 1
                continue
            distinct.add(value)
            try:
                int(value)
                int_count += 1
                continue
            except ValueError:
                pass
            try:
                float(value)
                float_count += 1
                continue
            except ValueError:
                pass
            text_count += 1
        result[col] = {
            "null_count": null_count,
            "int_count": int_count,
            "float_count": float_count,
            "text_count": text_count,
            "distinct_count": len(distinct),
        }
    return result
