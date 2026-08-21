def days_needed(weights: list, capacity: int) -> int:
    days = 1
    load = 0
    for w in weights:
        if load + w > capacity:
            days += 1
            load = 0
        load += w
    return days


def min_capacity_to_ship(weights: list, days: int) -> int:
    lo = max(weights)
    hi = sum(weights)
    while lo < hi:
        mid = lo + (hi - lo) // 2
        if days_needed(weights, mid) <= days:
            hi = mid
        else:
            lo = mid + 1
    return lo
