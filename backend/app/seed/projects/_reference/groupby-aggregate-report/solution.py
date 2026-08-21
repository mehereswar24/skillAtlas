import math
import statistics


def summarize(rows: list[dict], group_by: str, value_field: str) -> dict:
    """Group `rows` by `group_by` and summarize `value_field` per group."""
    groups: dict = {}
    for row in rows:
        groups.setdefault(row[group_by], []).append(row[value_field])

    result = {}
    for key, values in groups.items():
        ordered = sorted(values)
        n = len(ordered)
        rank = math.ceil(0.9 * n)
        p90 = ordered[min(max(rank, 1), n) - 1]
        result[key] = {
            "count": n,
            "total": round(sum(values), 2),
            "mean": round(sum(values) / n, 2),
            "median": round(statistics.median(values), 2),
            "p90": round(p90, 2),
        }
    return result
