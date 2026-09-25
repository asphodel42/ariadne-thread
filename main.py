from pathlib import Path

from PyQt6.QtWidgets import QApplication

from graph_model import Graph
from main_window import MainWindow

DEFAULT_GRAPH_PATH = Path(__file__).parent / "data" / "default_graph.json"


def main() -> None:
    app = QApplication([])
    graph = Graph.from_json(DEFAULT_GRAPH_PATH)
    window = MainWindow(graph)
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
