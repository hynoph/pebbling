# Why the main solver is exact

Notation: `P` a distribution, `D` a demand (vertex -> non-negative int), `e_v` the unit
vector at `v`. `D` is *coverable* if some legal move sequence turns `P` into `Q >= D`.
A vertex `X` is reachable iff `e_X` is coverable.

A *move multiset* `F` assigns a count `F(u->w)` to each ordered edge. Write
`in(v) = sum_u F(u->v)`, `out(v) = sum_w F(v->w)`. `F` is *balanced for D* if
`P(v) + in(v) - 2 out(v) >= D(v)` for every `v`.

## Lemma 1 (acyclic balanced multisets are executable)
If `F` is balanced for `D` and its support digraph is acyclic, the moves can be executed
from `P` and the result is `>= D`.

Proof. Order vertices topologically. Process them in order; at `v`, perform all
`out(v)` moves leaving `v`. Every move into `v` comes from an earlier vertex, so `v`
currently holds `P(v) + in(v) >= 2 out(v) + D(v) >= 2 out(v)` pebbles, enough for all
its moves. The final distribution is `P + in - 2 out >= D`.

## Lemma 2 (cycles can be removed)
If a move sequence covers `D`, there is an acyclic multiset balanced for `D`.

Proof. The sequence's multiset `F` is balanced (its final distribution is `>= D`). If
the support has a directed cycle, delete one copy of each move on it: every vertex on
the cycle loses one incoming and one outgoing move, a net change of `-1 + 2 = +1`, so
balance is kept. `|F|` strictly drops, so this terminates in an acyclic balanced
multiset.

## Theorem (the recursion)
If `P >= D` then `D` is coverable. Otherwise let `v` be **any** vertex with
`D(v) > P(v)`. Then `D` is coverable iff for some neighbour `u` of `v`,
`D' = D + 2 e_u - e_v` is coverable.

(<=) Cover `D'` reaching `Q' >= D'`. Then `Q'(u) >= D(u) + 2 >= 2`, so the move `u->v`
is legal and gives `Q` with `Q(u) >= D(u)`, `Q(v) = Q'(v) + 1 >= D(v)`, other entries
unchanged. So `Q >= D`.

(=>) By Lemma 2 take an acyclic `F` balanced for `D`. Balance at `v` with
`D(v) > P(v)` forces `in(v) >= 1`, so `F` contains some move `u->v`. Remove one copy.
At `u`: `P(u) + in(u) - 2(out(u) - 1) >= D(u) + 2 = D'(u)`. At `v`:
`P(v) + in(v) - 1 - 2 out(v) >= D(v) - 1 = D'(v)`. Other vertices are unchanged. The
smaller multiset is acyclic and balanced for `D'`, so by Lemma 1 `D'` is coverable.

Termination: every step raises `|D|` by one, and a coverable `D` has `|D| <= |P|`.

The (=>) direction holds for every deficit vertex `v` at once. So if any deficit vertex
has no neighbour whose child demand survives the necessary conditions below, `D` is not
coverable. This is pruning rule (c) in `solver.py`.

## Necessary conditions used for pruning
(a) Each unit of deficit `max(0, D(v) - P(v))` needs its own incoming move, and each move
destroys a pebble. So `|D| + total deficit <= |P|`.

(b) For every vertex `y`, `v_Q(y) = sum_x Q(x) 2^-d(x,y)` never increases under a move
`u->w`: the change is `-2*2^-d(u,y) + 2^-d(w,y) <= 0`, since `d(w,y) >= d(u,y) - 1`.
If `Q >= D` then `v_Q(y) >= sum_x D(x) 2^-d(x,y)`. So a coverable `D` has
`sum_x D(x) 2^-d(x,y) <= v_P(y)` for all `y`. With `D = e_X` and `y = X` this is exactly
the `v_P(X) >= 1` rule. It is used only to reject.

(d) If `P' >= P`, any sequence legal from `P` is legal from `P'`. So "not coverable from
`P'`" implies "not coverable from `P`". Failure memos may be inherited downward only.

## Integer flow form (used by `ipsolver.py`)
`D` is coverable iff some integer multiset `F >= 0` is balanced for `D`. No acyclicity
constraint is needed.

(=>) The multiset of any covering sequence is balanced. (<=) Cancel directed cycles as
in Lemma 2. Subtracting `c` copies around a cycle changes each balance on it by
`-c + 2c = +c`. What remains is acyclic and balanced, hence executable by Lemma 1.

Variable restrictions in `ipsolver.py` are valid because the executable acyclic solution
obtained from any covering sequence satisfies them:
- The `k`-th firing of `u` needs 2 pebbles on `u`, so `v(u) >= 2` at that moment. A move
  out of `u` lowers `v(u)` by `3/2`, and no move raises it. So `k <= (2 v_P(u) - 1)/3`.
- A vertex with `v_P(w) < 2` never holds 2 pebbles, so never fires. Deleting a move
  into such a `w` with `D(w) = 0` adds 2 at the source and keeps `w`'s balance
  non-negative, since that move had delivered at least one pebble.

## Why moves away from the target cannot be excluded
Grid with 2 rows and 3 columns. Vertex `(r,c)` has id `3r + c`. Take
`P = [0,0,2, 1,1,1]` and target `(0,0)`. The only first move toward the target is
`(0,2)->(0,1)`, after which no vertex holds 2 pebbles. The sequence
`(0,2)->(1,2)` (away from the target), `(1,2)->(1,1)`, `(1,1)->(1,0)`,
`(1,0)->(0,0)` reaches it. The test suite checks this case.
