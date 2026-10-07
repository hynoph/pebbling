"""Independent flow-model check of unreachability, for instances too large for naive search."""
from ortools.sat.python import cp_model


def target_feasible(adj, P, X, time_limit=None):
    n = len(adj)
    total = sum(P)
    model = cp_model.CpModel()
    F = {}
    for u in range(n):
        for w in adj[u]:
            F[(u, w)] = model.NewIntVar(0, total, f"F{u}_{w}")
    for v in range(n):
        incoming = [F[(u, v)] for u in adj[v]]
        outgoing = [F[(v, w)] for w in adj[v]]
        model.Add(P[v] + sum(incoming) - 2 * sum(outgoing) >= (1 if v == X else 0))
    solver = cp_model.CpSolver()
    solver.parameters.num_workers = 1
    if time_limit is not None:
        solver.parameters.max_time_in_seconds = time_limit
    status = solver.Solve(model)
    if status == cp_model.INFEASIBLE:
        return False
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return True
    return None
