# pebbling

Exact tools for graph pebbling: reachability, solvability and minimality of pebble distributions, with
move sequences anyone can replay.

## Optimal pebbling

A pebbling move removes two pebbles from a vertex and puts one pebble on a neighbouring vertex. A
distribution of pebbles is solvable if every vertex can be reached, that is, for every vertex some sequence of
moves puts a pebble on it. The optimal pebbling number of a graph is the smallest number of pebbles in a
solvable distribution. Computing it is NP-hard in general, and for grids it is known only up to constant
factors.

## What the code does

`pebbling/solver.py` decides whether a demand can be covered, using a backward search over demands with exact
integer potentials for pruning. The proofs behind the search and the pruning rules are in
`docs/solver_notes.md`. `pebbling/ipsolver.py` answers the same questions a second way, as an integer flow
model solved with OR-Tools CP-SAT.

Every positive answer comes with an explicit move sequence, which `pebbling/certify.py` replays. The
`naivecheck/` package, written separately from the solver, re-checks results with a plain forward search over
pebbling states and its own flow model. `validate.py` compares all engines against brute force on small
graphs, against known pebbling numbers, and against invariants such as symmetry and monotonicity.

## Installation

To use the library:

```bash
pip install pypebbling
```

It is imported as `pebbling` (for example `from pebbling.solver import solvability`) and needs Python 3.12 or
later.

To run the tests, the validation suite or the counterexample check, clone the repository instead:

```bash
git clone https://github.com/hynoph/pebbling
cd pebbling
python -m venv .venv
.venv\Scripts\activate          # Windows; on Linux/macOS: source .venv/bin/activate
pip install -e ".[test]"
```

## Example

Four piles of four pebbles on a 5x5 grid. Check that the distribution is solvable and print the move sequence
that reaches the corner (0, 0):

```python
from pebbling.graphs import grid_graph
from pebbling.solver import solvability
from pebbling.certify import replay

G = grid_graph(5, 5)
P = [0] * 25
for r, c in [(1, 1), (1, 3), (3, 1), (3, 3)]:
    P[r * 5 + c] = 4

solvable, certs, _ = solvability(G, tuple(P))
print("solvable:", solvable)

target = 0  # vertex (0, 0); vertex v is (v // 5, v % 5)
moves = certs[target]
print("moves to (0, 0):", [(divmod(u, 5), divmod(w, 5)) for u, w in moves])
print("replay ok:", replay(G.adj, P, moves, target))
```

A move `((a, b), (c, d))` removes two pebbles from `(a, b)` and adds one to the adjacent `(c, d)`.
`solvability` returns `(True, certificates, solver)` or `(False, unreachable_vertex, solver)`.

## Tests and validation

```bash
python -m pytest -q tests
python validate.py              # writes logs/validation/<run>/
python validate.py --quick      # shorter run
```

validate.py takes about 20 minutes. On Windows, set `PYTHONUTF8=1` if your console is not UTF-8.

## The counterexample

[`docs/counterexample_conj41.pdf`](docs/counterexample_conj41.pdf) (LaTeX source in `docs/counterexample_conj41.tex`) gives a solvable distribution of 57 pebbles
on the 10x10 grid in which the degree-4 vertex (5, 5) has value $v(5,5)=379/256<3/2$. This contradicts
Conjecture 4.1 of Petr, Portier and Stolarczyk (Discrete Mathematics 346 (2023) 113212) as printed, with $v$
computed from $P$ itself. It says nothing about the version for the hemmed distribution $P'$, which is what
their lower-bound method uses. [`docs/counterexample_conj41.md`](docs/counterexample_conj41.md) adds the arXiv
wording of the conjecture, the value broken down by distance, and a ten-line checker.

I verified the value v(5,5) = 379/256 and the move certificates by hand; they are also replayed by
verify_counterexample.py and by an independent checker (naivecheck). The counterexample was found by a
randomized local search over solvable distributions; the search code is not included in this repository.

```bash
python verify_counterexample.py
```

## How this was built

Results are cross-checked by the independent checker in `naivecheck/` and were verified by hand. Writeups were
primarily done using AI tools with revision.

## License

MIT; see `LICENSE`.
