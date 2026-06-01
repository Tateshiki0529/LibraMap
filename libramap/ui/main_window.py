from __future__ import annotations

from enum import Enum, auto

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QFont, QImage, QKeyEvent, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from libramap.core.barcode import BarcodeType
from libramap.core.placement_engine import PlacementResult
from libramap.printing.receipt_renderer import FloorMapRenderer, ReceiptData


class UIState(Enum):
    WAITING_SCAN = auto()
    WAITING_ISBN_SCAN = auto()


class MainWindow(QMainWindow):
    STYLE_SHEET = """
    QMainWindow, QWidget#central {
        background: #f5f7fb;
        color: #111827;
        font-family: "Meiryo", "Segoe UI", sans-serif;
    }
    QLabel {
        color: #111827;
    }
    QLineEdit {
        background: #ffffff;
        color: #111827;
        border: 2px solid #9ca3af;
        border-radius: 6px;
        padding: 12px 14px;
        font-size: 24px;
    }
    QLineEdit::placeholder {
        color: #6b7280;
    }
    QLineEdit:focus {
        border-color: #2563eb;
    }
    QPushButton, QComboBox {
        background: #ffffff;
        color: #111827;
        border: 1px solid #9ca3af;
        border-radius: 6px;
        padding: 10px 14px;
        font-size: 15px;
    }
    QComboBox QAbstractItemView {
        background: #ffffff;
        color: #111827;
        selection-background-color: #dbeafe;
        selection-color: #111827;
    }
    QPushButton:hover, QComboBox:hover {
        border-color: #2563eb;
    }
    """
    FRAME_BASE = "background:#ffffff;border:2px solid #d1d5db;border-radius:8px;"
    FRAME_OK = "background:#ecfdf5;border:3px solid #059669;border-radius:8px;"
    FRAME_WARN = "background:#fffbeb;border:3px solid #d97706;border-radius:8px;"
    FRAME_ERROR = "background:#fef2f2;border:3px solid #dc2626;border-radius:8px;"
    FRAME_PENDING = "background:#eff6ff;border:3px solid #2563eb;border-radius:8px;"

    def __init__(
        self,
        barcode_processor,
        local_db,
        ndl_api,
        cache_manager,
        placement_engine,
        receipt_renderer,
        printer,
        floor_data: dict,
    ) -> None:
        super().__init__()
        self.setWindowTitle("LibraMap - 蝗ｳ譖ｸ鬢ｨ霑泌唆謾ｯ謠ｴ")
        self.setMinimumSize(1000, 720)

        self._barcode_processor = barcode_processor
        self._local_db = local_db
        self._ndl_api = ndl_api
        self._cache_manager = cache_manager
        self._placement_engine = placement_engine
        self._receipt_renderer = receipt_renderer
        self._printer = printer
        self._floor_data = floor_data
        self._floor_renderer = FloorMapRenderer(floor_data)

        self._state = UIState.WAITING_SCAN
        self._pending_jan: str | None = None

        self._setup_ui()
        self.setStyleSheet(self.STYLE_SHEET)
        self._scan_input.setFocus()

    def _setup_ui(self) -> None:
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)

        main = QVBoxLayout(central)
        main.setContentsMargins(32, 24, 32, 24)
        main.setSpacing(18)

        header = QHBoxLayout()
        title = QLabel("LibraMap 霑泌唆謾ｯ謠ｴ")
        title.setFont(QFont("Meiryo", 26, QFont.Weight.Bold))
        header.addWidget(title)
        header.addStretch(1)

        self._printer_selector = QComboBox()
        self._printer_selector.addItems(["繧ｷ繝溘Η繝ｬ繝ｼ繧ｷ繝ｧ繝ｳ", "蜈ｱ譛峨・繝ｪ繝ｳ繧ｿ", "USB繝励Μ繝ｳ繧ｿ"])
        self._printer_selector.currentIndexChanged.connect(self._on_printer_changed)
        self._printer_status = QLabel(self._printer.get_status_message())
        self._printer_status.setMinimumWidth(220)
        header.addWidget(self._printer_selector)
        header.addWidget(self._printer_status)
        main.addLayout(header)
        self._printer_selector.setCurrentIndex(1)

        self._scan_label = QLabel("ISBN-13 縺ｾ縺溘・ 192邉ｻJAN繧偵せ繧ｭ繝｣繝ｳ縺励※縺上□縺輔＞")
        self._scan_label.setFont(QFont("Meiryo", 16, QFont.Weight.Bold))
        main.addWidget(self._scan_label)

        self._scan_input = QLineEdit()
        self._scan_input.setPlaceholderText("繝舌・繧ｳ繝ｼ繝牙・蜉帛ｾ・Enter")
        self._scan_input.returnPressed.connect(self._on_scan_submitted)
        main.addWidget(self._scan_input)

        self._result_frame = QFrame()
        self._result_frame.setStyleSheet(self.FRAME_BASE)
        frame_layout = QHBoxLayout(self._result_frame)
        frame_layout.setContentsMargins(24, 22, 24, 22)
        frame_layout.setSpacing(24)

        left = QVBoxLayout()
        self._status_title = QLabel("蠕・ｩ滉ｸｭ")
        self._status_title.setFont(QFont("Meiryo", 24, QFont.Weight.Bold))
        self._status_body = QLabel("霑泌唆雉・侭縺ｮ繝舌・繧ｳ繝ｼ繝峨ｒ繧ｹ繧ｭ繝｣繝ｳ縺励※縺上□縺輔＞縲・)
        self._status_body.setFont(QFont("Meiryo", 20))
        self._status_body.setWordWrap(True)
        left.addWidget(self._status_title)
        left.addWidget(self._status_body, 1)
        frame_layout.addLayout(left, 1)

        self._map_label = QLabel()
        self._map_label.setFixedSize(480, 260)
        self._map_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._map_label.setStyleSheet("background:#ffffff;border:1px solid #d1d5db;border-radius:6px;")
        frame_layout.addWidget(self._map_label)
        main.addWidget(self._result_frame, 1)

        buttons = QHBoxLayout()
        self._clear_button = QPushButton("繧ｯ繝ｪ繧｢ (Esc)")
        self._clear_button.clicked.connect(self._on_clear)
        buttons.addWidget(self._clear_button)
        buttons.addStretch(1)
        main.addLayout(buttons)

    @Slot(int)
    def _on_printer_changed(self, index: int) -> None:
        if index == 0:
            self._printer.connect(dummy=True)
        elif index == 1:
            self._printer.connect(file_path=r"\\localhost\RECEIPT")
        else:
            self._printer.connect()
        self._printer_status.setText(self._printer.get_status_message())
        self._scan_input.setFocus()

    @Slot()
    def _on_scan_submitted(self) -> None:
        raw = self._scan_input.text()
        self._scan_input.clear()
        if not raw.strip():
            return

        result = self._barcode_processor.process(raw)
        if self._state == UIState.WAITING_ISBN_SCAN:
            if result.barcode_type != BarcodeType.ISBN13 or not result.isbn:
                self._show_pending("ISBN-13繧偵せ繧ｭ繝｣繝ｳ縺励※縺上□縺輔＞縲ゆｸｭ豁｢縺吶ｋ蝣ｴ蜷医・Esc繧呈款縺励※縺上□縺輔＞縲・)
                return
            self._state = UIState.WAITING_SCAN
            self._pending_jan = None
            self._process_isbn(result.isbn)
            return

        if result.barcode_type == BarcodeType.ISBN13 and result.isbn:
            self._process_isbn(result.isbn)
        elif result.barcode_type == BarcodeType.JAN_192:
            self._state = UIState.WAITING_ISBN_SCAN
            self._pending_jan = result.raw
            self._show_pending("192邉ｻJAN繧貞女縺台ｻ倥￠縺ｾ縺励◆縲らｶ壹￠縺ｦ雉・侭譛ｬ菴薙・ISBN-13繧偵せ繧ｭ繝｣繝ｳ縺励※縺上□縺輔＞縲・)
        elif result.barcode_type == BarcodeType.JAN_OTHER:
            self._show_error("髱槫ｯｾ蠢廱AN縺ｧ縺吶・SBN-13縲√∪縺溘・192邉ｻJAN繧剃ｽｿ逕ｨ縺励※縺上□縺輔＞縲・)
        else:
            self._show_error("繝舌・繧ｳ繝ｼ繝峨ｒ蛻､螳壹〒縺阪∪縺帙ｓ縲りｪｭ縺ｿ蜿悶ｊ蜀・ｮｹ繧堤｢ｺ隱阪＠縺ｦ縺上□縺輔＞縲・)

    def _process_isbn(self, isbn: str) -> None:
        record = self._local_db.find_by_isbn(isbn)
        info = None

        if record is None:
            try:
                info = self._ndl_api.search_by_isbn(isbn)
                self._cache_manager.set(info.isbn, info.title, info.creator, info.ndc, info.publisher)
            except Exception:
                cached = self._cache_manager.get(isbn)
                if cached:
                    info = cached

            title = getattr(info, "title", "") or "譛ｪ逋ｻ骭ｲ雉・侭"
            creator = getattr(info, "creator", "")
            ndc = getattr(info, "ndc", "")
            placement = PlacementResult(
                found=False,
                message="鬢ｨ蜀・鳩譖ｸDB縺ｫ譛ｪ逋ｻ骭ｲ縺ｧ縺吶ら嶌莠貞茜逕ｨ繝ｻ譛ｪ逋ｻ骭ｲ雉・侭縺ｮ蜿ｯ閭ｽ諤ｧ縺後≠繧翫∪縺吶・,
            )
            receipt_data = ReceiptData(title, creator, isbn, ndc, placement)
            save_path = self._printer.print_image(self._receipt_renderer.render(receipt_data), save_image=True)
            suffix = f"\n繝ｬ繧ｷ繝ｼ繝育判蜒・ {save_path.name}" if save_path else ""
            self._show_error(
                f"蟇ｾ雎｡螟冶ｳ・侭縺ｧ縺吶・nISBN: {isbn}\n譖ｸ蜷・ {title}\n隕∵焔蜍戊ｿ泌唆遒ｺ隱阪・suffix}"
            )
            return

        title = record.title
        creator = record.creator
        ndc = record.ndc

        if not title or not ndc:
            cached = self._cache_manager.get(isbn)
            if cached:
                title = title or cached.title
                creator = creator or cached.creator
                ndc = ndc or cached.ndc
            else:
                try:
                    info = self._ndl_api.search_by_isbn(isbn)
                    self._cache_manager.set(info.isbn, info.title, info.creator, info.ndc, info.publisher)
                    title = title or info.title
                    creator = creator or info.creator
                    ndc = ndc or info.ndc
                except Exception:
                    pass

        placement = self._placement_engine.determine(ndc, record.is_restricted)
        rows, cols = self._get_shelf_size(placement.segment.shelf_id) if placement.segment else (5, 8)
        receipt_data = ReceiptData(
            title=title or "譖ｸ蜷堺ｸ肴・",
            creator=creator,
            isbn=isbn,
            ndc=ndc,
            placement=placement,
            shelf_rows=rows,
            shelf_cols=cols,
        )
        save_path = self._printer.print_image(self._receipt_renderer.render(receipt_data))

        if placement.is_restricted:
            floor_id = self._first_floor_with_type("restricted") or "1f"
            self._display_map(self._floor_renderer.render(floor_id, highlight_restricted=True))
            self._show_warning(f"{title}\n{placement.message}")
        elif placement.found and placement.segment:
            self._display_map(
                self._floor_renderer.render(
                    placement.segment.floor_id,
                    highlight_shelf_id=placement.segment.shelf_id,
                    highlight_segment=placement.segment,
                )
            )
            suffix = f"\n繝ｬ繧ｷ繝ｼ繝育判蜒・ {save_path.name}" if save_path else ""
            self._show_success(f"{title}\nNDC: {ndc}\n霑泌唆蜈・ {placement.message}{suffix}")
        else:
            suffix = f"\n繝ｬ繧ｷ繝ｼ繝育判蜒・ {save_path.name}" if save_path else ""
            self._map_label.clear()
            self._show_error(f"{title}\n{placement.message}{suffix}")

        self._printer_status.setText(self._printer.get_status_message())

    def _get_shelf_size(self, shelf_id: str) -> tuple[int, int]:
        for floor in self._floor_data.get("floors", []):
            for obj in floor.get("objects", []):
                if obj.get("type") == "shelf" and obj.get("id") == shelf_id:
                    return int(obj.get("rows", 5)), int(obj.get("cols", 8))
        return 5, 8

    def _first_floor_with_type(self, obj_type: str) -> str | None:
        for floor in self._floor_data.get("floors", []):
            if any(obj.get("type") == obj_type for obj in floor.get("objects", [])):
                return floor.get("id")
        return None

    def _display_map(self, image) -> None:
        rgb = image.convert("RGB")
        data = rgb.tobytes("raw", "RGB")
        qimage = QImage(data, rgb.width, rgb.height, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qimage).scaled(
            self._map_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._map_label.setPixmap(pixmap)

    def _show_success(self, message: str) -> None:
        self._result_frame.setStyleSheet(self.FRAME_OK)
        self._status_title.setText("霑泌唆蜈医ｒ蛻､螳壹＠縺ｾ縺励◆")
        self._status_body.setText(message)

    def _show_warning(self, message: str) -> None:
        self._result_frame.setStyleSheet(self.FRAME_WARN)
        self._status_title.setText("遖∝ｸｯ蜃ｺ雉・侭")
        self._status_body.setText(message)

    def _show_error(self, message: str) -> None:
        self._result_frame.setStyleSheet(self.FRAME_ERROR)
        self._status_title.setText("隕∵焔蜍慕｢ｺ隱・)
        self._status_body.setText(message)
        self._map_label.clear()

    def _show_pending(self, message: str) -> None:
        self._result_frame.setStyleSheet(self.FRAME_PENDING)
        self._status_title.setText("霑ｽ蜉繧ｹ繧ｭ繝｣繝ｳ蠕・■")
        self._status_body.setText(message)
        self._map_label.clear()

    @Slot()
    def _on_clear(self) -> None:
        self._state = UIState.WAITING_SCAN
        self._pending_jan = None
        self._scan_input.clear()
        self._result_frame.setStyleSheet(self.FRAME_BASE)
        self._status_title.setText("蠕・ｩ滉ｸｭ")
        self._status_body.setText("霑泌唆雉・侭縺ｮ繝舌・繧ｳ繝ｼ繝峨ｒ繧ｹ繧ｭ繝｣繝ｳ縺励※縺上□縺輔＞縲・)
        self._map_label.clear()
        self._scan_input.setFocus()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self._on_clear()
            return
        super().keyPressEvent(event)


