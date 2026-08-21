def next_greater(nums: list) -> list:
    result = [-1] * len(nums)
    stack = []  # indices whose next-greater value is still unknown

    for i, value in enumerate(nums):
        while stack and nums[stack[-1]] < value:
            j = stack.pop()
            result[j] = value
        stack.append(i)

    return result
