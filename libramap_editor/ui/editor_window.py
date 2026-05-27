from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from libramap.printing.receipt_renderer import FloorMapRenderer
from libramap_editor.model import OBJECT_TYPES, MapDataError, ShelfMapDocument


class EditorWindow(QMainWindow):
    STYLE_SHEET = """
    QMainWindow, QWidget#central {
        background: #f5f7fb;
        color: #111827;
        font-family: "Meiryo", "Segoe UI", sans-serif;
    }
    QLabel {
        color: #111827;
    }
    QLineEdit, QSpinBox, QComboBox, QListWidget, QTableWidget {
        background: #ffffff;
        color: #111827;
        border: 1px solid #9ca3af;
        border-radius: 4px;
        padding: 4px;
    }
    QPushButton {
        background: #ffffff;
        color: #111827;
        border: 1px solid #9ca3af;
        border-radius: 4px;
        padding: 8px 12px;
    }
    QPushButton:hover {
        border-color: #2563eb;
    }
    """

    def __init__(self, document: ShelfMapDocument) -> None:
        super().__init__()
        self._document = document
        self._selected_floor_id: str | None = None
        self._selected_object_id: str | None = None
        self._loading = False

        self.setWindowTitle("LibraMap Editor")
        self.setMinimumSize(1180, 760)
        self._setup_ui()
        self.setStyleSheet(self.STYLE_SHEET)
        self._refresh_all()

    def _setup_ui(self) -> None:
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)

        root.addLayout(self._build_toolbar())

        body = QHBoxLayout()
        body.setSpacing(14)
        body.addLayout(self._build_left_panel(), 0)
        body.addLayout(self._build_center_panel(), 1)
        body.addLayout(self._build_right_panel(), 0)
        root.addLayout(body, 1)

        self._status_label = QLabel("")
        root.addWidget(self._status_label)

    def _build_toolbar(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        title = QLabel("LibraMap Editor")
        title.setStyleSheet("font-size: 24px; font-weight: 700;")
        layout.addWidget(title)
        layout.addStretch(1)

        self._open_button = QPushButton("開く")
        self._open_button.clicked.connect(self._open_file)
        self._save_button = QPushButton("保存")
        self._save_button.clicked.connect(self._save_file)
        self._save_as_button = QPushButton("別名保存")
        self._save_as_button.clicked.connect(self._save_file_as)
        self._validate_button = QPushButton("検証")
        self._validate_button.clicked.connect(self._validate_document)

        layout.addWidget(self._open_button)
        layout.addWidget(self._save_button)
        layout.addWidget(self._save_as_button)
        layout.addWidget(self._validate_button)
        return layout

    def _build_left_panel(self) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setSpacing(8)

        floor_header = QHBoxLayout()
        floor_header.addWidget(QLabel("フロア"))
        add_floor = QPushButton("追加")
        add_floor.clicked.connect(self._add_floor)
        delete_floor = QPushButton("削除")
        delete_floor.clicked.connect(self._delete_floor)
        floor_header.addWidget(add_floor)
        floor_header.addWidget(delete_floor)
        layout.addLayout(floor_header)

        self._floor_list = QListWidget()
        self._floor_list.currentItemChanged.connect(self._on_floor_selected)
        layout.addWidget(self._floor_list, 1)

        object_header = QHBoxLayout()
        object_header.addWidget(QLabel("オブジェクト"))
        add_object = QPushButton("追加")
        add_object.clicked.connect(self._add_object)
        delete_object = QPushButton("削除")
        delete_object.clicked.connect(self._delete_object)
        object_header.addWidget(add_object)
        object_header.addWidget(delete_object)
        layout.addLayout(object_header)

        self._object_list = QListWidget()
        self._object_list.currentItemChanged.connect(self._on_object_selected)
        layout.addWidget(self._object_list, 2)
        return layout

    def _build_center_panel(self) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.addWidget(QLabel("プレビュー"))

        self._preview = QLabel()
        self._preview.setMinimumSize(640, 360)
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setStyleSheet("background:#ffffff;border:1px solid #d1d5db;border-radius:6px;")
        layout.addWidget(self._preview, 1)
        return layout

    def _build_right_panel(self) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setSpacing(10)

        object_frame = QFrame()
        object_frame.setFrameShape(QFrame.Shape.StyledPanel)
        form = QFormLayout(object_frame)

        self._object_id = QLineEdit()
        self._object_id.editingFinished.connect(self._apply_object_form)
        self._object_type = QComboBox()
        self._object_type.addItems(list(OBJECT_TYPES))
        self._object_type.currentTextChanged.connect(self._apply_object_form)
        self._x = self._spin(0, 5000)
        self._y = self._spin(0, 5000)
        self._width = self._spin(1, 5000)
        self._height = self._spin(1, 5000)
        self._rows = self._spin(1, 50)
        self._cols = self._spin(1, 50)

        for spin in (self._x, self._y, self._width, self._height, self._rows, self._cols):
            spin.valueChanged.connect(self._apply_object_form)

        form.addRow("ID", self._object_id)
        form.addRow("種別", self._object_type)
        form.addRow("X", self._x)
        form.addRow("Y", self._y)
        form.addRow("幅", self._width)
        form.addRow("高さ", self._height)
        form.addRow("段数", self._rows)
        form.addRow("列数", self._cols)
        layout.addWidget(object_frame)

        segment_header = QHBoxLayout()
        segment_header.addWidget(QLabel("NDC範囲"))
        add_segment = QPushButton("行追加")
        add_segment.clicked.connect(self._add_segment)
        delete_segment = QPushButton("行削除")
        delete_segment.clicked.connect(self._delete_segment)
        segment_header.addWidget(add_segment)
        segment_header.addWidget(delete_segment)
        layout.addLayout(segment_header)

        self._segments = QTableWidget(0, 5)
        self._segments.setHorizontalHeaderLabels(["段", "開始列", "終了列", "NDC開始", "NDC終了"])
        self._segments.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._segments.itemChanged.connect(self._apply_segment_table)
        layout.addWidget(self._segments, 1)
        return layout

    @staticmethod
    def _spin(minimum: int, maximum: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        return spin

    def _refresh_all(self) -> None:
        self._loading = True
        self._floor_list.clear()
        for floor in self._document.floors():
            item = QListWidgetItem(f"{floor.get('name', floor.get('id'))} ({floor.get('id')})")
            item.setData(Qt.ItemDataRole.UserRole, floor.get("id"))
            self._floor_list.addItem(item)
            if self._selected_floor_id == floor.get("id"):
                self._floor_list.setCurrentItem(item)

        if self._floor_list.count() and self._floor_list.currentItem() is None:
            self._floor_list.setCurrentRow(0)
        self._loading = False
        self._refresh_objects()
        self._refresh_preview()
        self._set_status()

    def _refresh_objects(self) -> None:
        self._loading = True
        self._object_list.clear()
        if self._selected_floor_id:
            for obj in self._document.objects(self._selected_floor_id):
                item = QListWidgetItem(f"{obj.get('id')} [{obj.get('type')}]")
                item.setData(Qt.ItemDataRole.UserRole, obj.get("id"))
                self._object_list.addItem(item)
                if self._selected_object_id == obj.get("id"):
                    self._object_list.setCurrentItem(item)
        if self._object_list.count() and self._object_list.currentItem() is None:
            self._object_list.setCurrentRow(0)
        self._loading = False
        self._refresh_object_form()

    def _refresh_object_form(self) -> None:
        self._loading = True
        obj = self._current_object()
        enabled = obj is not None
        for widget in (self._object_id, self._object_type, self._x, self._y, self._width, self._height, self._rows, self._cols, self._segments):
            widget.setEnabled(enabled)

        if obj is None:
            self._object_id.clear()
            self._segments.setRowCount(0)
            self._loading = False
            return

        self._object_id.setText(str(obj.get("id", "")))
        self._object_type.setCurrentText(str(obj.get("type", "shelf")))
        self._x.setValue(int(obj.get("x", 0)))
        self._y.setValue(int(obj.get("y", 0)))
        self._width.setValue(int(obj.get("width", 1)))
        self._height.setValue(int(obj.get("height", 1)))
        self._rows.setValue(int(obj.get("rows", 5)))
        self._cols.setValue(int(obj.get("cols", 8)))
        is_shelf = obj.get("type") == "shelf"
        self._rows.setEnabled(is_shelf)
        self._cols.setEnabled(is_shelf)
        self._segments.setEnabled(is_shelf)
        self._refresh_segments(obj)
        self._loading = False

    def _refresh_segments(self, obj: dict) -> None:
        self._segments.blockSignals(True)
        segments = obj.get("segments", []) if obj.get("type") == "shelf" else []
        self._segments.setRowCount(len(segments))
        for row_index, segment in enumerate(segments):
            values = [
                segment.get("row", 0),
                segment.get("col_start", 0),
                segment.get("col_end", 0),
                segment.get("ndc_start", ""),
                segment.get("ndc_end", ""),
            ]
            for col_index, value in enumerate(values):
                self._segments.setItem(row_index, col_index, QTableWidgetItem(str(value)))
        self._segments.blockSignals(False)

    def _refresh_preview(self) -> None:
        if not self._selected_floor_id:
            self._preview.clear()
            return
        renderer = FloorMapRenderer(self._document.clone_data())
        image = renderer.render(self._selected_floor_id, highlight_shelf_id=self._selected_object_id)
        rgb = image.convert("RGB")
        qimage = QImage(rgb.tobytes("raw", "RGB"), rgb.width, rgb.height, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qimage).scaled(
            self._preview.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._preview.setPixmap(pixmap)

    def _current_object(self) -> dict | None:
        if not self._selected_floor_id or not self._selected_object_id:
            return None
        return self._document.object_by_id(self._selected_floor_id, self._selected_object_id)

    @Slot()
    def _open_file(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, "書架JSONを開く", "", "JSON (*.json)")
        if not filename:
            return
        try:
            self._document = ShelfMapDocument.load(Path(filename))
            self._selected_floor_id = None
            self._selected_object_id = None
            self._refresh_all()
        except Exception as exc:
            self._show_error(str(exc))

    @Slot()
    def _save_file(self) -> None:
        try:
            self._document.save()
            self._set_status("保存しました。")
        except Exception as exc:
            self._show_error(str(exc))

    @Slot()
    def _save_file_as(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(self, "書架JSONを保存", "", "JSON (*.json)")
        if not filename:
            return
        try:
            self._document.save(Path(filename))
            self._set_status("保存しました。")
        except Exception as exc:
            self._show_error(str(exc))

    @Slot()
    def _validate_document(self) -> None:
        issues = self._document.validate()
        if not issues:
            QMessageBox.information(self, "検証", "問題はありません。")
            return
        QMessageBox.warning(self, "検証", "\n".join(f"{issue.path}: {issue.message}" for issue in issues))

    @Slot()
    def _add_floor(self) -> None:
        index = self._floor_list.count() + 1
        try:
            floor = self._document.add_floor(f"{index}f", f"{index}階")
            self._selected_floor_id = floor["id"]
            self._selected_object_id = None
            self._refresh_all()
        except MapDataError as exc:
            self._show_error(str(exc))

    @Slot()
    def _delete_floor(self) -> None:
        if not self._selected_floor_id:
            return
        self._document.delete_floor(self._selected_floor_id)
        self._selected_floor_id = None
        self._selected_object_id = None
        self._refresh_all()

    @Slot()
    def _add_object(self) -> None:
        if not self._selected_floor_id:
            return
        obj_type = "shelf"
        obj_id = self._next_object_id(obj_type)
        try:
            obj = self._document.add_object(self._selected_floor_id, obj_type, obj_id)
            self._selected_object_id = obj["id"]
            self._refresh_objects()
            self._refresh_preview()
        except MapDataError as exc:
            self._show_error(str(exc))

    @Slot()
    def _delete_object(self) -> None:
        if not self._selected_floor_id or not self._selected_object_id:
            return
        self._document.delete_object(self._selected_floor_id, self._selected_object_id)
        self._selected_object_id = None
        self._refresh_objects()
        self._refresh_preview()

    @Slot(QListWidgetItem, QListWidgetItem)
    def _on_floor_selected(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if self._loading or current is None:
            return
        self._selected_floor_id = current.data(Qt.ItemDataRole.UserRole)
        self._selected_object_id = None
        self._refresh_objects()
        self._refresh_preview()

    @Slot(QListWidgetItem, QListWidgetItem)
    def _on_object_selected(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if self._loading or current is None:
            return
        self._selected_object_id = current.data(Qt.ItemDataRole.UserRole)
        self._refresh_object_form()
        self._refresh_preview()

    @Slot()
    def _apply_object_form(self) -> None:
        if self._loading or not self._selected_floor_id or not self._selected_object_id:
            return
        try:
            obj = self._document.update_object(
                self._selected_floor_id,
                self._selected_object_id,
                {
                    "id": self._object_id.text(),
                    "type": self._object_type.currentText(),
                    "x": self._x.value(),
                    "y": self._y.value(),
                    "width": self._width.value(),
                    "height": self._height.value(),
                    "rows": self._rows.value(),
                    "cols": self._cols.value(),
                },
            )
            self._selected_object_id = obj["id"]
            self._refresh_objects()
            self._refresh_preview()
        except Exception as exc:
            self._show_error(str(exc))
            self._refresh_object_form()

    @Slot()
    def _add_segment(self) -> None:
        if not self._selected_floor_id or not self._selected_object_id:
            return
        try:
            self._document.add_segment(self._selected_floor_id, self._selected_object_id, 0, 0, 0, "000", "099")
            self._refresh_object_form()
        except Exception as exc:
            self._show_error(str(exc))

    @Slot()
    def _delete_segment(self) -> None:
        row = self._segments.currentRow()
        if row < 0 or not self._selected_floor_id or not self._selected_object_id:
            return
        self._document.delete_segment(self._selected_floor_id, self._selected_object_id, row)
        self._refresh_object_form()

    @Slot(QTableWidgetItem)
    def _apply_segment_table(self, item: QTableWidgetItem) -> None:
        if self._loading or not self._selected_floor_id or not self._selected_object_id:
            return
        row = item.row()
        try:
            values = {
                "row": self._segments.item(row, 0).text(),
                "col_start": self._segments.item(row, 1).text(),
                "col_end": self._segments.item(row, 2).text(),
                "ndc_start": self._segments.item(row, 3).text(),
                "ndc_end": self._segments.item(row, 4).text(),
            }
            self._document.update_segment(self._selected_floor_id, self._selected_object_id, row, values)
            self._refresh_preview()
        except Exception as exc:
            self._show_error(str(exc))
            self._refresh_object_form()

    def _next_object_id(self, obj_type: str) -> str:
        prefix = {
            "shelf": "S",
            "wall": "wall",
            "stairs": "stairs",
            "elevator": "elevator",
            "desk": "desk",
            "restricted": "restricted",
            "return_box": "return-box",
        }.get(obj_type, "obj")
        existing = {obj.get("id") for obj in self._document.objects(self._selected_floor_id or "")}
        index = 1
        while f"{prefix}-{index:02d}" in existing:
            index += 1
        return f"{prefix}-{index:02d}"

    def _set_status(self, message: str | None = None) -> None:
        path = str(self._document.path) if self._document.path else "未保存"
        self._status_label.setText(message or f"編集中: {path}")

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "エラー", message)
