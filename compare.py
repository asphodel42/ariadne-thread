"""BFS vs DFS over all node pairs of several graph variants."""
from pathlib import Path

from algorithms import bfs, dfs
from graph_model import Graph

DATA = Path(__file__).parent / "data"
ORDERS = ("ascending", "descending")
GRAPHS = {
    "A": "default_graph.json",
    "B": "graph_B_more_edges.json",
    "D": "graph_D_more_nodes_and_edges.json",
    "U": "graph_U_undirected.json",
    "G": "graph_G_directed.json",
    "T": "graph_T_tree.json",
}


def distances(g: Graph, s: int) -> dict[int, int]:
    """Shortest distances from s, layer by layer, independent of the traversal order."""
    dist, layer = {s: 0}, [s]
    while layer:
        nxt = []
        for u in layer:
            for v in g.get_neighbors(u):
                if v not in dist:
                    dist[v] = dist[u] + 1
                    nxt.append(v)
        layer = nxt
    return dist


def run(alg, g: Graph, s: int, t: int, order: str) -> tuple[int, int, int]:
    """(path length, expanded nodes, largest open list) of one search."""
    events = list(alg(g, s, t, order))
    last = events[-1]
    return len(last.path_so_far) - 1, len(last.expanded), max(len(e.frontier) for e in events)


def main() -> None:
    header = ("Graph", "n/m", "Order", "Len BFS", "Len DFS", "DFS opt", "Exp BFS", "Exp DFS", "Queue", "Stack", "Pairs")
    print("{:<5} {:>5} {:<10} {:>7} {:>7} {:>7} {:>7} {:>7} {:>6} {:>6} {:>6}".format(*header))
    for name, file in GRAPHS.items():
        g = Graph.from_json(DATA / file)
        dist = {s: distances(g, s) for s in g.nodes}
        pairs = [(s, t) for s in g.nodes for t in g.nodes if s != t and t in dist[s]]
        for order in ORDERS:
            totals = [0] * 7  # len bfs, len dfs, dfs optimal, exp bfs, exp dfs, queue, stack
            for s, t in pairs:
                lb, eb, qb = run(bfs, g, s, t, order)
                ld, ed, qd = run(dfs, g, s, t, order)
                assert lb == dist[s][t], f"BFS path is not shortest: {name} {s}->{t} {order}"
                for i, value in enumerate((lb, ld, ld == lb, eb, ed, qb, qd)):
                    totals[i] += value
            avg = [x / len(pairs) for x in totals]
            print(f"{name:<5} {len(g.nodes):>2}/{len(g.edges):<2} {order:<10} {avg[0]:>7.1f} {avg[1]:>7.1f} "
                  f"{avg[2]:>7.0%} {avg[3]:>7.1f} {avg[4]:>7.1f} {avg[5]:>6.1f} {avg[6]:>6.1f} {len(pairs):>6}")
    print("ok: every BFS path is the shortest one")


if __name__ == "__main__":
    main()
