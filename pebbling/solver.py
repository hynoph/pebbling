"""Exact pebbling reachability, solvability and minimality; proofs in docs/solver_notes.md."""
import sys
from array import array
from fractions import Fraction
from operator import gt

from .certify import replay

sys.setrecursionlimit(max(sys.getrecursionlimit(), 50000))

FAIL_CACHE_CAP = 600_000   # clearing a memo only costs time; it never changes an answer
SUCC_CACHE_CAP = 100_000


class Undecided(Exception):
    """The node budget ran out; the answer is unknown."""


def value(G, P, X):
    """v_P(X) as an exact Fraction, summed term by term from the definition."""
    total = Fraction(0)
    dX = G.dist[X]
    for y, c in enumerate(P):
        if c:
            total += Fraction(c, 1 << dX[y])
    return total


def potential_scaled(G, P, X):
    """v_P(X) * 2**diam as an exact integer."""
    w = G.weight[X]
    return sum(c * w[y] for y, c in enumerate(P) if c)


def _packed_tables(G, F):
    cache = G.__dict__.setdefault("_packed_cache", {})
    t = cache.get(F)
    if t is None:
        n = G.n
        W = G.weight
        packW = tuple(sum(W[v][y] << (F * y) for y in range(n)) for v in range(n))
        packW2 = tuple(2 * p for p in packW)
        H = sum(1 << (F * y + F - 1) for y in range(n))
        t = (packW, packW2, H, (1 << F) - 1)
        cache[F] = t
    return t


class Solver:
    """Reachability oracle for one fixed distribution P (memo shared across targets)."""

    def __init__(self, G, P, potential_prune=True, inherited_fail=(), node_limit=None,
                 potential_impl="packed"):
        P = tuple(P)
        if len(P) != G.n:
            raise ValueError("distribution length does not match graph")
        for c in P:
            if not isinstance(c, int) or c < 0:
                raise ValueError(f"bad pebble count {c!r}")
        if potential_impl not in ("packed", "list"):
            raise ValueError(potential_impl)
        self.G = G
        self.P = P
        self.total = sum(P)
        self.potential_prune = potential_prune
        self.inherited_fail = tuple(inherited_fail)
        self.node_limit = node_limit
        self.fail = set()
        self.succ = {}
        self.nodes = 0
        self.total_nodes = 0
        self._adj = G.adj
        self._W = G.weight
        self._W2 = G.weight2
        W = G.weight
        support = [y for y, c in enumerate(P) if c]
        self.phiP = [sum(P[y] * W[x][y] for y in support) for x in range(G.n)]
        self._packed = potential_prune and potential_impl == "packed"
        if self._packed:
            F = ((self.total + 2) * G.scale).bit_length() + 2
            packW, packW2, H, mask = _packed_tables(G, F)
            self._F = F
            self._mask = mask
            self._pW = packW
            self._pW2 = packW2
            self._H = H
            self._PH = sum(P[y] * packW[y] for y in support) + H

    def reach(self, X):
        """A move sequence ((from, to), ...) that puts a pebble on X, or None if X is unreachable."""
        self.nodes = 0
        if self.P[X] >= 1:
            return ()
        if self._packed:
            phiD = self._pW[X]
            if (self._PH - phiD) & self._H != self._H:
                return None
        elif self.potential_prune:
            phiD = list(self._W[X])
            if any(map(gt, phiD, self.phiP)):
                return None
        else:
            phiD = None
        try:
            return self._cover({X: 1}, 1, phiD, array("I", (X, 1)).tobytes())
        finally:
            self.total_nodes += self.nodes

    def _add_fail(self, key):
        if len(self.fail) >= FAIL_CACHE_CAP:
            self.fail.clear()
        self.fail.add(key)

    def _cover(self, D, size, phiD, key):
        P = self.P
        deficits = []
        deficit_total = 0
        for v, d in D.items():
            e = d - P[v]
            if e > 0:
                deficits.append(v)
                deficit_total += e
        if not deficits:
            return ()
        if size + deficit_total > self.total:
            return None
        cached = self.succ.get(key)
        if cached is not None:
            return cached
        if key in self.fail:
            return None
        for layer in self.inherited_fail:
            if key in layer:
                return None
        self.nodes += 1
        if self.node_limit is not None and self.nodes > self.node_limit:
            raise Undecided(f"node limit {self.node_limit} exceeded")

        total = self.total
        adj = self._adj
        prune = self.potential_prune
        packed = self._packed
        phiP = self.phiP
        if packed:
            PH = self._PH
            H = self._H
            pW = self._pW
            pW2 = self._pW2
        else:
            W = self._W
            W2 = self._W2

        best_v = -1
        best_kids = None
        for v in deficits:
            kids = []
            if packed:
                pWv = pW[v]
            elif prune:
                Wv = W[v]
            for u in adj[v]:
                du = D.get(u, 0)
                pu = P[u]
                grow = (du + 2 - pu if du + 2 > pu else 0) - (du - pu if du > pu else 0)
                # child has size+1 and deficit (deficit_total - 1 + grow)
                if size + deficit_total + grow > total:
                    continue
                if packed:
                    phi2 = phiD + pW2[u] - pWv
                    if (PH - phi2) & H != H:
                        continue
                elif prune:
                    phi2 = [a + b - c for a, b, c in zip(phiD, W2[u], Wv)]
                    if any(map(gt, phi2, phiP)):
                        continue
                else:
                    phi2 = None
                kids.append((u, phi2))
            if not kids:
                self._add_fail(key)
                return None
            if best_kids is None or len(kids) < len(best_kids):
                best_v, best_kids = v, kids

        v = best_v
        kids = best_kids
        if len(kids) > 1:
            if packed:
                F = self._F
                mask = self._mask
                kids.sort(key=lambda t: (D.get(t[0], 0) - P[t[0]], ((t[1] >> (F * t[0])) & mask) - phiP[t[0]]))
            elif prune:
                kids.sort(key=lambda t: (D.get(t[0], 0) - P[t[0]], t[1][t[0]] - phiP[t[0]]))
            else:
                kids.sort(key=lambda t: (D.get(t[0], 0) - P[t[0]], -phiP[t[0]]))
        dv = D[v]
        for u, phi2 in kids:
            D2 = dict(D)
            if dv == 1:
                del D2[v]
            else:
                D2[v] = dv - 1
            D2[u] = D2.get(u, 0) + 2
            key2 = array("I", [x for item in sorted(D2.items()) for x in item]).tobytes()
            res = self._cover(D2, size + 1, phi2, key2)
            if res is not None:
                res = res + ((u, v),)
                if len(self.succ) >= SUCC_CACHE_CAP:
                    self.succ.clear()
                self.succ[key] = res
                return res
        self._add_fail(key)
        return None


def solvability(G, P, parent_certs=None, inherited_fail=(), potential_prune=True, node_limit=None,
                potential_impl="packed"):
    """Decide whether every vertex is reachable from P."""
    s = Solver(G, P, potential_prune=potential_prune, inherited_fail=inherited_fail,
               node_limit=node_limit, potential_impl=potential_impl)
    certs = {}
    pending = []
    for X in range(G.n):
        c = parent_certs.get(X) if parent_certs else None
        if c is not None and replay(G.adj, s.P, c, X):
            certs[X] = c
        else:
            pending.append(X)
    pending.sort(key=lambda X: s.phiP[X])
    for X in pending:
        c = s.reach(X)
        if c is None:
            return False, X, s
        certs[X] = c
    return True, certs, s


def is_solvable(G, P, **kw):
    return solvability(G, P, **kw)[0]


def reachable_set(G, P, **kw):
    s = Solver(G, P, **kw)
    return frozenset(X for X in range(G.n) if s.reach(X) is not None)


def minimality(G, P, potential_prune=True, node_limit=None, certs=None, fail_layers=(),
               potential_impl="packed"):
    """Classify P as 'unsolvable', 'not_minimal' or 'minimal'."""
    ok, info, s = solvability(G, P, parent_certs=certs, inherited_fail=fail_layers,
                              potential_prune=potential_prune, node_limit=node_limit,
                              potential_impl=potential_impl)
    if not ok:
        return {"status": "unsolvable", "unreachable": info}
    certs = info
    layers = (s.fail,) + tuple(fail_layers)
    witnesses = {}
    for v in range(G.n):
        if P[v] == 0:
            continue
        P2 = list(P)
        P2[v] -= 1
        ok2, info2, _ = solvability(G, P2, parent_certs=certs, inherited_fail=layers,
                                    potential_prune=potential_prune, node_limit=node_limit,
                                    potential_impl=potential_impl)
        if ok2:
            return {"status": "not_minimal", "removable": v, "certs": certs}
        witnesses[v] = info2
    return {"status": "minimal", "certs": certs, "witnesses": witnesses}
