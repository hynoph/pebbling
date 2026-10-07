import random
import sys
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pebbling.graphs import (grid_graph, path_graph, cycle_graph, complete_graph, petersen_graph,
                             grid_symmetries, apply_perm, make_graph)
from pebbling.solver import Solver, value, potential_scaled, reachable_set, minimality, is_solvable
from pebbling.certify import replay
from pebbling.numbers import distributions, count_distributions
from naivecheck import naive


def test_grid_distance_is_taxicab():
    for m, n in [(1, 1), (1, 5), (3, 4), (5, 5), (4, 7)]:
        G = grid_graph(m, n)
        for a in range(G.n):
            for b in range(G.n):
                (i1, j1), (i2, j2) = G.coords[a], G.coords[b]
                assert G.dist[a][b] == abs(i1 - i2) + abs(j1 - j2)


def test_naive_adjacency_matches_main():
    for spec in ["grid:3x4", "grid:5x5", "path:7", "cycle:6", "complete:5", "petersen"]:
        G = make_graph(spec)
        adj = naive.build_adjacency(spec)
        assert [sorted(a) for a in adj] == [list(a) for a in G.adj]


def test_symmetries_are_isomorphisms():
    for m, n in [(3, 3), (4, 4), (3, 5), (2, 6)]:
        G = grid_graph(m, n)
        for name, (m2, n2), perm in grid_symmetries(m, n):
            H = grid_graph(m2, n2)
            assert sorted(perm) == list(range(G.n)), name
            img = {tuple(sorted((perm[a], perm[b]))) for a, b in G.edges}
            assert img == set(H.edges), name


def test_value_exact_forms_agree():
    rng = random.Random(1)
    for spec in ["grid:5x5", "path:9", "cycle:7", "petersen"]:
        G = make_graph(spec)
        adj = naive.build_adjacency(spec)
        for _ in range(50):
            P = [rng.choice([0, 0, 0, 1, 2, 3, 5]) for _ in range(G.n)]
            for X in range(G.n):
                v1 = value(G, P, X)
                assert v1 == Fraction(potential_scaled(G, P, X), G.scale)
                assert v1 == naive.value(adj, P, X)


def test_non_greedy_move_required():
    spec = "grid:2x3"
    G = make_graph(spec)
    adj = naive.build_adjacency(spec)
    P = [0, 0, 2, 1, 1, 1]
    cert = Solver(G, P).reach(0)
    assert cert is not None
    assert replay(G.adj, P, cert, 0)
    assert naive.replay_moves(adj, P, cert, 0)
    assert Solver(G, P, potential_prune=False).reach(0) is not None
    assert naive.is_reachable(adj, P, 0)
    assert not naive.is_reachable(adj, P, 0, greedy_only=True)


def test_tiny_known_cases():
    G = path_graph(3)
    assert is_solvable(G, [0, 2, 0])
    assert not is_solvable(G, [1, 0, 1])
    assert not is_solvable(G, [3, 0, 0])
    assert is_solvable(G, [4, 0, 0])
    assert minimality(G, [4, 0, 0])["status"] == "minimal"
    assert minimality(G, [5, 0, 0])["status"] == "not_minimal"


def test_distributions_enumerator():
    for n in range(1, 6):
        for k in range(0, 7):
            ds = list(distributions(n, k))
            assert len(ds) == count_distributions(n, k)
            assert len(set(ds)) == len(ds)
            assert all(len(d) == n and sum(d) == k and min(d) >= 0 for d in ds)


def test_packed_potential_matches_list_implementation():
    rng = random.Random(99)
    specs = ["grid:3x3", "grid:4x5", "grid:6x6", "grid:7x7", "path:9", "cycle:8", "petersen", "complete:6"]
    compared = 0
    for spec in specs:
        G = make_graph(spec)
        for _ in range(40):
            dens = rng.uniform(0.1, 0.6)
            P = [rng.choice([1, 1, 2, 2, 3, 4, 8]) if rng.random() < dens else 0 for _ in range(G.n)]
            a = Solver(G, P, potential_impl="packed", node_limit=20000)
            b = Solver(G, P, potential_impl="list", node_limit=20000)
            for X in range(G.n):
                ra = rb = "undecided"
                try:
                    ra = a.reach(X)
                except Exception as e:
                    ra = type(e).__name__
                try:
                    rb = b.reach(X)
                except Exception as e:
                    rb = type(e).__name__
                assert ra == rb, (spec, P, X)
                assert a.nodes == b.nodes, (spec, P, X, a.nodes, b.nodes)
                compared += 1
    assert compared > 1000


def test_main_matches_naive_quick():
    rng = random.Random(7)
    specs = ["path:6", "cycle:5", "cycle:6", "complete:4", "grid:2x3", "grid:3x3", "petersen"]
    for spec in specs:
        G = make_graph(spec)
        adj = naive.build_adjacency(spec)
        for _ in range(60):
            T = rng.randint(0, 9)
            P = [0] * G.n
            for _ in range(T):
                P[rng.randrange(G.n)] += 1
            got = reachable_set(G, P)
            got_np = reachable_set(G, P, potential_prune=False)
            want = frozenset(naive.reachable_vertices(adj, P))
            assert got == want, (spec, P, got, want)
            assert got_np == want, (spec, P)
