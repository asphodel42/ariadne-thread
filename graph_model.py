import json
import random
from dataclasses import dataclass
from pathlib import Path

DIRECTION_UNDIRECTED = "undirected"
DIRECTION_DIRECTED = "directed"
EDGE_DIRECTIONS = (DIRECTION_UNDIRECTED, DIRECTION_DIRECTED)


@dataclass
class Node:
    id: int
    x: float
    y: float
    label: str = ""


@dataclass
class Edge:
    u: int
    v: int
    direction: str = DIRECTION_UNDIRECTED


class Graph:
    def __init__(self) -> None:
        self.nodes: dict[int, Node] = {}
        self.out_edges: dict[int, list[Edge]] = {}
        self.next_id = 0

    def add_node(self, x: float, y: float, label: str | None = None, node_id: int | None = None) -> Node:
        vid = self.next_id if node_id is None else node_id
        if vid in self.nodes:
            raise ValueError(f"node {vid} already exists")
        node = Node(vid, x, y, label or str(vid))
        self.nodes[vid] = node
        self.out_edges[vid] = []
        self.next_id = max(self.next_id, vid + 1)
        return node

    def remove_node(self, node_id: int) -> None:
        if node_id not in self.nodes:
            return
        for edge in list(self.out_edges.get(node_id, [])):
            self.remove_edge(edge.u, edge.v)
        del self.nodes[node_id]
        del self.out_edges[node_id]

    def move_node(self, node_id: int, x: float, y: float) -> None:
        node = self.nodes[node_id]
        node.x, node.y = x, y

    def find_edge(self, u: int, v: int) -> Edge | None:
        for e in self.out_edges.get(u, []):
            if {e.u, e.v} == {u, v}:
                return e
        for e in self.out_edges.get(v, []):
            if {e.u, e.v} == {u, v}:
                return e
        return None

    def add_edge(self, u: int, v: int, direction: str = DIRECTION_UNDIRECTED) -> Edge:
        if u == v:
            raise ValueError("self-loops are not allowed")
        if u not in self.nodes or v not in self.nodes:
            raise ValueError("both endpoints must exist")
        if self.find_edge(u, v) is not None:
            raise ValueError(f"edge between {u} and {v} already exists")
        edge = Edge(u, v, direction)
        self.out_edges[u].append(edge)
        if direction != DIRECTION_DIRECTED:
            self.out_edges[v].append(edge)
        return edge

    def remove_edge(self, u: int, v: int) -> None:
        for owner in (u, v):
            edges = self.out_edges.get(owner)
            if edges is None:
                continue
            self.out_edges[owner] = []
            for e in edges:
                if {e.u, e.v} != {u, v}:
                    self.out_edges[owner].append(e)

    def resync_edge_membership(self, edge: Edge) -> None:
        for node_id in (edge.u, edge.v):
            lst = self.out_edges[node_id]
            if edge in lst:
                lst.remove(edge)
        self.out_edges[edge.u].append(edge)
        if edge.direction != DIRECTION_DIRECTED:
            self.out_edges[edge.v].append(edge)

    def set_edge_direction(self, u: int, v: int, direction: str) -> None:
        if direction not in EDGE_DIRECTIONS:
            raise ValueError(f"unknown edge direction: {direction}")
        edge = self.find_edge(u, v)
        if edge is None:
            raise ValueError(f"no edge between {u} and {v}")
        edge.direction = direction
        self.resync_edge_membership(edge)

    def cycle_edge_direction(self, u: int, v: int) -> None:
        edge = self.find_edge(u, v)
        if edge is None:
            raise ValueError(f"no edge between {u} and {v}")
        next_direction = EDGE_DIRECTIONS[(EDGE_DIRECTIONS.index(edge.direction) + 1) % len(EDGE_DIRECTIONS)]
        self.set_edge_direction(u, v, next_direction)

    def reverse_edge(self, u: int, v: int) -> None:
        edge = self.find_edge(u, v)
        if edge is None:
            raise ValueError(f"no edge between {u} and {v}")
        edge.u, edge.v = edge.v, edge.u
        self.resync_edge_membership(edge)

    @property
    def edges(self) -> list[Edge]:
        seen: set[tuple[int, int]] = set()
        result: list[Edge] = []
        for edge_list in self.out_edges.values():
            for e in edge_list:
                key = (e.u, e.v)
                if key not in seen:
                    seen.add(key)
                    result.append(e)
        return result

    def get_neighbors(self, node_id: int, order: str = "insertion") -> list[int]:
        edges = self.out_edges.get(node_id, [])
        neighbors = []
        for e in edges:
            if e.u == node_id:
                neighbors.append(e.v)
            else:
                neighbors.append(e.u)
        if order == "insertion":
            return neighbors
        if order == "reverse_insertion":
            return list(reversed(neighbors))
        if order == "ascending":
            return sorted(neighbors)
        if order == "descending":
            return sorted(neighbors, reverse=True)
        raise ValueError(f"unknown order: {order}")

    def to_json(self, path: str | Path) -> None:
        node_list = []
        for node in self.nodes.values():
            node_list.append({"id": node.id, "x": node.x, "y": node.y, "label": node.label})

        edge_list = []
        for edge in self.edges:
            edge_list.append({"u": edge.u, "v": edge.v, "direction": edge.direction})

        data = {"nodes": node_list, "edges": edge_list}
        Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")

    @classmethod
    def from_json(cls, path: str | Path) -> "Graph":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        graph = cls()
        for vd in data["nodes"]:
            graph.add_node(vd["x"], vd["y"], vd.get("label"), node_id=vd["id"])
        for ed in data["edges"]:
            if "direction" in ed:
                direction = ed["direction"]
            else:
                direction = DIRECTION_DIRECTED if ed.get("directed", False) else DIRECTION_UNDIRECTED
            graph.add_edge(ed["u"], ed["v"], direction)
        return graph


def layered_layout(
    n_nodes: int,
    parent_of: dict[int, int],
    x_spacing: float = 90.0,
    y_spacing: float = 110.0,
    margin: float = 60.0,
) -> dict[int, tuple[float, float]]:
    depth = {0: 0}
    for i in range(1, n_nodes):
        depth[i] = depth[parent_of[i]] + 1

    levels: dict[int, list[int]] = {}
    for node_id, d in depth.items():
        levels.setdefault(d, []).append(node_id)

    positions: dict[int, tuple[float, float]] = {0: (0.0, 0.0)}
    for d in sorted(levels):
        if d == 0:
            continue

        pairs = []
        for node_id in levels[d]:
            parent_x = positions[parent_of[node_id]][0]
            pairs.append((parent_x, node_id))
        pairs.sort()

        nodes = []
        for parent_x, node_id in pairs:
            nodes.append(node_id)

        count = len(nodes)
        for idx, node_id in enumerate(nodes):
            x = (idx - (count - 1) / 2) * x_spacing
            positions[node_id] = (x, d * y_spacing)

    min_x = None
    for x, y in positions.values():
        if min_x is None or x < min_x:
            min_x = x

    result: dict[int, tuple[float, float]] = {}
    for node_id, xy in positions.items():
        x, y = xy
        result[node_id] = (x - min_x + margin, y + margin)
    return result


def generate_random_graph(
    n_nodes: int,
    n_edges: int,
    tree_mode: bool = False,
    percent_directed: float = 0.0,
    seed: int | None = None,
) -> Graph:
    if n_nodes < 2:
        raise ValueError("n_nodes must be >= 2")
    rng = random.Random(seed)
    graph = Graph()

    parent_of: dict[int, int] = {}
    for i in range(1, n_nodes):
        parent_of[i] = rng.randrange(i)

    if tree_mode:
        min_branches = min(5, n_nodes - 1)
        root_children = [i for i, p in parent_of.items() if p == 0]
        if len(root_children) < min_branches:
            candidates = [i for i in range(1, n_nodes) if parent_of[i] != 0]
            rng.shuffle(candidates)
            for i in candidates[: min_branches - len(root_children)]:
                parent_of[i] = 0

    positions = layered_layout(n_nodes, parent_of)
    for i in range(n_nodes):
        x, y = positions[i]
        graph.add_node(x, y, node_id=i)
    for i in range(1, n_nodes):
        graph.add_edge(parent_of[i], i)

    if not tree_mode:
        if n_edges < n_nodes - 1:
            raise ValueError("n_edges must be >= n_nodes - 1 for a connected graph")
        existing_pairs = {frozenset((e.u, e.v)) for e in graph.edges}
        attempts = 0
        max_attempts = max(n_edges, 1) * 50
        while len(graph.edges) < n_edges and attempts < max_attempts:
            attempts += 1
            u, v = rng.randrange(n_nodes), rng.randrange(n_nodes)
            if u == v:
                continue
            pair = frozenset((u, v))
            if pair in existing_pairs:
                continue
            graph.add_edge(u, v)
            existing_pairs.add(pair)

    if percent_directed > 0:
        all_edges = graph.edges
        k = min(round(percent_directed / 100 * len(all_edges)), len(all_edges))
        for edge in rng.sample(all_edges, k):
            graph.set_edge_direction(edge.u, edge.v, DIRECTION_DIRECTED)

    return graph
