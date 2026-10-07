import argparse
import itertools
import json
import os
import random
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from fractions import Fraction
from math import ceil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from pebbling.graphs import make_graph, grid_graph, random_connected_graph, grid_symmetries, apply_perm
from pebbling import solver as S
from pebbling import portfolio as PF
from pebbling.ipsolver import ip_reach
from pebbling.certify import replay
from pebbling.numbers import distributions, count_distributions
from naivecheck import naive
import workers

STATE_CAP = 2_000_000


class CheckFailed(Exception):
    def __init__(self, message, details=None):
        super().__init__(message)
        self.details = details or {}


def _default(o):
    if isinstance(o, Fraction):
        return f"{o.numerator}/{o.denominator}"
    if isinstance(o, (set, frozenset)):
        return sorted(o)
    return str(o)


class Runner:
    def __init__(self, outdir, quick, nworkers):
        self.outdir = outdir
        self.quick = quick
        self.results = []
        self.log = open(outdir / "log.jsonl", "a", encoding="utf-8")
        self.pool = ProcessPoolExecutor(nworkers) if nworkers > 1 else None
        self.started = time.time()

    def record(self, rec):
        rec["logged_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        self.log.write(json.dumps(rec, default=_default) + "\n")
        self.log.flush()
        os.fsync(self.log.fileno())
        print(f"[{rec['status']}] {rec['check']} ({rec.get('seconds')}s) {rec.get('summary', '')}", flush=True)

    def run(self, name, fn):
        t = time.time()
        try:
            out = fn(self) or {}
        except CheckFailed as e:
            rec = {"check": name, "status": "FAIL", "seconds": round(time.time() - t, 2),
                   "message": str(e), "details": e.details}
            self.record(rec)
            self.results.append(rec)
            raise
        except Exception as e:
            rec = {"check": name, "status": "ERROR", "seconds": round(time.time() - t, 2),
                   "message": repr(e), "traceback": traceback.format_exc()}
            self.record(rec)
            self.results.append(rec)
            raise CheckFailed(f"exception in {name}: {e!r}") from e
        rec = {"check": name, "status": "PASS", "seconds": round(time.time() - t, 2)}
        rec.update(out)
        self.record(rec)
        self.results.append(rec)

    def n(self, full, quick):
        return quick if self.quick else full

    def parallel_scan(self, engine, spec, k, mode):
        G = workers.graph(spec)
        if self.pool is None or G.n < 3:
            return workers.scan_chunk((engine, spec, (), k, mode))
        prefixes = [(a, b) for a in range(k + 1) for b in range(k + 1 - a)]
        futs = [self.pool.submit(workers.scan_chunk, (engine, spec, p, k, mode)) for p in prefixes]
        checked = 0
        found = None
        for fut in as_completed(futs):
            c, ex = fut.result()
            checked += c
            if ex is not None:
                found = ex
                for f in futs:
                    f.cancel()
                break
        return checked, found


def random_distribution(rng, n, max_total):
    style = rng.random()
    P = [0] * n
    if style < 0.35:
        for _ in range(rng.randint(0, max_total)):
            P[rng.randrange(n)] += 1
    elif style < 0.65:
        for v in range(n):
            if rng.random() < 0.35:
                P[v] = rng.choice([1, 1, 2, 2, 3, 4])
    elif style < 0.85:
        for _ in range(rng.randint(1, 2)):
            P[rng.randrange(n)] += rng.randint(1, max_total)
    else:
        for v in range(n):
            if rng.random() < 0.6:
                P[v] = 1
        P[rng.randrange(n)] = 2
    return P


def repair_to_solvable(G, P, is_solvable_witness):
    P = list(P)
    while True:
        ok, X = is_solvable_witness(P)
        if ok:
            return P
        P[X] += 1


def bs_witness(G):
    def f(P):
        ok, info, _ = S.solvability(G, P)
        return (True, None) if ok else (False, info)
    return f


def pf_witness(G):
    def f(P):
        ok, info, _ = PF.solvability(G, P)
        return (True, None) if ok else (False, info[0])
    return f


def random_solvable(G, rng):
    P = [2 if rng.random() < 0.45 else (1 if rng.random() < 0.3 else 0) for _ in range(G.n)]
    return repair_to_solvable(G, P, pf_witness(G))


def reduce_to_minimal(G, P, rng, solvable):
    P = list(P)
    order = [v for v in range(G.n) for _ in range(P[v])]
    rng.shuffle(order)
    for v in order:
        P[v] -= 1
        if not solvable(P):
            P[v] += 1
    return P


def all_graph_specs_small():
    specs = [f"path:{n}" for n in range(2, 9)] + [f"cycle:{n}" for n in range(3, 9)]
    specs += [f"complete:{n}" for n in range(2, 7)] + ["petersen"]
    specs += ["grid:2x2", "grid:2x3", "grid:2x4", "grid:2x5", "grid:3x3", "grid:3x4", "grid:4x4"]
    rng = random.Random(20260913)
    for i in range(8):
        n = rng.randint(4, 8)
        specs.append(random_connected_graph(n, rng.uniform(0.3, 0.6), rng).spec())
    return specs


def check_graphs(R):
    pairs = 0
    for m in range(1, 9):
        for n in range(1, 9):
            spec = f"grid:{m}x{n}"
            G = grid_graph(m, n)
            adj = naive.build_adjacency(spec)
            if [sorted(a) for a in adj] != [list(a) for a in G.adj]:
                raise CheckFailed("grid adjacency differs between packages", {"spec": spec})
            for a in range(G.n):
                if naive.distances_from(adj, a) != list(G.dist[a]):
                    raise CheckFailed("grid BFS distances differ between packages", {"spec": spec})
                for b in range(G.n):
                    (i1, j1), (i2, j2) = G.coords[a], G.coords[b]
                    if G.dist[a][b] != abs(i1 - i2) + abs(j1 - j2):
                        raise CheckFailed("grid distance is not taxicab", {"spec": spec, "a": a, "b": b})
                    pairs += 1
            for name, (m2, n2), perm in grid_symmetries(m, n):
                H = grid_graph(m2, n2)
                if sorted(perm) != list(range(G.n)):
                    raise CheckFailed("symmetry not a bijection", {"spec": spec, "sym": name})
                if {tuple(sorted((perm[a], perm[b]))) for a, b in G.edges} != set(H.edges):
                    raise CheckFailed("symmetry not an isomorphism", {"spec": spec, "sym": name})
    others = 0
    for n in range(2, 13):
        for spec, dist in ((f"path:{n}", lambda i, j: abs(i - j)),
                           (f"complete:{n}", lambda i, j: int(i != j))):
            G = make_graph(spec)
            adj = naive.build_adjacency(spec)
            for i in range(n):
                if naive.distances_from(adj, i) != list(G.dist[i]):
                    raise CheckFailed("distances differ between packages", {"spec": spec})
                for j in range(n):
                    if G.dist[i][j] != dist(i, j):
                        raise CheckFailed("distance formula mismatch", {"spec": spec})
                    others += 1
        if n >= 3:
            spec = f"cycle:{n}"
            G = make_graph(spec)
            for i in range(n):
                for j in range(n):
                    if G.dist[i][j] != min(abs(i - j), n - abs(i - j)):
                        raise CheckFailed("cycle distance mismatch", {"spec": spec})
                    others += 1
    return {"summary": f"{pairs} grid distance pairs (1x1..8x8) + {others} path/complete/cycle pairs; "
                       f"8 symmetries per grid are isomorphisms"}


def check_values(R):
    rng = random.Random(1)
    count = 0
    specs = ["grid:5x5", "grid:9x9", "grid:4x7", "path:12", "cycle:9", "petersen", "complete:6"]
    for spec in specs:
        G = make_graph(spec)
        adj = naive.build_adjacency(spec)
        for _ in range(R.n(60, 10)):
            P = [rng.choice([0, 0, 0, 1, 2, 3, 7, 16]) for _ in range(G.n)]
            for X in range(G.n):
                a = S.value(G, P, X)
                b = Fraction(S.potential_scaled(G, P, X), G.scale)
                c = naive.value(adj, P, X)
                d = sum((Fraction(P[y], 2 ** G.dist[X][y]) for y in range(G.n)), Fraction(0))
                if not (a == b == c == d):
                    raise CheckFailed("value forms disagree", {"spec": spec, "P": P, "X": X})
                count += 1
    return {"summary": f"{count} exact potentials agree across 4 computations"}


def check_nongreedy_example(R):
    spec = "grid:2x3"
    G = make_graph(spec)
    adj = naive.build_adjacency(spec)
    P = [0, 0, 2, 1, 1, 1]
    res = {
        "bs": S.Solver(G, P).reach(0),
        "bs_noprune": S.Solver(G, P, potential_prune=False).reach(0),
        "ip": ip_reach(G, P, 0),
        "ip_norestrict": ip_reach(G, P, 0, restrict=False),
    }
    for k, moves in res.items():
        if moves is None or not replay(G.adj, P, moves, 0) or not naive.replay_moves(adj, P, moves, 0):
            raise CheckFailed("non-greedy example not solved", {"engine": k})
    if not naive.is_reachable(adj, P, 0):
        raise CheckFailed("naive fails non-greedy example")
    if naive.is_reachable(adj, P, 0, greedy_only=True):
        raise CheckFailed("greedy-only search unexpectedly solves the example")
    return {"summary": "target (0,0) of grid 2x3 from [0,0,2,1,1,1] reachable by all engines; "
                       "greedy-only search says unreachable",
            "certificate_bs": res["bs"]}


def check_engine_agreement(R):
    rng = random.Random(42)
    specs = all_graph_specs_small()
    instances = skipped = targets = 0
    greedy_differs = 0
    minimal_checked = {"minimal": 0, "not_minimal": 0, "unsolvable": 0}
    for spec in specs:
        G = make_graph(spec)
        adj = naive.build_adjacency(spec)
        max_total = 12 if G.n <= 9 else 10
        for trial in range(R.n(120, 12)):
            P = random_distribution(rng, G.n, max_total)
            try:
                want = frozenset(naive.reachable_vertices(adj, P, max_states=STATE_CAP))
            except naive.StateLimit:
                skipped += 1
                continue
            instances += 1
            engines = {
                "bs": S.Solver(G, P),
                "bs_list_potentials": S.Solver(G, P, potential_impl="list"),
                "bs_noprune": S.Solver(G, P, potential_prune=False),
                "portfolio_tiny_budget": PF.Oracle(G, P, node_limit=3),
            }
            got = {k: set() for k in list(engines) + ["ip", "ip_norestrict"]}
            for X in range(G.n):
                targets += 1
                for k, eng in engines.items():
                    moves = eng.reach(X)
                    if isinstance(eng, PF.Oracle):
                        moves = moves[0]
                    if moves is not None:
                        if not replay(G.adj, P, moves, X) or not naive.replay_moves(adj, P, moves, X):
                            raise CheckFailed("certificate failed replay", {"spec": spec, "P": P, "X": X, "engine": k})
                        got[k].add(X)
                for k, restrict in (("ip", True), ("ip_norestrict", False)):
                    moves = ip_reach(G, P, X, restrict=restrict)
                    if moves is not None:
                        if not naive.replay_moves(adj, P, moves, X):
                            raise CheckFailed("IP certificate failed naive replay", {"spec": spec, "P": P, "X": X})
                        got[k].add(X)
            for k, s in got.items():
                if frozenset(s) != want:
                    raise CheckFailed("ENGINE DISAGREEMENT with naive reachable set",
                                      {"spec": spec, "P": P, "engine": k, "engine_set": sorted(s),
                                       "naive_set": sorted(want)})
            greedy = {X for X in range(G.n) if naive.is_reachable(adj, P, X, greedy_only=True)}
            if greedy != want:
                greedy_differs += 1
            if G.n <= 12:
                cands = [P]
                if want and len(want) == G.n:
                    Pm = reduce_to_minimal(G, P, rng, lambda Q: naive.is_solvable(adj, Q, STATE_CAP))
                    cands.append(Pm)
                for Q in cands:
                    naive_solv = naive.is_solvable(adj, Q, STATE_CAP)
                    if not naive_solv:
                        expect = "unsolvable"
                    else:
                        expect = "minimal"
                        for v in range(G.n):
                            if Q[v]:
                                Q2 = list(Q)
                                Q2[v] -= 1
                                if naive.is_solvable(adj, Q2, STATE_CAP):
                                    expect = "not_minimal"
                                    break
                    for label, res in (("bs", S.minimality(G, Q)),
                                       ("bs_noprune", S.minimality(G, Q, potential_prune=False)),
                                       ("portfolio_tiny_budget", PF.minimality(G, Q, node_limit=3))):
                        if res["status"] != expect:
                            raise CheckFailed("MINIMALITY DISAGREEMENT with naive",
                                              {"spec": spec, "Q": Q, "engine": label,
                                               "engine_status": res["status"], "naive_status": expect})
                    minimal_checked[expect] += 1
    return {"summary": f"{instances} distributions / {targets} targets on {len(specs)} graphs: "
                       f"{', '.join(got)} all equal naive; "
                       f"minimality statuses agree {minimal_checked}; naive state cap skips {skipped}; "
                       f"greedy-only search differed on {greedy_differs} distributions",
            "graphs": specs}


def pi_scan(R, spec, engine, seq_cap=20000):
    G = workers.graph(spec)
    witness_below = tuple([0] * G.n)
    per_k = []
    for k in itertools.count(1):
        total = count_distributions(G.n, k)
        checked, found = 0, None
        for P in itertools.islice(distributions(G.n, k), seq_cap):
            checked += 1
            if not workers.solvable_by(engine, spec, P):
                found = P
                break
        if found is None and total > seq_cap:
            checked, found = R.parallel_scan(engine, spec, k, "find_unsolvable")
        per_k.append([k, checked, total, found])
        if found is None:
            if checked != total:
                raise CheckFailed("enumeration count mismatch", {"spec": spec, "k": k, "checked": checked, "total": total})
            return {"value": k, "all_solvable_checked": checked, "unsolvable_witness_size_value_minus_1": witness_below}
        witness_below = found


def pi_opt_scan(R, spec, engine, seq_cap=20000):
    G = workers.graph(spec)
    prev = None
    for k in itertools.count(1):
        total = count_distributions(G.n, k)
        checked, found = 0, None
        for P in itertools.islice(distributions(G.n, k), seq_cap):
            checked += 1
            if workers.solvable_by(engine, spec, P):
                found = P
                break
        if found is None and total > seq_cap:
            checked, found = R.parallel_scan(engine, spec, k, "find_solvable")
        if found is not None:
            if prev is not None and prev[0] != prev[1]:
                raise CheckFailed("enumeration count mismatch", {"spec": spec, "k": k - 1, "prev": prev})
            return {"value": k, "solvable_witness": found,
                    "all_unsolvable_checked_at_value_minus_1": prev[0] if prev else 0}
        prev = (checked, total)


def _cross_verify_witness(spec, P, expect_solvable, engines):
    G = workers.graph(spec)
    for e in engines:
        if workers.solvable_by(e, spec, P) != expect_solvable:
            raise CheckFailed("ENGINE DISAGREEMENT on witness", {"spec": spec, "P": P, "engine": e,
                                                                 "expected_solvable": expect_solvable})


def known_value_check(R, label, spec, kind, expected, engines, witness_engines):
    out = {}
    for e in engines:
        r = pi_scan(R, spec, e) if kind == "pi" else pi_opt_scan(R, spec, e)
        out[e] = r
    values = {e: r["value"] for e, r in out.items()}
    if len(set(values.values())) != 1:
        raise CheckFailed(f"ENGINE DISAGREEMENT on {label}", {"values": values, "runs": out})
    value = next(iter(values.values()))
    first = out[engines[0]]
    if kind == "pi":
        _cross_verify_witness(spec, first["unsolvable_witness_size_value_minus_1"], False, witness_engines)
    else:
        _cross_verify_witness(spec, first["solvable_witness"], True, witness_engines)
    if value != expected:
        raise CheckFailed(f"DISAGREEMENT WITH PROVIDED VALUE: {label} computed {value}, provided {expected}",
                          {"values": values, "runs": out})
    return {"label": label, "expected": expected, "computed": value, "engines": engines, "runs": out}


def sampled_cross_check(spec, k_values, count, engines, rng):
    G = workers.graph(spec)
    done = 0
    for k in k_values:
        for _ in range(count):
            P = [0] * G.n
            for _ in range(k):
                P[rng.randrange(G.n)] += 1
            if rng.random() < 0.3:
                P = [0] * G.n
                P[rng.randrange(G.n)] = k
            answers = {e: workers.solvable_by(e, spec, tuple(P)) for e in engines}
            if len(set(answers.values())) != 1:
                raise CheckFailed("ENGINE DISAGREEMENT in sampled cross-check", {"spec": spec, "P": P, "answers": answers})
            done += 1
    return done


def check_known_values(R):
    recs = []
    for n in range(2, 7):
        recs.append(known_value_check(R, f"pi(K{n})", f"complete:{n}", "pi", n, ["bs", "ip", "naive"], ["bs", "ip", "naive"]))
    for n in range(2, 7):
        engines = ["bs", "ip", "naive"] if n <= 5 else ["bs"]
        recs.append(known_value_check(R, f"pi(P{n})", f"path:{n}", "pi", 2 ** (n - 1), engines,
                                      ["bs", "bs_noprune", "ip", "ip_norestrict", "naive"]))
    rng = random.Random(6)
    extra = sampled_cross_check("path:6", [30, 31, 32, 33], R.n(500, 30), ["bs", "ip", "naive"], rng)
    recs.append({"label": "pi(P6) sampled cross-engine check", "distributions": extra})
    for n in (4, 5):
        recs.append(known_value_check(R, f"pi(C{n})", f"cycle:{n}", "pi", n, ["bs", "ip", "naive"],
                                      ["bs", "bs_noprune", "ip", "ip_norestrict", "naive"]))
    for n in range(2, 13):
        engines = ["bs", "naive"] + (["ip"] if n <= 8 else [])
        recs.append(known_value_check(R, f"pi_opt(P{n})", f"path:{n}", "pi_opt", ceil(2 * n / 3), engines,
                                      ["bs", "bs_noprune", "ip", "ip_norestrict", "naive"]))
    for n in range(2, 11):
        recs.append(known_value_check(R, f"pi_opt(K{n})", f"complete:{n}", "pi_opt", 2, ["bs", "ip", "naive"],
                                      ["bs", "ip", "naive"]))
    table = {r["label"]: [r.get("expected"), r.get("computed")] for r in recs if "computed" in r}
    return {"summary": f"{len(table)} provided values reproduced by every engine listed", "table": table,
            "records": recs}


def check_extra_values_and_order(R):
    rows = {}
    pi_specs = ["complete:2", "complete:3", "complete:4", "complete:5", "complete:6",
                "path:2", "path:3", "path:4", "path:5", "path:6", "cycle:3", "cycle:4", "cycle:5",
                "cycle:6", "cycle:7", "cycle:8", "grid:2x2", "grid:2x3", "grid:2x4", "grid:3x3", "petersen"]
    for spec in pi_specs:
        rows.setdefault(spec, {})["pi"] = pi_scan(R, spec, "bs")["value"]
    opt_specs = pi_specs + ["cycle:9", "cycle:10", "cycle:11", "cycle:12", "grid:3x4", "grid:4x4"]
    for spec in opt_specs:
        rows.setdefault(spec, {})["pi_opt"] = pi_opt_scan(R, spec, "bs")["value"]
    for spec in ["cycle:6", "cycle:7", "cycle:8", "grid:2x3", "grid:3x3", "petersen"]:
        rows[spec]["pi_opt_naive"] = pi_opt_scan(R, spec, "naive")["value"]
        if rows[spec]["pi_opt_naive"] != rows[spec]["pi_opt"]:
            raise CheckFailed("ENGINE DISAGREEMENT on extra pi_opt", {"spec": spec, "row": rows[spec]})
    violations = {s: r for s, r in rows.items() if "pi" in r and r["pi_opt"] > r["pi"]}
    if violations:
        raise CheckFailed("pi_opt > pi", violations)
    iso = [("complete:3", "cycle:3"), ("cycle:4", "grid:2x2")]
    for a, b in iso:
        if rows[a] .get("pi") != rows[b].get("pi") or rows[a]["pi_opt"] != rows[b]["pi_opt"]:
            raise CheckFailed("isomorphic graphs got different values", {"a": a, "b": b})
    both = sum(1 for r in rows.values() if "pi" in r)
    return {"summary": f"pi_opt <= pi on all {both} graphs with both values; isomorphic pairs agree",
            "computed_values_not_asserted": rows}


def check_monotonicity(R):
    rng = random.Random(9)
    specs_small = ["path:7", "cycle:7", "complete:5", "petersen", "grid:3x3", "grid:3x4", "grid:4x4"]
    specs_large = ["grid:5x5", "grid:6x6", "grid:7x7", "grid:9x9"]
    checks = naive_checks = naive_skips = 0
    for spec in specs_small + specs_large:
        G = make_graph(spec)
        adj = naive.build_adjacency(spec)
        small = spec in specs_small
        for _ in range(R.n(60 if small else 15, 5)):
            naive_usable = small
            if small:
                P = repair_to_solvable(G, random_distribution(rng, G.n, 10), bs_witness(G))
                try:
                    if not naive.is_solvable(adj, P, STATE_CAP):
                        raise CheckFailed("repaired distribution not solvable by naive", {"spec": spec, "P": P})
                except naive.StateLimit:
                    naive_usable = False
                    naive_skips += 1
            else:
                P = random_solvable(G, rng)
            vs = range(G.n) if small else rng.sample(range(G.n), 6)
            for v in vs:
                Q = list(P)
                Q[v] += 1
                ok = S.is_solvable(G, Q) if small else PF.solvability(G, Q)[0]
                if not ok:
                    raise CheckFailed("adding a pebble destroyed solvability", {"spec": spec, "P": P, "v": v})
                if naive_usable:
                    try:
                        if not naive.is_solvable(adj, Q, STATE_CAP):
                            raise CheckFailed("naive: adding a pebble destroyed solvability",
                                              {"spec": spec, "P": P, "v": v})
                        naive_checks += 1
                    except naive.StateLimit:
                        naive_skips += 1
                checks += 1
    return {"summary": f"{checks} (solvable P, P + e_v) pairs stay solvable by the main engines; "
                       f"naive confirmed {naive_checks}; naive state-cap skips {naive_skips}"}


def check_value_rejection(R):
    rng = random.Random(13)
    specs = ["path:8", "cycle:8", "complete:6", "petersen", "grid:3x3", "grid:3x4", "grid:4x4",
             "grid:5x5", "grid:6x6", "grid:9x9"]
    counts = {"cases": 0, "naive": 0, "bs_noprune": 0, "bs_noprune_undecided": 0, "ip_norestrict": 0}
    for spec in specs:
        G = make_graph(spec)
        adj = naive.build_adjacency(spec)
        found = 0
        tries = 0
        while found < R.n(80, 8) and tries < 5000:
            tries += 1
            P = random_distribution(rng, G.n, max(4, G.n // 2))
            vals = [S.value(G, P, X) for X in range(G.n)]
            X = min(range(G.n), key=lambda y: vals[y])
            if vals[X] >= 1:
                continue
            found += 1
            counts["cases"] += 1
            if G.n <= 16:
                if naive.is_reachable(adj, P, X, prune_by_value=False, max_states=STATE_CAP):
                    raise CheckFailed("naive reaches a vertex with v_P < 1", {"spec": spec, "P": P, "X": X})
                counts["naive"] += 1
            try:
                limit = 200000 if G.n <= 16 else 30000
                if S.Solver(G, P, potential_prune=False, node_limit=limit).reach(X) is not None:
                    raise CheckFailed("bs_noprune reaches a vertex with v_P < 1", {"spec": spec, "P": P, "X": X})
                counts["bs_noprune"] += 1
            except S.Undecided:
                counts["bs_noprune_undecided"] += 1
            if ip_reach(G, P, X, restrict=False) is not None:
                raise CheckFailed("ip_norestrict reaches a vertex with v_P < 1", {"spec": spec, "P": P, "X": X})
            counts["ip_norestrict"] += 1
            if S.is_solvable(G, P) or PF.solvability(G, P)[0]:
                raise CheckFailed("solver calls a distribution with v_P(X) < 1 solvable", {"spec": spec, "P": P})
    return {"summary": f"{counts['cases']} distributions with some v_P(X) < 1: unreachable per engines "
                       f"that do not use v_P ({counts})", "counts": counts}


def check_symmetry(R):
    rng = random.Random(17)
    shapes = [(3, 3), (4, 4), (5, 5), (6, 6), (7, 7), (9, 9), (3, 5), (4, 6), (2, 7), (5, 8)]
    checked = 0
    minimal_seen = 0
    for m, n in shapes:
        G = grid_graph(m, n)
        syms = grid_symmetries(m, n)
        hosts = {shape: grid_graph(*shape) for _, shape, _ in syms}
        for trial in range(R.n(12, 2)):
            P = random_distribution(rng, G.n, 14)
            if trial % 2 == 1:
                P = random_solvable(G, rng)
                if G.n <= 25:
                    P = reduce_to_minimal(G, P, rng, lambda Q: PF.solvability(G, Q)[0])
            base = frozenset(X for X in range(G.n) if PF.Oracle(G, P).reach(X)[0] is not None)
            base_vals = [S.value(G, P, X) for X in range(G.n)]
            base_min = PF.minimality(G, P)["status"] if G.n <= 36 else None
            if base_min == "minimal":
                minimal_seen += 1
            for name, shape, perm in syms:
                H = hosts[shape]
                Q = apply_perm(P, perm)
                img = frozenset(perm[x] for x in base)
                got = frozenset(X for X in range(H.n) if PF.Oracle(H, Q).reach(X)[0] is not None)
                got_bs = frozenset(X for X in range(H.n) if S.Solver(H, Q, node_limit=10**6).reach(X) is not None) if G.n <= 36 else got
                if got != img or got_bs != img:
                    raise CheckFailed("reachable set not symmetric", {"shape": (m, n), "sym": name, "P": P})
                for X in range(G.n):
                    if S.value(H, Q, perm[X]) != base_vals[X]:
                        raise CheckFailed("value not symmetric", {"shape": (m, n), "sym": name, "P": P, "X": X})
                if base_min is not None and PF.minimality(H, Q)["status"] != base_min:
                    raise CheckFailed("minimality status not symmetric", {"shape": (m, n), "sym": name, "P": P})
                checked += 1
    return {"summary": f"{checked} (distribution, symmetry) pairs: reachable sets, exact values and "
                       f"minimality status commute with all 8 dihedral maps ({minimal_seen} minimal bases)"}


CHECKS = [
    ("graphs_distances_symmetries", check_graphs),
    ("exact_values", check_values),
    ("non_greedy_regression", check_nongreedy_example),
    ("engine_agreement_vs_naive", check_engine_agreement),
    ("provided_values", check_known_values),
    ("extra_values_and_pi_opt_le_pi", check_extra_values_and_order),
    ("monotonicity_add_pebble", check_monotonicity),
    ("value_rejection_consistency", check_value_rejection),
    ("dihedral_invariance", check_symmetry),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--only", nargs="*")
    args = ap.parse_args()
    run_id = time.strftime("%Y%m%d-%H%M%S") + ("-quick" if args.quick else "")
    outdir = ROOT / "logs" / "validation" / run_id
    outdir.mkdir(parents=True, exist_ok=True)
    R = Runner(outdir, args.quick, args.workers)
    status = "PASS"
    try:
        for name, fn in CHECKS:
            if args.only and name not in args.only:
                continue
            R.run(name, fn)
    except CheckFailed:
        status = "FAIL"
    finally:
        summary = {"run": run_id, "status": status, "quick": args.quick,
                   "seconds": round(time.time() - R.started, 1),
                   "checks": [{k: r.get(k) for k in ("check", "status", "seconds", "summary", "message")}
                              for r in R.results]}
        (outdir / "summary.json").write_text(json.dumps(summary, indent=2, default=_default), encoding="utf-8")
        if R.pool:
            R.pool.shutdown(cancel_futures=True)
    print("VALIDATION", status, outdir, flush=True)
    sys.exit(0 if status == "PASS" else 1)


if __name__ == "__main__":
    main()
