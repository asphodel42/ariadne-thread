from collections import deque
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import Enum, auto

from graph_model import Graph


class StepKind(Enum):
    VISIT = auto()          # a node was popped off the frontier and expanded
    EXPLORE_EDGE = auto()   # one neighbor edge was examined while expanding
    FOUND = auto()          # target was generated -> search stops, path_so_far is the answer
    DONE = auto()           # frontier exhausted, no path found


@dataclass
class StepEvent:
    kind: StepKind
    node: int | None
    edge: tuple[int, int] | None
    frontier: list[int] = field(default_factory=list)
    expanded: set[int] = field(default_factory=set)
    path_so_far: list[int] | None = None


def reconstruct_path(parent: dict[int, int], start: int, target: int) -> list[int]:
    path = [target]
    while path[-1] != start:
        path.append(parent[path[-1]])
    path.reverse()
    return path


def dfs(graph: Graph, start: int, target: int, order: str = "insertion") -> Iterator[StepEvent]:
    """Depth-first search.

    - the node added to the open list (stack) last is expanded first;
    - a node goes to the closed list when it is expanded;
    - every generated node is checked against the target right away;
    - a generated node is dropped only if it was already expanded; a node that is
      still waiting on the stack is pushed again on top with a new parent pointer,
      so the search keeps going deeper along the current branch.
    """
    stack = [start]
    expanded: set[int] = set()
    parent: dict[int, int] = {}

    def open_nodes() -> list[int]:
        # stale copies of already expanded nodes may stay deep in the stack; hide them
        return [v for v in stack if v not in expanded]

    if start == target:
        yield StepEvent(StepKind.FOUND, start, None, [], set(), [start])
        return

    while stack:
        current = stack.pop()
        if current in expanded:
            continue  # stale duplicate, this node was already expanded via a deeper branch
        expanded.add(current)
        yield StepEvent(StepKind.VISIT, current, None, open_nodes(), set(expanded))

        children = []
        for neighbor in graph.get_neighbors(current, order):
            yield StepEvent(StepKind.EXPLORE_EDGE, current, (current, neighbor), open_nodes(), set(expanded))
            if neighbor == target:
                parent[neighbor] = current
                path = reconstruct_path(parent, start, target)
                yield StepEvent(StepKind.FOUND, neighbor, (current, neighbor), open_nodes(), set(expanded), path)
                return
            if neighbor not in expanded:
                parent[neighbor] = current
                children.append(neighbor)
        # push in reverse so the first child in the chosen order ends up on top and is expanded next
        stack.extend(reversed(children))

    yield StepEvent(StepKind.DONE, None, None, [], set(expanded), None)


def bfs(graph: Graph, start: int, target: int, order: str = "insertion") -> Iterator[StepEvent]:
    """Breadth-first search.

    - the node added to the open list (queue) first is expanded first;
    - a node goes to the closed list when it is expanded;
    - every generated node is checked against the target right away;
    - a generated node is dropped if it was already expanded or is already waiting in
      the queue.
    """
    queue = deque([start])
    expanded: set[int] = set()
    parent: dict[int, int] = {}

    if start == target:
        yield StepEvent(StepKind.FOUND, start, None, [], set(), [start])
        return

    while queue:
        current = queue.popleft()
        expanded.add(current)
        yield StepEvent(StepKind.VISIT, current, None, list(queue), set(expanded))

        for neighbor in graph.get_neighbors(current, order):
            yield StepEvent(StepKind.EXPLORE_EDGE, current, (current, neighbor), list(queue), set(expanded))
            if neighbor == target:
                parent[neighbor] = current
                path = reconstruct_path(parent, start, target)
                yield StepEvent(StepKind.FOUND, neighbor, (current, neighbor), list(queue), set(expanded), path)
                return
            if neighbor not in expanded and neighbor not in parent:
                parent[neighbor] = current
                queue.append(neighbor)

    yield StepEvent(StepKind.DONE, None, None, [], set(expanded), None)


ALGORITHMS = {
    "DFS": dfs,
    "BFS": bfs,
}
