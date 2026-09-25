from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDockWidget,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStatusBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from algorithms import ALGORITHMS, StepKind
from animation import AnimationController
from canvas import EditMode, GraphScene, GraphView
from graph_model import (
    DIRECTION_DIRECTED,
    DIRECTION_UNDIRECTED,
    Graph,
    generate_random_graph,
)
from results_panel import ResultsPanel, RunRecord

DEFAULT_GRAPH_PATH = Path(__file__).parent / "data" / "default_graph.json"

BASE_INTERVAL_MS = 500
SPEEDS = [0.5, 1.0, 2.0, 4.0]

ORDER_LABELS = {
    "Insertion order": "insertion",
    "Reverse insertion order": "reverse_insertion",
    "Ascending ID": "ascending",
    "Descending ID": "descending",
}


class RandomGraphDialog(QDialog):
    def __init__(self, parent=None) -> None:
        """Dialog for generating a random graph.

        Options:
            Nodes: Number of nodes in the graph
            Edges: Number of edges in the graph
            Tree mode: Generate a tree-like graph (no cross-branch edges)
            Directed edges: Percentage of directed edges
        """

        super().__init__(parent)
        self.setWindowTitle("Generate Random Graph")
        layout = QFormLayout(self)

        self.node_spin = QSpinBox()
        self.node_spin.setRange(2, 500)
        self.node_spin.setValue(30)
        layout.addRow("Nodes:", self.node_spin)

        self.edge_spin = QSpinBox()
        self.edge_spin.setRange(1, 2000)
        self.edge_spin.setValue(36)
        layout.addRow("Edges:", self.edge_spin)

        self.tree_check = QCheckBox("Tree mode (no cross-branch edges)")
        self.tree_check.toggled.connect(self.edge_spin.setDisabled)
        layout.addRow(self.tree_check)

        self.directed_spin = QDoubleSpinBox()
        self.directed_spin.setRange(0, 100)
        self.directed_spin.setValue(20)
        self.directed_spin.setSuffix(" %")
        layout.addRow("Directed edges:", self.directed_spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def values(self) -> dict:
        return {
            "n_nodes": self.node_spin.value(),
            "n_edges": self.edge_spin.value(),
            "tree_mode": self.tree_check.isChecked(),
            "percent_directed": self.directed_spin.value(),
        }


class MainWindow(QMainWindow):
    def __init__(self, graph: Graph) -> None:
        super().__init__()
        self.setWindowTitle("Ariadne's Thread Desktop")
        self.resize(1200, 800)

        self.graph = graph
        self.scene = GraphScene(self.graph)
        self.view = GraphView(self.scene)
        self.setCentralWidget(self.view)

        self.animation = AnimationController(self)
        self.animation.step_shown.connect(self.scene.render_state)
        self.animation.finished.connect(self.on_finished)
        # `pending_record_meta` contains Algorithm, order, start, target
        self.pending_record_meta: tuple[str, str, int, int] | None = None

        self.results_panel = ResultsPanel(self)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.results_panel)

        self.current_algorithm = next(iter(ALGORITHMS))  # Get the first algorithm
        self.current_order = ORDER_LABELS[
            next(iter(ORDER_LABELS))
        ]  # Get the first order

        self.build_side_panel()
        self.build_menu_bar()
        self.setStatusBar(QStatusBar())
        self.connect_scene_signals()
        self.scene.set_mode(
            self.scene.mode
        )  # emit the initial mode hint now a listener exists
        self.scene.render_idle()

    def build_menu_bar(self) -> None:
        view_menu = self.menuBar().addMenu("View")
        view_menu.addAction(self.controls_dock.toggleViewAction())
        view_menu.addAction(self.results_panel.toggleViewAction())

    def build_side_panel(self) -> None:
        panel = QDockWidget("Controls", self)
        self.controls_dock = panel
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        layout.addWidget(self.build_edit_mode_box())
        layout.addWidget(self.build_selection_box())
        layout.addWidget(self.build_search_box())
        layout.addWidget(self.build_playback_box())
        layout.addWidget(self.build_graph_box())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        scroll.setMinimumWidth(250)
        panel.setWidget(scroll)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, panel)

    def build_edit_mode_box(self) -> QGroupBox:
        box = QGroupBox("Edit Mode")
        box_layout = QVBoxLayout(box)
        mode_group = QButtonGroup(self)
        mode_group.setExclusive(True)
        for mode, text in [
            (EditMode.SELECT, "Select"),
            (EditMode.ADD_NODE, "Add Node"),
            (EditMode.ADD_EDGE, "Add Edge"),
        ]:
            btn = QToolButton()
            btn.setText(text)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, m=mode: self.scene.set_mode(m))
            mode_group.addButton(btn)
            box_layout.addWidget(btn)
            if mode == EditMode.SELECT:
                btn.setChecked(True)
        self.directed_checkbox = QCheckBox("New edges: Directed")
        self.directed_checkbox.toggled.connect(self.set_new_edge_directed)
        box_layout.addWidget(self.directed_checkbox)
        return box

    def build_selection_box(self) -> QGroupBox:
        box = QGroupBox("Selected Node/Edge")
        box_layout = QVBoxLayout(box)
        start_btn = QPushButton("Set as Start")
        start_btn.clicked.connect(self.set_selected_as_start)
        box_layout.addWidget(start_btn)
        target_btn = QPushButton("Set as Target")
        target_btn.clicked.connect(self.set_selected_as_target)
        box_layout.addWidget(target_btn)
        cycle_btn = QPushButton("Cycle Edge Type")
        cycle_btn.setToolTip("Undirected <-> Directed")
        cycle_btn.clicked.connect(self.cycle_direction_selected)
        box_layout.addWidget(cycle_btn)
        reverse_btn = QPushButton("Reverse Edge Direction")
        reverse_btn.clicked.connect(self.reverse_direction_selected)
        box_layout.addWidget(reverse_btn)
        delete_btn = QPushButton("Delete Selected")
        delete_btn.clicked.connect(self.delete_selected)
        box_layout.addWidget(delete_btn)
        return box

    def build_search_box(self) -> QGroupBox:
        box = QGroupBox("Search")
        box_layout = QFormLayout(box)
        self.algorithm_combo = QComboBox()
        self.algorithm_combo.addItems(list(ALGORITHMS.keys()))
        self.algorithm_combo.currentTextChanged.connect(self.set_algorithm)
        box_layout.addRow("Algorithm:", self.algorithm_combo)
        self.order_combo = QComboBox()
        self.order_combo.addItems(list(ORDER_LABELS.keys()))
        self.order_combo.currentTextChanged.connect(self.set_order)
        box_layout.addRow("Order:", self.order_combo)
        self.start_label = QLabel("Start: -")
        self.target_label = QLabel("Target: -")
        box_layout.addRow(self.start_label)
        box_layout.addRow(self.target_label)
        swap_btn = QPushButton("Swap Start/Target")
        swap_btn.clicked.connect(self.swap_start_target)
        box_layout.addRow(swap_btn)
        run_btn = QPushButton("Run")
        run_btn.clicked.connect(self.run_search)
        box_layout.addRow(run_btn)
        return box

    def build_playback_box(self) -> QGroupBox:
        box = QGroupBox("Playback")
        box_layout = QVBoxLayout(box)
        self.play_btn = QPushButton("Play")
        self.play_btn.clicked.connect(self.toggle_play)
        box_layout.addWidget(self.play_btn)

        step_row = QHBoxLayout()
        step_back_btn = QPushButton("Step Back")
        step_back_btn.clicked.connect(self.step_back)
        step_row.addWidget(step_back_btn)
        step_btn = QPushButton("Step")
        step_btn.clicked.connect(self.step_forward)
        step_row.addWidget(step_btn)
        box_layout.addLayout(step_row)

        reset_btn = QPushButton("Reset")
        reset_btn.clicked.connect(self.reset_animation)
        box_layout.addWidget(reset_btn)

        self.speed_index = SPEEDS.index(1.0)
        self.speed_btn = QPushButton()
        self.speed_btn.clicked.connect(self.cycle_speed)
        box_layout.addWidget(self.speed_btn)
        self.apply_speed()
        return box

    def build_graph_box(self) -> QGroupBox:
        box = QGroupBox("Graph")
        box_layout = QVBoxLayout(box)
        load_default_btn = QPushButton("Load Default")
        load_default_btn.clicked.connect(self.load_default_graph)
        box_layout.addWidget(load_default_btn)
        load_btn = QPushButton("Load...")
        load_btn.clicked.connect(self.load_graph)
        box_layout.addWidget(load_btn)
        save_btn = QPushButton("Save...")
        save_btn.clicked.connect(self.save_graph)
        box_layout.addWidget(save_btn)
        random_btn = QPushButton("Generate Random...")
        random_btn.clicked.connect(self.open_random_graph_dialog)
        box_layout.addWidget(random_btn)
        clear_btn = QPushButton("Clear Graph")
        clear_btn.clicked.connect(self.clear_graph)
        box_layout.addWidget(clear_btn)
        return box

    def connect_scene_signals(self) -> None:
        self.scene.start_set.connect(self.on_start_set)
        self.scene.target_set.connect(self.on_target_set)
        self.scene.status_message.connect(self.statusBar().showMessage)

    def set_algorithm(self, text: str) -> None:
        self.current_algorithm = text

    def set_order(self, text: str) -> None:
        self.current_order = ORDER_LABELS[text]

    def on_start_set(self, node_id: int) -> None:
        self.start_label.setText(f"Start: {node_id}")

    def on_target_set(self, node_id: int) -> None:
        self.target_label.setText(f"Target: {node_id}")

    def swap_start_target(self) -> None:
        start, target = self.scene.start_id, self.scene.target_id
        if start is None or target is None:
            QMessageBox.information(
                self, "Swap Start/Target", "Set both a start and a target node first."
            )
            return
        self.scene.set_start(target)
        self.scene.set_target(start)

    def set_selected_as_start(self) -> None:
        node = self.scene.selected_node()
        if node is None:
            QMessageBox.information(
                self, "Set as Start", "Select exactly one node first."
            )
            return
        self.scene.set_start(node.node_id)

    def set_selected_as_target(self) -> None:
        node = self.scene.selected_node()
        if node is None:
            QMessageBox.information(
                self, "Set as Target", "Select exactly one node first."
            )
            return
        self.scene.set_target(node.node_id)

    def set_new_edge_directed(self, checked: bool) -> None:
        self.scene.new_edge_direction = (
            DIRECTION_DIRECTED if checked else DIRECTION_UNDIRECTED
        )

    def cycle_direction_selected(self) -> None:
        if not self.scene.selected_edges():
            QMessageBox.information(self, "Cycle Edge Type", "Select an edge first.")
            return
        self.scene.cycle_direction_selected()

    def reverse_direction_selected(self) -> None:
        if not self.scene.selected_edges():
            QMessageBox.information(self, "Reverse Direction", "Select an edge first.")
            return
        self.scene.reverse_direction_selected()

    def delete_selected(self) -> None:
        if not self.scene.selectedItems():
            QMessageBox.information(
                self, "Delete Selected", "Select a node or edge first."
            )
            return
        self.scene.delete_selected()

    def run_search(self) -> None:
        start, target = self.scene.start_id, self.scene.target_id
        if start is None or target is None:
            QMessageBox.information(
                self, "Run", "Set both a start and a target node first."
            )
            return
        algorithm = ALGORITHMS[self.current_algorithm]
        steps = list(algorithm(self.graph, start, target, self.current_order))
        self.animation.load(steps)
        self.pending_record_meta = (
            self.current_algorithm,
            self.current_order,
            start,
            target,
        )
        self.animation.play()
        self.play_btn.setText("Pause")

    def toggle_play(self) -> None:
        if self.animation.is_playing():
            self.animation.pause()
            self.play_btn.setText("Play")
        else:
            self.reset_animation()
            self.animation.play()
            self.play_btn.setText("Pause")

    def step_forward(self) -> None:
        self.animation.pause()
        self.play_btn.setText("Play")
        self.animation.step_forward()

    def step_back(self) -> None:
        self.animation.pause()
        self.play_btn.setText("Play")
        self.animation.step_back()

    def cycle_speed(self) -> None:
        self.speed_index = (self.speed_index + 1) % len(SPEEDS)
        self.apply_speed()

    def apply_speed(self) -> None:
        speed = SPEEDS[self.speed_index]
        self.speed_btn.setText(f"Speed: {speed:g}x")
        self.animation.set_speed(round(BASE_INTERVAL_MS / speed))

    def reset_animation(self) -> None:
        self.animation.reset()
        self.play_btn.setText("Play")
        self.scene.render_idle()

    def on_finished(self, found: bool) -> None:
        self.play_btn.setText("Play")
        if self.pending_record_meta is None:
            return
        algorithm, order, start, target = self.pending_record_meta
        self.pending_record_meta = None
        steps = self.animation.steps
        expanded = len(steps[-1].expanded) if steps else 0
        path  = []
        if steps and steps[-1].kind == StepKind.FOUND:
            path = steps[-1].path_so_far
        record = RunRecord(algorithm, order, start, target, found, path or [], expanded)
        self.results_panel.add_run(record)


    def load_default_graph(self) -> None:
        self.replace_graph(Graph.from_json(DEFAULT_GRAPH_PATH))

    def load_graph(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Graph", "", "JSON files (*.json)"
        )
        if not path:
            return
        try:
            self.replace_graph(Graph.from_json(path))
        except Exception as exc:
            QMessageBox.warning(self, "Load failed", str(exc))

    def save_graph(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Graph", "graph.json", "JSON files (*.json)"
        )
        if not path:
            return
        self.graph.to_json(path)

    def open_random_graph_dialog(self) -> None:
        dialog = RandomGraphDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            graph = generate_random_graph(**dialog.values())
        except ValueError as exc:
            QMessageBox.warning(self, "Generate failed", str(exc))
            return
        self.replace_graph(graph)

    def clear_graph(self) -> None:
        answer = QMessageBox.question(
            self,
            "Clear Graph",
            "Discard the current graph and start with an empty canvas?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.replace_graph(Graph())

    def replace_graph(self, graph: Graph) -> None:
        self.animation.reset()
        self.pending_record_meta = None
        self.graph = graph
        self.scene = GraphScene(self.graph)
        self.animation.step_shown.connect(self.scene.render_state)
        self.connect_scene_signals()
        self.view.setScene(self.scene)
        self.start_label.setText("Start: -")
        self.target_label.setText("Target: -")
        self.scene.set_mode(self.scene.mode)
        self.scene.render_idle()
