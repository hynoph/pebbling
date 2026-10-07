"""Decision procedure for large instances: backward search under a node budget, then CP-SAT."""
from .certify import replay
from .ipsolver import ip_reach
from .solver import Solver, Undecided


class Oracle:
    def __init__(self, G, P, node_limit=20000, inherited_fail=(), ip_time_limit=None):
        self.G = G
        self.P = tuple(P)
        self.bs = Solver(G, self.P, inherited_fail=inherited_fail, node_limit=node_limit)
        self.phiP = self.bs.phiP
        self.ip_time_limit = ip_time_limit
        self.engine_counts = {"bs": 0, "ip": 0}

    def reach(self, X):
        """(moves or None, engine)."""
        try:
            moves = self.bs.reach(X)
            engine = "bs"
        except Undecided:
            moves = ip_reach(self.G, self.P, X, time_limit=self.ip_time_limit)
            engine = "ip"
        self.engine_counts[engine] += 1
        if moves is not None and not replay(self.G.adj, self.P, moves, X):
            raise AssertionError(f"certificate replay failed ({engine})")
        return moves, engine


def solvability(G, P, parent_certs=None, inherited_fail=(), node_limit=20000, priority=None,
                collect=None, ip_time_limit=None):
    """(True, certs, oracle) or (False, (X, engine), oracle)."""
    o = Oracle(G, P, node_limit=node_limit, inherited_fail=inherited_fail, ip_time_limit=ip_time_limit)
    certs = {}
    pending = []
    for X in range(G.n):
        c = parent_certs.get(X) if parent_certs else None
        if c is not None and replay(G.adj, o.P, c, X):
            certs[X] = c
        else:
            pending.append(X)
    if collect is not None:
        collect.update(certs)
    if priority is None:
        pending.sort(key=lambda X: o.phiP[X])
    else:
        pending.sort(key=lambda X: (priority(X), o.phiP[X]))
    for X in pending:
        moves, engine = o.reach(X)
        if moves is None:
            return False, (X, engine), o
        certs[X] = moves
        if collect is not None:
            collect[X] = moves
    return True, certs, o


def minimality(G, P, node_limit=20000, certs=None, fail_layers=(), ip_time_limit=None):
    """Same contract as solver.minimality; witnesses map v -> (unreachable X, engine)."""
    ok, info, o = solvability(G, P, parent_certs=certs, inherited_fail=fail_layers,
                              node_limit=node_limit, ip_time_limit=ip_time_limit)
    if not ok:
        return {"status": "unsolvable", "unreachable": info[0], "engine": info[1]}
    certs = info
    layers = (o.bs.fail,) + tuple(fail_layers)
    witnesses = {}
    for v in range(G.n):
        if P[v] == 0:
            continue
        P2 = list(P)
        P2[v] -= 1
        dv = G.dist[v]
        ok2, info2, _ = solvability(G, P2, parent_certs=certs, inherited_fail=layers,
                                    node_limit=node_limit, priority=lambda X: dv[X],
                                    ip_time_limit=ip_time_limit)
        if ok2:
            return {"status": "not_minimal", "removable": v, "certs": certs}
        witnesses[v] = info2
    return {"status": "minimal", "certs": certs, "witnesses": witnesses}
