"""Path-specific reachability by carries."""
from fractions import Fraction


def left_arrivals(P):
    n = len(P)
    A = [0] * n
    carry = 0
    for i in range(1, n):
        carry = (P[i - 1] + carry) // 2
        A[i] = carry
    return A


def right_arrivals(P):
    n = len(P)
    B = [0] * n
    carry = 0
    for i in range(n - 2, -1, -1):
        carry = (P[i + 1] + carry) // 2
        B[i] = carry
    return B


def reachable(P):
    A = left_arrivals(P)
    B = right_arrivals(P)
    return [P[i] + A[i] + B[i] >= 1 for i in range(len(P))]


def solvable(P):
    return all(reachable(P))


def minimality_status(P):
    """'unsolvable', 'not_minimal' or 'minimal'; for 'minimal' also v -> an unreachable vertex of P - e_v."""
    if not solvable(P):
        return "unsolvable", None
    witnesses = {}
    Q = list(P)
    for v, c in enumerate(P):
        if c == 0:
            continue
        Q[v] -= 1
        r = reachable(Q)
        Q[v] += 1
        bad = [i for i, ok in enumerate(r) if not ok]
        if not bad:
            return "not_minimal", v
        witnesses[v] = bad[0]
    return "minimal", witnesses


def value(P, X):
    return sum((Fraction(c, 2 ** abs(X - y)) for y, c in enumerate(P) if c), Fraction(0))
