"""Graphs for pebbling: constructors, all-pairs distances, grid symmetries."""
from collections import deque
import random


class Graph:
    def __init__(self, name, num_vertices, edges, kind="other", coords=None, grid_shape=None):
        n = num_vertices
        nbrs = [set() for _ in range(n)]
        for a, b in edges:
            if not (0 <= a < n and 0 <= b < n) or a == b:
                raise ValueError(f"bad edge {(a, b)} for {name}")
            nbrs[a].add(b)
            nbrs[b].add(a)
        self.name = name
        self.kind = kind
        self.n = n
        self.adj = tuple(tuple(sorted(s)) for s in nbrs)
        self.edges = tuple(sorted({(min(a, b), max(a, b)) for a, b in edges}))
        self.coords = coords
        self.grid_shape = grid_shape
        self.dist = tuple(tuple(self._bfs(s)) for s in range(n))
        for row in self.dist:
            if min(row) < 0:
                raise ValueError(f"{name} is disconnected")
        self.diam = max(max(row) for row in self.dist)
        # potentials are exact integers: v_P(X) = sum_y P[y] * weight[X][y] / scale
        self.scale = 1 << self.diam
        self.weight = tuple(tuple(1 << (self.diam - d) for d in row) for row in self.dist)
        self.weight2 = tuple(tuple(2 * w for w in row) for row in self.weight)

    def _bfs(self, s):
        dist = [-1] * self.n
        dist[s] = 0
        q = deque([s])
        while q:
            x = q.popleft()
            for y in self.adj[x]:
                if dist[y] < 0:
                    dist[y] = dist[x] + 1
                    q.append(y)
        return dist

    def spec(self):
        """String from which make_graph() rebuilds this graph (for worker processes)."""
        if self.kind == "grid":
            return f"grid:{self.grid_shape[0]}x{self.grid_shape[1]}"
        if self.kind in ("path", "cycle", "complete"):
            return f"{self.kind}:{self.n}"
        if self.kind == "petersen":
            return "petersen"
        return "edges:" + str(self.n) + ":" + ";".join(f"{a}-{b}" for a, b in self.edges)

    def __repr__(self):
        return f"Graph({self.name}, n={self.n}, |E|={len(self.edges)})"


def complete_graph(n):
    return Graph(f"K{n}", n, [(a, b) for a in range(n) for b in range(a + 1, n)], kind="complete")


def path_graph(n):
    return Graph(f"P{n}", n, [(i, i + 1) for i in range(n - 1)], kind="path")


def cycle_graph(n):
    if n < 3:
        raise ValueError("cycle needs n >= 3")
    return Graph(f"C{n}", n, [(i, (i + 1) % n) for i in range(n)], kind="cycle")


def grid_graph(m, n):
    edges = []
    for i in range(m):
        for j in range(n):
            v = i * n + j
            if i + 1 < m:
                edges.append((v, v + n))
            if j + 1 < n:
                edges.append((v, v + 1))
    coords = tuple((i, j) for i in range(m) for j in range(n))
    return Graph(f"grid{m}x{n}", m * n, edges, kind="grid", coords=coords, grid_shape=(m, n))


def petersen_graph():
    outer = [(i, (i + 1) % 5) for i in range(5)]
    spokes = [(i, i + 5) for i in range(5)]
    inner = [(5 + i, 5 + (i + 2) % 5) for i in range(5)]
    return Graph("Petersen", 10, outer + spokes + inner, kind="petersen")


def random_connected_graph(n, p, rng):
    """G(n, p) conditioned on connectivity (rejection sampling), for solver cross-checks."""
    while True:
        edges = [(a, b) for a in range(n) for b in range(a + 1, n) if rng.random() < p]
        try:
            g = Graph(f"rand{n}", n, edges, kind="other")
        except ValueError:
            continue
        return g


def make_graph(spec):
    kind, _, rest = spec.partition(":")
    if kind == "grid":
        m, n = rest.split("x")
        return grid_graph(int(m), int(n))
    if kind == "path":
        return path_graph(int(rest))
    if kind == "cycle":
        return cycle_graph(int(rest))
    if kind == "complete":
        return complete_graph(int(rest))
    if kind == "petersen":
        return petersen_graph()
    if kind == "edges":
        n_str, _, e_str = rest.partition(":")
        edges = [tuple(int(x) for x in e.split("-")) for e in e_str.split(";") if e]
        return Graph(f"rand{n_str}", int(n_str), edges, kind="other")
    raise ValueError(spec)


def grid_symmetries(m, n):
    """The 8 dihedral maps of an m-by-n grid."""
    maps = [
        ("id", (m, n), lambda i, j: (i, j)),
        ("flip_rows", (m, n), lambda i, j: (m - 1 - i, j)),
        ("flip_cols", (m, n), lambda i, j: (i, n - 1 - j)),
        ("rot180", (m, n), lambda i, j: (m - 1 - i, n - 1 - j)),
        ("transpose", (n, m), lambda i, j: (j, i)),
        ("anti_transpose", (n, m), lambda i, j: (n - 1 - j, m - 1 - i)),
        ("rot90", (n, m), lambda i, j: (j, m - 1 - i)),
        ("rot270", (n, m), lambda i, j: (n - 1 - j, i)),
    ]
    out = []
    for name, (m2, n2), f in maps:
        perm = []
        for i in range(m):
            for j in range(n):
                i2, j2 = f(i, j)
                if not (0 <= i2 < m2 and 0 <= j2 < n2):
                    raise AssertionError(f"symmetry {name} leaves the grid")
                perm.append(i2 * n2 + j2)
        out.append((name, (m2, n2), tuple(perm)))
    return out


def apply_perm(P, perm):
    """Image of distribution P under a vertex map perm (perm must be a bijection)."""
    Q = [0] * len(P)
    for v, c in enumerate(P):
        Q[perm[v]] = c
    return tuple(Q)


def boundary_distance(G, v):
    """Distance from v to the nearest boundary vertex."""
    if G.kind == "grid":
        m, n = G.grid_shape
        i, j = G.coords[v]
        return min(i, j, m - 1 - i, n - 1 - j)
    if G.kind == "path":
        return min(v, G.n - 1 - v)
    raise ValueError(f"boundary distance undefined for kind {G.kind}")
