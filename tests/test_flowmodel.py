import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from naivecheck import naive, flowmodel
from pebbling.graphs import make_graph
from pebbling.solver import Solver


def test_flowmodel_matches_naive_and_backward_search():
    rng = random.Random(2024)
    specs = ["path:7", "cycle:6", "cycle:7", "complete:5", "petersen", "grid:2x3", "grid:3x3", "grid:3x4", "grid:4x4"]
    compared = 0
    for spec in specs:
        adj = naive.build_adjacency(spec)
        G = make_graph(spec)
        for _ in range(40):
            P = [0] * len(adj)
            style = rng.random()
            if style < 0.5:
                for _ in range(rng.randint(0, 10)):
                    P[rng.randrange(len(adj))] += 1
            else:
                for v in range(len(adj)):
                    if rng.random() < 0.4:
                        P[v] = rng.choice([1, 1, 2, 3, 4])
            for X in range(len(adj)):
                a = flowmodel.target_feasible(adj, P, X)
                b = naive.is_reachable(adj, P, X, max_states=2_000_000)
                c = Solver(G, P).reach(X) is not None
                assert a == b == c, (spec, P, X, a, b, c)
                compared += 1
    assert compared > 2000


def test_flowmodel_non_greedy_example():
    adj = naive.build_adjacency("grid:2x3")
    assert flowmodel.target_feasible(adj, [0, 0, 2, 1, 1, 1], 0) is True
    assert flowmodel.target_feasible(adj, [0, 0, 2, 1, 1, 0], 0) is False
