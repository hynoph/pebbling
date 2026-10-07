"""Deliberately naive pebbling checker, written independently of the `pebbling` package."""
from fractions import Fraction


def build_adjacency(spec):
    kind, _, rest = spec.partition(":")
    if kind == "grid":
        rows, cols = (int(t) for t in rest.split("x"))
        adj = [[] for _ in range(rows * cols)]
        for r in range(rows):
            for c in range(cols):
                for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    r2, c2 = r + dr, c + dc
                    if 0 <= r2 < rows and 0 <= c2 < cols:
                        adj[r * cols + c].append(r2 * cols + c2)
        return adj
    if kind == "path":
        n = int(rest)
        return [[x for x in (i - 1, i + 1) if 0 <= x < n] for i in range(n)]
    if kind == "cycle":
        n = int(rest)
        return [sorted({(i - 1) % n, (i + 1) % n}) for i in range(n)]
    if kind == "complete":
        n = int(rest)
        return [[j for j in range(n) if j != i] for i in range(n)]
    if kind == "petersen":
        adj = [[] for _ in range(10)]
        pairs = []
        for i in range(5):
            pairs.append((i, (i + 1) % 5))
            pairs.append((i, i + 5))
            pairs.append((5 + i, 5 + (i + 2) % 5))
        for a, b in pairs:
            adj[a].append(b)
            adj[b].append(a)
        return adj
    if kind == "edges":
        n_str, _, e_str = rest.partition(":")
        adj = [[] for _ in range(int(n_str))]
        for e in e_str.split(";"):
            if e:
                a, b = (int(t) for t in e.split("-"))
                adj[a].append(b)
                adj[b].append(a)
        return adj
    raise ValueError(spec)


def distances_from(adj, source):
    dist = {source: 0}
    frontier = [source]
    while frontier:
        nxt = []
        for x in frontier:
            for y in adj[x]:
                if y not in dist:
                    dist[y] = dist[x] + 1
                    nxt.append(y)
        frontier = nxt
    return [dist[v] for v in range(len(adj))]


def value(adj, P, X):
    d = distances_from(adj, X)
    total = Fraction(0)
    for y in range(len(adj)):
        total += Fraction(P[y], 2 ** d[y])
    return total


def replay_moves(adj, P, moves, X):
    state = list(P)
    for u, w in moves:
        if w not in adj[u]:
            return False
        if state[u] < 2:
            return False
        state[u] -= 2
        state[w] += 1
    return state[X] >= 1


class StateLimit(Exception):
    pass


def is_reachable(adj, P, X, prune_by_value=False, max_states=None, greedy_only=False):
    """Forward depth-first search over pebbling states."""
    start = tuple(P)
    if start[X] > 0:
        return True
    d = distances_from(adj, X)
    half_powers = [Fraction(1, 2 ** k) for k in range(max(d) + 2)]
    start_val = sum((Fraction(P[y], 2 ** d[y]) for y in range(len(adj))), Fraction(0))
    if prune_by_value and start_val < 1:
        return False
    seen = {start}
    stack = [(start, start_val)]
    n = len(adj)
    while stack:
        state, val = stack.pop()
        candidates = []
        for u in range(n):
            if state[u] >= 2:
                for w in adj[u]:
                    if greedy_only and d[w] >= d[u]:
                        continue
                    candidates.append((u, w))
        candidates.sort(key=lambda m: d[m[1]] - d[m[0]], reverse=True)
        for u, w in candidates:
            nxt = list(state)
            nxt[u] -= 2
            nxt[w] += 1
            if w == X:
                return True
            nxt = tuple(nxt)
            if nxt in seen:
                continue
            nval = val - 2 * half_powers[d[u]] + half_powers[d[w]]
            if prune_by_value and nval < 1:
                continue
            seen.add(nxt)
            if max_states is not None and len(seen) > max_states:
                raise StateLimit(len(seen))
            stack.append((nxt, nval))
    return False


def reachable_vertices(adj, P, max_states=None):
    """Vertices that hold a pebble in some state reachable from P."""
    start = tuple(P)
    n = len(adj)
    covered = {v for v in range(n) if start[v] > 0}
    seen = {start}
    stack = [start]
    while stack:
        state = stack.pop()
        for u in range(n):
            if state[u] >= 2:
                for w in adj[u]:
                    nxt = list(state)
                    nxt[u] -= 2
                    nxt[w] += 1
                    nxt = tuple(nxt)
                    covered.add(w)
                    if nxt not in seen:
                        seen.add(nxt)
                        if max_states is not None and len(seen) > max_states:
                            raise StateLimit(len(seen))
                        stack.append(nxt)
    return covered


def is_solvable(adj, P, max_states=None):
    return len(reachable_vertices(adj, P, max_states)) == len(adj)


def check_minimal_distribution(adj, P, witness_hints=None, prune_by_value=False,
                               max_states=None, certificates=None, hint_only=False):
    """Naive minimality verification of a claimed minimal distribution."""
    n = len(adj)
    report = {"reach_method": {}, "deletions": {}, "ok": True}
    for X in range(n):
        try:
            ok = is_reachable(adj, P, X, prune_by_value=prune_by_value, max_states=max_states)
            report["reach_method"][X] = "search"
        except StateLimit:
            cert = (certificates or {}).get(X)
            if cert is None:
                report["reach_method"][X] = "undecided"
                report["ok"] = False
                continue
            ok = replay_moves(adj, P, cert, X)
            report["reach_method"][X] = "certificate_replay"
        if not ok:
            report["ok"] = False
            report["unreachable_in_P"] = X
            return report
    for v in range(n):
        if P[v] == 0:
            continue
        Q = list(P)
        Q[v] -= 1
        order = list(range(n))
        if witness_hints and v in witness_hints:
            h = witness_hints[v]
            order = [h] if hint_only else [h] + [x for x in order if x != h]
        found = None
        undecided = []
        for X in order:
            try:
                if not is_reachable(adj, Q, X, prune_by_value=prune_by_value, max_states=max_states):
                    found = X
                    break
            except StateLimit:
                undecided.append(X)
        report["deletions"][v] = {"unreachable_target": found, "undecided_targets": undecided}
        if found is None:
            report["ok"] = False
    return report
