"""pi(G) and pi_opt(G) by exhaustive enumeration of distributions."""
from itertools import combinations
from math import comb


def distributions(n, k):
    """All distributions of k pebbles on n vertices (stars and bars), each exactly once."""
    if n == 1:
        yield (k,)
        return
    last = k + n - 2
    for bars in combinations(range(k + n - 1), n - 1):
        out = []
        prev = -1
        for b in bars:
            out.append(b - prev - 1)
            prev = b
        out.append(last - prev)
        yield tuple(out)


def count_distributions(n, k):
    return comb(k + n - 1, n - 1)


def pebbling_number(n, is_solvable, k_max=10**9):
    """Pebbling number by scanning k upward; returns a dict with the value and witnesses."""
    witness_below = tuple([0] * n)  # the empty distribution is unsolvable
    per_k = []
    for k in range(1, k_max + 1):
        checked = 0
        found = None
        for P in distributions(n, k):
            checked += 1
            if not is_solvable(P):
                found = P
                break
        per_k.append({"k": k, "checked": checked, "unsolvable_example": found})
        if found is None:
            return {"value": k, "witness_below": witness_below, "checked_at_value": checked,
                    "total_at_value": count_distributions(n, k), "per_k": per_k}
        witness_below = found
    return {"value": None, "per_k": per_k}


def optimal_pebbling_number(n, is_solvable, k_max=10**9):
    """Optimal pebbling number by scanning k upward; returns a dict with the value and witnesses."""
    per_k = []
    for k in range(1, k_max + 1):
        checked = 0
        found = None
        for P in distributions(n, k):
            checked += 1
            if is_solvable(P):
                found = P
                break
        per_k.append({"k": k, "checked": checked, "solvable_example": found})
        if found is not None:
            below = per_k[-2]["checked"] if len(per_k) > 1 else 0
            return {"value": k, "witness": found, "checked_all_unsolvable_at_k_minus_1": below,
                    "total_at_k_minus_1": count_distributions(n, k - 1) if k > 1 else 1,
                    "per_k": per_k}
    return {"value": None, "per_k": per_k}
