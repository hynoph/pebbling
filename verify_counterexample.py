import json
import sys
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from naivecheck import naive  # noqa: E402
from pebbling.graphs import grid_graph  # noqa: E402
from pebbling.solver import solvability  # noqa: E402


def check(P, moves, target):
    Q = dict(P)
    for (a, b), (c, d) in moves:
        if abs(a - c) + abs(b - d) != 1 or Q.get((a, b), 0) < 2:
            return False
        Q[(a, b)] -= 2
        Q[(c, d)] = Q.get((c, d), 0) + 1
    return Q.get(target, 0) >= 1


def main():
    data = json.loads((ROOT / "data" / "counterexample_10x10.json").read_text(encoding="utf-8"))
    m, n = data["grid"]
    P = {(r, c): k for r, c, k in data["distribution"]}
    x = tuple(data["witness"])
    ok = True

    adj = naive.build_adjacency(f"grid:{m}x{n}")
    Pl = [P.get((v // n, v % n), 0) for v in range(m * n)]
    bad = []
    for r in range(m):
        for c in range(n):
            mv = [((a, b), (cc, d)) for a, b, cc, d in data["certificates"][f"{r},{c}"]]
            mv_idx = [(a * n + b, cc * n + d) for (a, b), (cc, d) in mv]
            if not (check(P, mv, (r, c)) and naive.replay_moves(adj, Pl, mv_idx, r * n + c)):
                bad.append((r, c))
    print(f"1. stored certificates: {m * n - len(bad)}/{m * n} vertices verified by replay")
    ok &= not bad

    v = sum(Fraction(k, 2 ** (abs(r - x[0]) + abs(c - x[1]))) for (r, c), k in P.items())
    deg = sum(1 for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)) if 0 <= x[0] + dr < m and 0 <= x[1] + dc < n)
    print(f"2. |P| = {sum(P.values())}, vertex {x} has degree {deg} and v_P = {v} = {float(v):.6f} "
          f"({'<' if v < Fraction(3, 2) else '>='} 3/2)")
    ok &= deg == 4 and v < Fraction(3, 2) and str(v) == data["v_P_witness"]

    G = grid_graph(m, n)
    solvable, certs, _ = solvability(G, tuple(Pl))
    replayed = solvable and all(naive.replay_moves(adj, Pl, certs[t], t) for t in range(m * n))
    print(f"3. fresh exact search: solvable = {solvable}; all {m * n} new certificates replayed by naivecheck: {replayed}")
    ok &= bool(replayed)

    print("PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
