# A solvable distribution with $v_P(x) < 3/2$ at a degree-4 vertex (PPS Conjecture 4.1)

Key `5dc88ec7bccc7a39`; machine-readable data in `data/counterexample_10x10.json`, re-checked by `verify_counterexample.py`. Every number in this document is exact. The solvability certificate below can be checked by hand, one move at a time.

## The statement checked

PPS Conjecture 4.1, journal version (Petr, Portier, Stolarczyk, *Discrete Mathematics* 346 (2023) 113212):

> Let P be a solvable pebbling distribution on the grid. Then for all vertices x that have degree 4, v(x) >= 3/2.

The arXiv version (arXiv:2111.13173v1) numbers it Conjecture 1 and reads:

> Let $P$ be a solvable pebbling distribution on the grid. Then for all vertices $X$ that do not lie on the boundary of the grid, $v(X) \geq \frac{3}{2}$.

On an $m\times n$ grid with $m,n\ge3$, a vertex has degree 4 exactly when it is not on the boundary, so the two wordings are the same statement. The distribution below violates both.

Definitions used (arXiv:2111.13173v1, quoted): "A pebbling move ... consists of removing $2$ pebbles from a vertex and adding $1$ pebble to one of the neighbouring vertices. A vertex is called reachable if we can put $1$ pebble on it after a sequence of moves." A distribution is solvable if every vertex is reachable. "We define the value of $x$ as $v(x)=\sum_{y \in V(G)} v_y(x)$", where "$v_y(x)=P(y)2^{-d(x,y)}$ where $d$ is the graph distance in $G$." On the grid, $d$ is the taxicab distance.

## The grid and $P$

Grid $10\times10$ (rows and columns numbered from 0), $|P| = 57$ pebbles on 24 vertices. Entry = number of pebbles; `.` = none; `[ ]` marks $x=(5,5)$ (degree 4, distance 4 from the boundary).

```
        0   1   2   3   4   5   6   7   8   9
   0    2   .   .   2   .   .   3   .   4   .
   1    3   2   2   3   .   .   .   .   .   .
   2    3   2   2   3   .   .   .   .   .   .
   3    2   .   .   .   .   .   .   .   4   .
   4    .   .   .   .   .   .   1   .   .   .
   5    .   .   .   .   . [.]   .   .   .   .
   6    1   .   .   1   .   .   .   2   .   .
   7    .   .   .   .   .   .   1   .   .   .
   8    4   .   .   4   .   .   1   .   3   .
   9    .   .   .   .   .   .   .   .   2   .
```

## $v_P(x)$ at $x = (5,5)$, term by term

Each pebbled vertex $y$ contributes $P(y)\,2^{-d(x,y)}$, with $d(x,y)=|y_1-x_1|+|y_2-x_2|$.

| $y$ | $P(y)$ | $d(x,y)$ | $P(y)2^{-d}$ |
|---|---|---|---|
| (4,6) | 1 | 2 | 1/4 |
| (6,3) | 1 | 3 | 1/8 |
| (6,7) | 2 | 3 | 1/4 |
| (7,6) | 1 | 3 | 1/8 |
| (8,6) | 1 | 4 | 1/16 |
| (2,3) | 3 | 5 | 3/32 |
| (3,8) | 4 | 5 | 1/8 |
| (8,3) | 4 | 5 | 1/8 |
| (0,6) | 3 | 6 | 3/64 |
| (1,3) | 3 | 6 | 3/64 |
| (2,2) | 2 | 6 | 1/32 |
| (6,0) | 1 | 6 | 1/64 |
| (8,8) | 3 | 6 | 3/64 |
| (0,3) | 2 | 7 | 1/64 |
| (1,2) | 2 | 7 | 1/64 |
| (2,1) | 2 | 7 | 1/64 |
| (3,0) | 2 | 7 | 1/64 |
| (9,8) | 2 | 7 | 1/64 |
| (0,8) | 4 | 8 | 1/64 |
| (1,1) | 2 | 8 | 1/128 |
| (2,0) | 3 | 8 | 3/256 |
| (8,0) | 4 | 8 | 1/64 |
| (1,0) | 3 | 9 | 3/512 |
| (0,0) | 2 | 10 | 1/512 |

Grouped by distance (pebbles at distance $k$, over $2^k$): $v_P(x) = 1/2^2 + 4/2^3 + 1/2^4 + 11/2^5 + 12/2^6 + 10/2^7 + 13/2^8 + 3/2^9 + 2/2^10$.

Over the common denominator $2^{10} = 1024$: $v_P(x) = (1\cdot256 + 4\cdot128 + 1\cdot64 + 11\cdot32 + 12\cdot16 + 10\cdot8 + 13\cdot4 + 3\cdot2 + 2\cdot1)/1024 = 1516/1024 = 379/256$.

Since $3/2 = 1536/1024$ and $1516 < 1536$, $v_P(x) < 3/2$. (Recomputed with `naivecheck` BFS distances and Fraction: 379/256.)

Every degree-4 vertex with $v_P < 3/2$: (5,5) with $v_P = 379/256$ (margin 4).

## Solvability: a move sequence for every vertex

Notation: a move `ab>cd` removes two pebbles from $(a,b)$ and puts one on $(c,d)$; the vertices must be adjacent. Each line lists the target vertex and a sequence of moves, applied in order to the original $P$ (each line starts again from $P$). A sequence is valid if every move takes two pebbles from a vertex that has at least two at that moment, and at the end the target has at least one pebble. Vertices with a pebble in $P$ need no moves (`-`).

The sequences were found by `pebbling/solver.py` (exact backward search) and then shortened while the replay still succeeds. Each stops as soon as its target holds a pebble, and no single move or pair of moves can be deleted from it. They are not claimed to be shortest. Every sequence was replayed successfully by `naivecheck/naive.py`, which shares no code with the solver, and again by the coordinate-only checker printed below. Total 466 moves; longest sequence 46 moves.

```
00: -
01: 11>01
02: 12>02
03: -
04: 03>04
05: 06>05
06: -
07: 08>07
08: -
09: 08>09
10: -
11: -
12: -
13: -
14: 13>14
15: 23>13 13>14 13>14 14>15
16: 06>16
17: 06>07 08>07 07>17
18: 08>18
19: 08>18 08>18 18>19
20: -
21: -
22: -
23: -
24: 23>24
25: 13>23 23>24 23>24 24>25
26: 08>07 08>07 07>06 06>16 06>16 16>26
27: 38>28 38>28 28>27
28: 38>28
29: 38>28 38>28 28>29
30: -
31: 21>31
32: 22>32
33: 23>33
34: 13>23 23>33 23>33 33>34
35: 12>13 22>23 08>07 08>07 07>06 06>05 06>05 13>14 13>14 05>15 14>15 23>24 23>24 15>25 24>25 25>35
36: 00>10 10>11 10>11 30>20 11>12 11>12 20>21 20>21 12>13 03>13 12>13 21>22 21>22 13>23 22>23 22>23 13>14 13>14 23>24 14>24 23>24 23>24 08>07 08>07 07>06 24>25 24>25 06>16 06>16 25>26 16>26 26>36
37: 38>37
38: -
39: 38>39
40: 30>40
41: 30>31 21>31 31>41
42: 12>22 23>22 22>32 22>32 32>42
43: 13>23 23>33 23>33 33>43
44: 11>21 20>21 21>31 30>31 03>13 12>22 21>22 22>32 31>32 13>23 22>23 13>23 23>33 32>33 23>33 23>33 33>43 33>43 43>44
45: 00>10 10>11 10>11 30>20 11>12 11>12 20>21 20>21 12>13 03>13 12>13 21>22 21>22 13>23 22>23 22>23 13>14 13>14 23>24 14>24 23>24 23>24 08>07 08>07 07>06 24>25 24>25 06>16 06>16 25>26 16>26 38>37 38>37 26>36 37>36 36>46 46>45
46: -
47: 00>10 10>11 10>11 30>20 11>12 11>12 20>21 20>21 12>13 03>13 12>13 21>22 21>22 13>23 22>23 22>23 13>14 13>14 23>24 14>24 23>24 23>24 08>07 08>07 07>06 24>25 24>25 06>16 06>16 25>26 16>26 38>37 38>37 26>36 37>36 36>46 46>47
48: 38>48
49: 38>48 38>48 48>49
50: 80>70 80>70 70>60 60>50
51: 11>21 22>21 10>20 21>31 21>31 20>30 20>30 30>40 30>40 40>41 31>41 41>51
52: 03>13 13>12 13>12 00>10 12>11 10>11 12>22 23>22 10>20 11>21 11>21 20>30 20>30 21>31 21>31 30>40 30>40 40>41 31>41 22>32 22>32 41>42 32>42 42>52
53: 83>73 83>73 73>63 63>53
54: 11>21 20>21 21>31 30>31 03>13 12>22 21>22 22>32 31>32 13>23 22>23 13>23 23>33 32>33 23>33 23>33 33>43 33>43 83>73 83>73 73>63 43>53 63>53 53>54
55: 00>10 10>11 10>11 30>20 11>12 11>12 20>21 20>21 12>13 03>13 12>13 21>22 21>22 13>23 22>23 22>23 13>14 13>14 23>24 14>24 23>24 23>24 08>07 08>07 07>06 24>25 24>25 06>16 06>16 25>26 16>26 38>37 38>37 26>36 37>36 98>88 88>87 88>87 87>86 86>76 76>66 67>66 36>46 66>56 46>56 56>55
56: 00>10 10>11 10>11 30>20 11>12 11>12 20>21 20>21 12>13 03>13 12>13 21>22 21>22 13>23 22>23 22>23 13>14 13>14 23>24 14>24 23>24 23>24 08>07 08>07 07>06 24>25 24>25 06>16 06>16 25>26 16>26 38>37 38>37 26>36 37>36 36>46 46>56
57: 67>57
58: 38>48 38>48 48>58
59: 98>88 88>78 88>78 78>68 67>68 38>48 38>48 68>58 48>58 58>59
60: -
61: 80>70 80>70 70>60 60>61
62: 83>73 83>73 73>63 63>62
63: -
64: 83>73 83>73 73>63 63>64
65: 98>88 88>87 88>87 87>86 86>76 76>66 67>66 66>65
66: 67>66
67: -
68: 67>68
69: 98>88 88>78 88>78 78>68 67>68 68>69
70: 80>70
71: 80>81 80>81 81>71
72: 83>82 83>82 82>72
73: 83>73
74: 83>73 83>73 73>74
75: 98>88 88>87 88>87 87>86 86>76 76>75
76: -
77: 67>77
78: 88>78
79: 98>88 88>78 88>78 78>79
80: -
81: 80>81
82: 83>82
83: -
84: 83>84
85: 98>88 88>78 88>78 78>77 67>77 77>76 76>86 86>85
86: -
87: 88>87
88: -
89: 88>89
90: 80>90
91: 80>81 80>81 81>91
92: 83>82 83>82 82>92
93: 83>93
94: 83>84 83>84 84>94
95: 98>88 88>78 88>78 78>77 67>77 77>76 76>86 83>84 83>84 84>85 86>85 85>95
96: 98>88 88>78 88>78 78>77 67>77 77>76 76>86 86>96
97: 98>97
98: -
99: 98>99
```

A short program that checks every line (the same test as `naivecheck/naive.py:replay_moves`):

```python
def check(P, moves, target):  # P: dict (row, col) -> pebbles
    Q = dict(P)
    for (a, b), (c, d) in moves:
        assert abs(a - c) + abs(b - d) == 1 and Q.get((a, b), 0) >= 2
        Q[(a, b)] -= 2
        Q[(c, d)] = Q.get((c, d), 0) + 1
    return Q.get(target, 0) >= 1
```

Every vertex was also checked by an engine other than `solver.py`: 24 vertices already hold a pebble, 61 were shown reachable by the naive forward search `naivecheck/naive.py:is_reachable`, and 15 by the CP-SAT model in `pebbling/ipsolver.py`, whose move sequences were again replayed by `naivecheck`.

## What this does and does not show

It shows, in a way that can be checked by hand from this page, that the Conjecture as printed, with $v$ computed from $P$ itself, is false: $P$ is solvable and the degree-4 vertex $(5,5)$ has $v_P = 379/256 < 3/2$. It does not touch the version the paper's method needs. PPS prove the lower bound through the hemmed distribution $P'$ ($P$ plus two pebbles on every boundary vertex; Lemma 2.1 is stated for $P'$), and under $P'$ all 18 candidates we found have $v_{P'} \ge 1.979$ at every non-boundary vertex. So this distribution is no evidence against "$v_{P'}(x) \ge 3/2$", and it has no effect on their lower bound $5092/28593\,nm$. The low value at $x$ comes from the boundary: pebbles near the edge are few, and raw $P$ gets no credit for the boundary's missing neighbours. Hemming adds that credit back.

## Provenance

- Found by a randomized search, then certified: every move sequence above was produced by `pebbling/solver.py` and replayed by `naivecheck/naive.py`; every vertex was confirmed a second time by an engine that did not produce its certificate.
- Key: sha1 of the smallest image of $P$ under the 8 symmetries of the square, `5dc88ec7bccc7a39`.
- Re-verify from scratch: `python verify_counterexample.py`.
