import bisect


def longest_increasing_subsequence(nums: list):
    if not nums:
        return 0, []

    # tails[k] = index into `nums` of the smallest possible tail value of an
    # increasing subsequence of length k + 1 found so far.
    tails = []
    # parent[i] = index of the element preceding nums[i] in the increasing
    # subsequence that ends at nums[i], or None if it starts the run.
    parent = [None] * len(nums)

    for i, value in enumerate(nums):
        pos = bisect.bisect_left([nums[t] for t in tails], value)
        if pos > 0:
            parent[i] = tails[pos - 1]
        if pos == len(tails):
            tails.append(i)
        else:
            tails[pos] = i

    length = len(tails)
    seq = []
    idx = tails[-1]
    while idx is not None:
        seq.append(nums[idx])
        idx = parent[idx]
    seq.reverse()
    return length, seq
