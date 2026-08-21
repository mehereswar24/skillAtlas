def build_failure_function(pattern: str) -> list:
    n = len(pattern)
    fail = [0] * n
    k = 0
    for i in range(1, n):
        while k > 0 and pattern[i] != pattern[k]:
            k = fail[k - 1]
        if pattern[i] == pattern[k]:
            k += 1
        fail[i] = k
    return fail


def find_all(text: str, pattern: str) -> list:
    if not pattern or len(pattern) > len(text):
        return []

    fail = build_failure_function(pattern)
    matches = []
    k = 0
    for i, ch in enumerate(text):
        while k > 0 and ch != pattern[k]:
            k = fail[k - 1]
        if ch == pattern[k]:
            k += 1
        if k == len(pattern):
            matches.append(i - k + 1)
            k = fail[k - 1]
    return matches
