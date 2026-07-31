import math


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("no samples")
    rank = math.ceil(p / 100 * len(ordered))
    return ordered[min(max(rank, 1), len(ordered)) - 1]


def error_budget(total: int, failed: int, target: float) -> dict:
    allowed = math.floor(total * (1 - target))
    remaining = max(0, allowed - failed)
    if allowed == 0:
        burned = 100.0 if failed else 0.0
    else:
        burned = round(failed / allowed * 100, 1)
    return {
        "allowed": allowed,
        "used": failed,
        "remaining": remaining,
        "burned_percent": burned,
    }


def should_page(budget: dict, elapsed_fraction: float) -> bool:
    return budget["burned_percent"] / 100 > 2 * elapsed_fraction
