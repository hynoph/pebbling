"""Second exact reachability engine: integer feasibility solved with OR-Tools CP-SAT."""
from ortools.sat.python import cp_model

from .certify import replay


class IPUndecided(Exception):
    pass


def firing_bounds(G, P):
    W = G.weight
    scale = G.scale
    n = G.n
    support = [y for y in range(n) if P[y]]
    out = []
    for u in range(n):
        phi = sum(P[y] * W[u][y] for y in support)
        num = 2 * phi - scale
        out.append(num // (3 * scale) if num >= 3 * scale else 0)
    return out


def ip_cover(G, P, D, restrict=True, time_limit=None, cuts=(), params=None):
    """Move sequence covering demand D (dict), None if not coverable."""
    n = G.n
    if all(P[v] >= d for v, d in D.items()):
        return ()
    total = sum(P)
    if restrict:
        bound = firing_bounds(G, P)
    else:
        bound = [total // 2] * n
    model = cp_model.CpModel()
    f = {}
    for u in range(n):
        if bound[u] == 0:
            continue
        for w in G.adj[u]:
            if restrict and D.get(w, 0) == 0 and bound[w] == 0:
                continue
            f[(u, w)] = model.NewIntVar(0, bound[u], f"f_{u}_{w}")
    inflow = [[] for _ in range(n)]
    outflow = [[] for _ in range(n)]
    for (u, w), var in f.items():
        outflow[u].append(var)
        inflow[w].append(var)
    for v in range(n):
        need = D.get(v, 0)
        if not inflow[v] and not outflow[v]:
            if P[v] < need:
                return None
            continue
        model.Add(P[v] + sum(inflow[v]) - 2 * sum(outflow[v]) >= need)
    if f and "moves" in cuts:
        model.Add(sum(f.values()) <= total - sum(D.values()))
    if f and "potential" in cuts and len(D) == 1:
        ((X, need),) = D.items()
        wX = G.weight[X]
        phiX = sum(P[y] * wX[y] for y in range(n) if P[y])
        model.Add(sum(var * (2 * wX[u] - wX[w]) for (u, w), var in f.items()) <= phiX - need * wX[X])
    if "two_cycle" in cuts:
        for (u, w), var in f.items():
            if u < w and (w, u) in f:
                b = model.NewBoolVar(f"dir_{u}_{w}")
                model.Add(var == 0).OnlyEnforceIf(b)
                model.Add(f[(w, u)] == 0).OnlyEnforceIf(b.Not())
    solver = cp_model.CpSolver()
    solver.parameters.num_workers = 1
    if time_limit is not None:
        solver.parameters.max_time_in_seconds = time_limit
    if params:
        for name, val in params.items():
            setattr(solver.parameters, name, val)
    status = solver.Solve(model)
    if status == cp_model.INFEASIBLE:
        return None
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise IPUndecided(solver.StatusName(status))
    F = {a: solver.Value(var) for a, var in f.items() if solver.Value(var) > 0}
    moves = flow_to_moves(n, F)
    Q = list(P)
    for u, w in moves:
        if Q[u] < 2 or w not in G.adj[u]:
            raise AssertionError("IP certificate failed to replay")
        Q[u] -= 2
        Q[w] += 1
    if any(Q[v] < d for v, d in D.items()):
        raise AssertionError("IP certificate does not cover the demand")
    return tuple(moves)


def ip_reach(G, P, X, restrict=True, time_limit=None, cuts=(), params=None):
    moves = ip_cover(G, P, {X: 1}, restrict=restrict, time_limit=time_limit, cuts=cuts, params=params)
    if moves is not None and not replay(G.adj, P, moves, X):
        raise AssertionError("IP certificate failed to replay")
    return moves


def flow_to_moves(n, F):
    """Cancel directed cycles in a balanced multiset, then list moves in topological order."""
    F = dict(F)
    while True:
        cycle = _find_cycle(n, F)
        if cycle is None:
            break
        c = min(F[a] for a in cycle)
        for a in cycle:
            F[a] -= c
            if F[a] == 0:
                del F[a]
    indeg = [0] * n
    succ = [[] for _ in range(n)]
    for (u, w) in F:
        succ[u].append(w)
        indeg[w] += 1
    order = [v for v in range(n) if indeg[v] == 0]
    i = 0
    while i < len(order):
        v = order[i]
        i += 1
        for w in succ[v]:
            indeg[w] -= 1
            if indeg[w] == 0:
                order.append(w)
    if len(order) != n:
        raise AssertionError("cycle cancellation left a cycle")
    moves = []
    for v in order:
        for w in sorted(succ[v]):
            moves.extend([(v, w)] * F[(v, w)])
    return moves


def _find_cycle(n, F):
    succ = [[] for _ in range(n)]
    for (u, w) in F:
        succ[u].append(w)
    color = [0] * n  # 0 new, 1 on stack, 2 done
    parent = [-1] * n
    for s in range(n):
        if color[s]:
            continue
        stack = [(s, 0)]
        color[s] = 1
        while stack:
            v, i = stack[-1]
            if i < len(succ[v]):
                stack[-1] = (v, i + 1)
                w = succ[v][i]
                if color[w] == 0:
                    color[w] = 1
                    parent[w] = v
                    stack.append((w, 0))
                elif color[w] == 1:
                    cyc = [(v, w)]
                    x = v
                    while x != w:
                        cyc.append((parent[x], x))
                        x = parent[x]
                    return cyc
            else:
                color[v] = 2
                stack.pop()
    return None
