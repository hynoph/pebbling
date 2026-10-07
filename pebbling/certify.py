"""Replay a pebbling move sequence."""


def replay(adj, P, moves, target):
    """True iff every move is legal from P in order and the result has a pebble on target."""
    Q = list(P)
    for u, w in moves:
        if w not in adj[u] or Q[u] < 2:
            return False
        Q[u] -= 2
        Q[w] += 1
    return Q[target] >= 1
