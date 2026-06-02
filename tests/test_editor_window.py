from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QComboBox, QScrollArea, QSplitter

from libramap_editor.model import ShelfMapDocument
from libramap_editor.ui.editor_window import EditorWindow, ResponsiveNdcRow


class EditorWindowLayoutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_responsive_ndc_row_switches_direction_on_resize(self) -> None:
        row = ResponsiveNdcRow(QComboBox(), QComboBox(), threshold=420)
        row.show()
        row.resize(520, 48)
        self._app.processEvents()
        self.assertEqual(row.layout().direction(), row.layout().Direction.LeftToRight)

        row.resize(280, 72)
        self._app.processEvents()
        self.assertEqual(row.layout().direction(), row.layout().Direction.TopToBottom)

    def test_editor_window_uses_splitter_and_scrollable_right_panel(self) -> None:
        document = ShelfMapDocument.empty()
        document.add_floor("1f", "1F")
        document.add_object("1f", "shelf", "S-01")

        window = EditorWindow(document)
        window.show()
        self._app.processEvents()
        splitter = window.findChild(QSplitter)
        scroll_area = window.findChild(QScrollArea)

        self.assertIsNotNone(splitter)
        self.assertEqual(splitter.count(), 3)
        self.assertIsNotNone(scroll_area)
        self.assertTrue(scroll_area.widgetResizable())


if __name__ == "__main__":
    unittest.main()
