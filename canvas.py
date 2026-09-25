import math
import itertools

from enum import Enum, auto

from PyQt6.QtCore import QLineF, QPointF, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPainterPathStroker, QPen, QPolygonF, QTransform
from PyQt6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsScene,
    QGraphicsView,
    QMenu,
)

from algorithms import StepEvent, StepKind
from graph_model import DIRECTION_DIRECTED, DIRECTION_UNDIRECTED, Edge, Graph, Node

NODE_RADIUS = 18.0
ARROW_SIZE = 10.0


class EditMode(Enum):
    SELECT = auto()
    ADD_NODE = auto()
    ADD_EDGE = auto()


MODE_HINTS = {
    EditMode.SELECT: "Click a node or edge to select it, then use the actions on the left. Drag to reposition.",
    EditMode.ADD_NODE: "Click empty canvas to add a node.",
    EditMode.ADD_EDGE: "Click a source node, then a target node.",
}

SELECTION_COLOR = QColor("#1565c0")


class HighlightState(Enum):
    NORMAL = auto()
    VISITED = auto()
    FRONTIER = auto()
    CURRENT = auto()
    START = auto()
    TARGET = auto()
    ON_PATH = auto()


class EdgeHighlight(Enum):
    NORMAL = auto()
    EXPLORING = auto()
    ON_PATH = auto()


NODE_COLORS = {
    HighlightState.NORMAL: QColor("#f5f5f5"),
    HighlightState.VISITED: QColor("#c8e6c9"),
    HighlightState.FRONTIER: QColor("#fff9c4"),
    HighlightState.CURRENT: QColor("#ff8a65"),
    HighlightState.START: QColor("#66bb6a"),
    HighlightState.TARGET: QColor("#ef5350"),
    HighlightState.ON_PATH: QColor("#42a5f5"),
}

EDGE_COLORS = {
    EdgeHighlight.NORMAL: QColor("#9e9e9e"),
    EdgeHighlight.EXPLORING: QColor("#ff8a65"),
    EdgeHighlight.ON_PATH: QColor("#1e88e5"),
}


class NodeItem(QGraphicsEllipseItem):
    def __init__(self, graph: Graph, node_id: int, x: float, y: float, label: str) -> None:
        super().__init__(-NODE_RADIUS, -NODE_RADIUS, 2 * NODE_RADIUS, 2 * NODE_RADIUS)
        self.graph = graph
        self.node_id = node_id
        self.label = label
        self.highlight = HighlightState.NORMAL
        self.attached_edges: list[EdgeItem] = []
        self.setPos(x, y)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setZValue(1)

    def set_highlight(self, state: HighlightState) -> None:
        if self.highlight != state:
            self.highlight = state
            self.update()

    def boundingRect(self):
        return self.rect().adjusted(-8, -8, 8, 8)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            pos = self.pos()
            self.graph.move_node(self.node_id, pos.x(), pos.y())
            for edge_item in self.attached_edges:
                edge_item.update_position()
        return super().itemChange(change, value)

    def paint(self, painter, option, widget=None) -> None:
        color = NODE_COLORS[self.highlight]
        border_width = 3 if self.highlight in (HighlightState.CURRENT, HighlightState.START, HighlightState.TARGET) else 1
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(QColor("#424242"), border_width))
        painter.drawEllipse(self.rect())
        painter.setPen(QPen(QColor("#212121")))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.label)
        if self.isSelected():
            pen = QPen(SELECTION_COLOR, 3, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(self.rect().adjusted(-4, -4, 4, 4))


class EdgeItem(QGraphicsLineItem):
    def __init__(self, edge: Edge, source: NodeItem, target: NodeItem) -> None:
        super().__init__()
        self.edge = edge
        self.source = source
        self.target = target
        self.highlight = EdgeHighlight.NORMAL
        self.setZValue(-1)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.update_position()

    def set_highlight(self, state: EdgeHighlight) -> None:
        if self.highlight != state:
            self.highlight = state
            self.update()

    def update_position(self) -> None:
        p1, p2 = self.source.pos(), self.target.pos()
        line = QLineF(p1, p2)
        length = line.length()
        if length == 0:
            return
        unit = QPointF(line.dx() / length, line.dy() / length)
        self.prepareGeometryChange()
        self.setLine(QLineF(p1 + unit * NODE_RADIUS, p2 - unit * NODE_RADIUS))

    def boundingRect(self):
        return super().boundingRect().adjusted(-ARROW_SIZE, -ARROW_SIZE, ARROW_SIZE, ARROW_SIZE)

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        path.moveTo(self.line().p1())
        path.lineTo(self.line().p2())
        stroker = QPainterPathStroker()
        stroker.setWidth(10.0)
        return stroker.createStroke(path)

    def paint(self, painter, option, widget=None) -> None:
        color = SELECTION_COLOR if self.isSelected() else EDGE_COLORS[self.highlight]
        width = 3 if (self.isSelected() or self.highlight != EdgeHighlight.NORMAL) else 1.5
        pen = QPen(color, width)
        if self.isSelected():
            pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawLine(self.line())
        if self.edge.direction == DIRECTION_DIRECTED:
            line = self.line()
            forward_angle = math.atan2(-line.dy(), line.dx())
            self.draw_arrowhead(painter, color, line.p2(), forward_angle)

    def draw_arrowhead(self, painter, color: QColor, tip: QPointF, angle: float) -> None:
        a1 = tip - QPointF(math.cos(angle - math.pi / 6) * ARROW_SIZE, -math.sin(angle - math.pi / 6) * ARROW_SIZE)
        a2 = tip - QPointF(math.cos(angle + math.pi / 6) * ARROW_SIZE, -math.sin(angle + math.pi / 6) * ARROW_SIZE)
        painter.setBrush(QBrush(color))
        painter.drawPolygon(QPolygonF([tip, a1, a2]))


class GraphScene(QGraphicsScene):
    node_added = pyqtSignal(int)
    node_removed = pyqtSignal(int)
    edge_added = pyqtSignal(int, int)
    edge_removed = pyqtSignal(int, int)
    start_set = pyqtSignal(int)
    target_set = pyqtSignal(int)
    status_message = pyqtSignal(str)

    def __init__(self, graph: Graph, parent=None) -> None:
        super().__init__(parent)
        self.graph = graph
        self.mode = EditMode.SELECT
        self.new_edge_direction = DIRECTION_UNDIRECTED
        self.node_items: dict[int, NodeItem] = {}
        self.edge_items: dict[tuple[int, int], EdgeItem] = {}
        self.start_id: int | None = None
        self.target_id: int | None = None
        self.pending_edge_source: NodeItem | None = None
        self.rebuild_from_graph()

    def rebuild_from_graph(self) -> None:
        self.clear()
        self.node_items.clear()
        self.edge_items.clear()
        self.start_id = None
        self.target_id = None
        for node in self.graph.nodes.values():
            self.add_node_item(node)
        for edge in self.graph.edges:
            self.add_edge_item(edge)
        self.set_mode(self.mode)

    def add_node_item(self, node: Node) -> NodeItem:
        item = NodeItem(self.graph, node.id, node.x, node.y, node.label)
        self.addItem(item)
        self.node_items[node.id] = item
        return item

    def add_edge_item(self, edge: Edge) -> EdgeItem:
        source, target = self.node_items[edge.u], self.node_items[edge.v]
        item = EdgeItem(edge, source, target)
        self.addItem(item)
        self.edge_items[(edge.u, edge.v)] = item
        source.attached_edges.append(item)
        target.attached_edges.append(item)
        return item

    def find_edge_item(self, u: int, v: int) -> EdgeItem | None:
        return self.edge_items.get((u, v)) or self.edge_items.get((v, u))

    def set_mode(self, mode: EditMode) -> None:
        self.mode = mode
        self.pending_edge_source = None
        movable = mode == EditMode.SELECT
        for item in self.node_items.values():
            item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, movable)
        self.status_message.emit(MODE_HINTS[mode])

    def mousePressEvent(self, event) -> None:
        if self.mode == EditMode.SELECT or event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        pos = event.scenePos()
        item = self.itemAt(pos, QTransform())
        if self.mode == EditMode.ADD_NODE:
            if item is None:
                self.add_node_at(pos)
            return
        if self.mode == EditMode.ADD_EDGE:
            if isinstance(item, NodeItem):
                self.handle_add_edge_click(item)
            return
        super().mousePressEvent(event)

    def contextMenuEvent(self, event) -> None:
        item = self.itemAt(event.scenePos(), QTransform())
        menu = QMenu()
        if isinstance(item, EdgeItem):
            undirected_action = menu.addAction("Set undirected")
            directed_action = menu.addAction("Set directed")
            reverse_action = menu.addAction("Reverse direction")
            delete_action = menu.addAction("Delete edge")
            chosen = menu.exec(event.screenPos())
            if chosen == undirected_action:
                self.graph.set_edge_direction(item.edge.u, item.edge.v, DIRECTION_UNDIRECTED)
                item.update()
            elif chosen == directed_action:
                self.graph.set_edge_direction(item.edge.u, item.edge.v, DIRECTION_DIRECTED)
                item.update()
            elif chosen == reverse_action:
                self.reverse_edge_item(item)
            elif chosen == delete_action:
                self.delete_edge(item)
        elif isinstance(item, NodeItem):
            start_action = menu.addAction("Set as start")
            target_action = menu.addAction("Set as target")
            delete_action = menu.addAction("Delete node")
            chosen = menu.exec(event.screenPos())
            if chosen == start_action:
                self.set_start(item.node_id)
            elif chosen == target_action:
                self.set_target(item.node_id)
            elif chosen == delete_action:
                self.delete_node(item)

    def add_node_at(self, pos: QPointF) -> None:
        node = self.graph.add_node(pos.x(), pos.y())
        self.add_node_item(node)
        self.node_added.emit(node.id)

    def handle_add_edge_click(self, item: NodeItem) -> None:
        if self.pending_edge_source is None:
            self.pending_edge_source = item
            item.setSelected(True)
            self.status_message.emit(f"Node {item.node_id} selected as source — click the target node.")
            return
        source = self.pending_edge_source
        self.pending_edge_source = None
        source.setSelected(False)
        if source.node_id == item.node_id:
            return
        if self.graph.find_edge(source.node_id, item.node_id) is not None:
            self.status_message.emit("That edge already exists.")
            return
        edge = self.graph.add_edge(source.node_id, item.node_id, direction=self.new_edge_direction)
        self.add_edge_item(edge)
        self.edge_added.emit(edge.u, edge.v)
        self.status_message.emit(MODE_HINTS[EditMode.ADD_EDGE])

    def delete_node(self, item: NodeItem) -> None:
        node_id = item.node_id
        for edge_item in list(item.attached_edges):
            self.remove_edge_item(edge_item)
        self.graph.remove_node(node_id)
        self.removeItem(item)
        del self.node_items[node_id]
        if self.start_id == node_id:
            self.start_id = None
        if self.target_id == node_id:
            self.target_id = None
        self.node_removed.emit(node_id)

    def delete_edge(self, item: EdgeItem) -> None:
        self.remove_edge_item(item)
        self.graph.remove_edge(item.edge.u, item.edge.v)
        self.edge_removed.emit(item.edge.u, item.edge.v)

    def remove_edge_item(self, item: EdgeItem) -> None:
        key = (item.edge.u, item.edge.v)
        self.edge_items.pop(key, None)
        item.source.attached_edges.remove(item)
        item.target.attached_edges.remove(item)
        self.removeItem(item)

    def reverse_edge_item(self, item: EdgeItem) -> None:
        old_key = (item.edge.u, item.edge.v)
        self.graph.reverse_edge(*old_key)
        item.source, item.target = item.target, item.source
        self.edge_items.pop(old_key, None)
        self.edge_items[(item.edge.u, item.edge.v)] = item
        item.update_position()
        item.update()

    def selected_node(self) -> NodeItem | None:
        nodes = [item for item in self.selectedItems() if isinstance(item, NodeItem)]
        return nodes[0] if len(nodes) == 1 else None

    def selected_edges(self) -> list[EdgeItem]:
        return [item for item in self.selectedItems() if isinstance(item, EdgeItem)]

    def delete_selected(self) -> None:
        for item in list(self.selectedItems()):
            if isinstance(item, NodeItem) and item.node_id in self.node_items:
                self.delete_node(item)
            elif isinstance(item, EdgeItem) and (item.edge.u, item.edge.v) in self.edge_items:
                self.delete_edge(item)

    def cycle_direction_selected(self) -> None:
        for item in self.selected_edges():
            self.graph.cycle_edge_direction(item.edge.u, item.edge.v)
            item.update()

    def reverse_direction_selected(self) -> None:
        for item in self.selected_edges():
            self.reverse_edge_item(item)

    def set_start(self, node_id: int) -> None:
        self.start_id = node_id
        self.render_idle()
        self.start_set.emit(node_id)

    def set_target(self, node_id: int) -> None:
        self.target_id = node_id
        self.render_idle()
        self.target_set.emit(node_id)

    def render_idle(self) -> None:
        for item in self.node_items.values():
            item.set_highlight(HighlightState.NORMAL)
        for item in self.edge_items.values():
            item.set_highlight(EdgeHighlight.NORMAL)
        if self.start_id in self.node_items:
            self.node_items[self.start_id].set_highlight(HighlightState.START)
        if self.target_id in self.node_items:
            self.node_items[self.target_id].set_highlight(HighlightState.TARGET)

    def render_state(self, event: StepEvent) -> None:
        for item in self.node_items.values():
            item.set_highlight(HighlightState.NORMAL)
        for item in self.edge_items.values():
            item.set_highlight(EdgeHighlight.NORMAL)

        for node_id in event.expanded:
            if node_id in self.node_items:
                self.node_items[node_id].set_highlight(HighlightState.VISITED)
        for node_id in event.frontier:
            if node_id in self.node_items:
                self.node_items[node_id].set_highlight(HighlightState.FRONTIER)
        if event.node is not None and event.node in self.node_items:
            self.node_items[event.node].set_highlight(HighlightState.CURRENT)
        if self.start_id in self.node_items:
            self.node_items[self.start_id].set_highlight(HighlightState.START)
        if self.target_id in self.node_items:
            self.node_items[self.target_id].set_highlight(HighlightState.TARGET)

        if event.kind == StepKind.EXPLORE_EDGE and event.edge is not None:
            edge_item = self.find_edge_item(*event.edge)
            if edge_item is not None:
                edge_item.set_highlight(EdgeHighlight.EXPLORING)

        if event.kind == StepKind.FOUND and event.path_so_far:
            path = event.path_so_far
            for node_id in path:
                if node_id in self.node_items:
                    self.node_items[node_id].set_highlight(HighlightState.ON_PATH)
            for a, b in itertools.pairwise(path):
                edge_item = self.find_edge_item(a, b)
                if edge_item is not None:
                    edge_item.set_highlight(EdgeHighlight.ON_PATH)
            if self.start_id in self.node_items:
                self.node_items[self.start_id].set_highlight(HighlightState.START)
            if self.target_id in self.node_items:
                self.node_items[self.target_id].set_highlight(HighlightState.TARGET)


class GraphView(QGraphicsView):
    def __init__(self, scene: GraphScene, parent=None) -> None:
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)

    def mousePressEvent(self, event) -> None:
        scene = self.scene()
        can_pan = (
            event.button() == Qt.MouseButton.LeftButton
            and isinstance(scene, GraphScene)
            and scene.mode == EditMode.SELECT
            and self.itemAt(event.pos()) is None
        )
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag if can_pan else QGraphicsView.DragMode.NoDrag)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        super().mouseReleaseEvent(event)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)

    def wheelEvent(self, event) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            delta = event.angleDelta().y() or event.angleDelta().x()
            bar = self.horizontalScrollBar()
            bar.setValue(bar.value() - delta)
            event.accept()
            return
        super().wheelEvent(event)
