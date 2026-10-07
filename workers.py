from functools import lru_cache

from pebbling.graphs import make_graph
from pebbling import solver as S
from pebbling import portfolio as PF
from pebbling.ipsolver import ip_reach
from pebbling.numbers import distributions
from naivecheck import naive


@lru_cache(maxsize=None)
def graph(spec):
    return make_graph(spec)


@lru_cache(maxsize=None)
def nadj(spec):
    return naive.build_adjacency(spec)


def solvable_by(engine, spec, P):
    G = graph(spec)
    if engine == "bs":
        return S.is_solvable(G, P)
    if engine == "bs_noprune":
        return S.is_solvable(G, P, potential_prune=False)
    if engine == "portfolio":
        return PF.solvability(G, P)[0]
    if engine == "ip":
        return all(ip_reach(G, P, X) is not None for X in range(G.n))
    if engine == "ip_norestrict":
        return all(ip_reach(G, P, X, restrict=False) is not None for X in range(G.n))
    if engine == "naive":
        return naive.is_solvable(nadj(spec), P)
    raise ValueError(engine)


def scan_chunk(args):
    engine, spec, prefix, k, mode = args
    G = graph(spec)
    rest_n = G.n - len(prefix)
    rest_k = k - sum(prefix)
    checked = 0
    for tail in distributions(rest_n, rest_k):
        P = tuple(prefix) + tail
        ok = solvable_by(engine, spec, P)
        checked += 1
        if mode == "find_unsolvable" and not ok:
            return checked, P
        if mode == "find_solvable" and ok:
            return checked, P
    return checked, None
