from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from libramap_editor.model import ShelfMapDocument
from libramap_editor.ui.editor_window import EditorWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("LibraMap Editor")
    app.setApplicationVersion("0.1.0")

    project_root = Path(__file__).resolve().parents[1]
    schema_path = project_root / "libramap" / "data" / "schema.json"
    document = ShelfMapDocument.load(schema_path)

    window = EditorWindow(document)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
