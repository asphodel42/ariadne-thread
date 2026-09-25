import csv
from dataclasses import dataclass, field
from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


@dataclass
class RunRecord:
    algorithm: str
    order: str
    start: int
    target: int
    found: bool
    path: list[int]
    expanded: int
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%H:%M:%S"))

    @property
    def path_length(self) -> int:
        return max(len(self.path) - 1, 0) if self.found else 0

    def path_label(self) -> str:
        return " -> ".join(str(v) for v in self.path)


class ResultsPanel(QDockWidget):
    def __init__(self, parent=None) -> None:
        super().__init__("Search Results", parent)
        self.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.records: list[RunRecord] = []

        body = QWidget()
        layout = QVBoxLayout(body)

        self.summary_label = QLabel("No search run yet.")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["Time", "Algorithm", "Order", "Start", "Target", "Result", "Expanded"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

        export_button = QPushButton("Export Log to CSV...")
        export_button.clicked.connect(self.export_csv)
        layout.addWidget(export_button)

        self.setWidget(body)

    def add_run(self, record: RunRecord) -> None:
        self.records.append(record)

        label = "path found"
        if record.found:
            text = (
                f"[{record.algorithm}] {label}: {record.path_label()}\n"
                f"length {record.path_length}, expanded {record.expanded} nodes "
                f"(order: {record.order})"
            )
        else:
            text = (
                f"[{record.algorithm}] no path found from {record.start} to {record.target} "
                f"(expanded {record.expanded} nodes, order: {record.order})"
            )
        self.summary_label.setText(text)

        row = self.table.rowCount()
        self.table.insertRow(row)
        values = [
            record.timestamp,
            record.algorithm,
            record.order,
            str(record.start),
            str(record.target),
            record.path_label() if record.found else "no path",
            str(record.expanded),
        ]
        for col, value in enumerate(values):
            self.table.setItem(row, col, QTableWidgetItem(value))

    def export_csv(self) -> None:
        if not self.records:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export Log", "search_log.csv", "CSV files (*.csv)")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["time", "algorithm", "order", "start", "target", "found", "path", "expanded"])
            for r in self.records:
                writer.writerow(
                    [r.timestamp, r.algorithm, r.order, r.start, r.target, r.found, r.path_label(), r.expanded]
                )
