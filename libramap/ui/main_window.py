"""
libramap.ui.main_window

メインウィンドウモジュール。

PySide6 を使用した返却支援 GUI のメイン画面を提供する。
バーコードスキャナからの入力を受け取り、
蔵書DB照合、NDL API 検索、配架判定、レシート印刷までの一連のフローを制御する。
モダンなダークモード風デザイン（高コントラスト・大型文字）を採用。

仕様参照: specs.md §16, §20.0.5
"""
from __future__ import annotations

from enum import Enum, auto
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QFont, QKeyEvent
from PySide6.QtWidgets import (
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
from libramap.printing.receipt_renderer import ReceiptData

# UIの状態定義
class UIState(Enum):
    WAITING_SCAN = auto()        # 通常のスキャン待ち（ISBNまたはJAN）
    WAITING_ISBN_SCAN = auto()   # 192系JANスキャン後のISBN追加スキャン待ち


class MainWindow(QMainWindow):
    """
    LibraMap メインウィンドウ。

    バーコードスキャナからの入力をトリガーとして、
    返却書籍の配架場所特定およびレシート出力を一括で処理する。
    """

    # モダンなQSSスタイルシート定義
    STYLE_SHEET = """
    QMainWindow {
        background-color: #0b0f19;
    }
    QWidget#central_widget {
        background-color: #0b0f19;
    }
    QLabel {
        color: #f8fafc;
        font-family: "Segoe UI", "Meiryo", sans-serif;
    }
    QLineEdit {
        background-color: #1e293b;
        border: 2px solid #334155;
        border-radius: 8px;
        color: #f8fafc;
        padding: 10px 15px;
        font-size: 22px;
        font-family: "Segoe UI", "Meiryo", sans-serif;
    }
    QLineEdit:focus {
        border: 2px solid #38bdf8;
    }
    QPushButton {
        background-color: #334155;
        color: #f8fafc;
        border: 1px solid #475569;
        border-radius: 8px;
        padding: 12px 24px;
        font-weight: bold;
        font-size: 16px;
        font-family: "Segoe UI", "Meiryo", sans-serif;
    }
    QPushButton:hover {
        background-color: #475569;
    }
    QPushButton:pressed {
        background-color: #1e293b;
    }
    QPushButton#clear_btn {
        background-color: #ef4444;
        color: #ffffff;
        border: none;
    }
    QPushButton#clear_btn:hover {
        background-color: #f87171;
    }
    QPushButton#clear_btn:pressed {
        background-color: #dc2626;
    }
    """

    # 結果表示フレームの異なる状態ごとのスタイル
    FRAME_STYLE_NORMAL = "background-color: #1e293b; border: 2px solid #475569; border-radius: 12px;"
    FRAME_STYLE_SUCCESS = "background-color: #064e3b; border: 2px solid #10b981; border-radius: 12px;"
    FRAME_STYLE_RESTRICTED = "background-color: #78350f; border: 2px solid #f59e0b; border-radius: 12px;"
    FRAME_STYLE_ERROR = "background-color: #7f1d1d; border: 2px solid #f87171; border-radius: 12px;"
    FRAME_STYLE_PENDING = "background-color: #1e1b4b; border: 2px solid #6366f1; border-radius: 12px;"

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
        """
        メインウィンドウを初期化する。

        各制御用モジュールを依存注入により受け取る。
        """
        super().__init__()
        self.setWindowTitle("LibraMap - 図書館返却支援システム")
        self.setMinimumSize(850, 650)

        # 依存モジュールの格納
        self._barcode_processor = barcode_processor
        self._local_db = local_db
        self._ndl_api = ndl_api
        self._cache_manager = cache_manager
        self._placement_engine = placement_engine
        self._receipt_renderer = receipt_renderer
        self._printer = printer
        self._floor_data = floor_data

        # 状態初期化
        self._state = UIState.WAITING_SCAN
        self._pending_jan: str | None = None

        self._setup_ui()
        self.setStyleSheet(self.STYLE_SHEET)
        
        # 初期状態としてフォーカスをスキャン入力欄へ
        self._scan_input.setFocus()

    def _setup_ui(self) -> None:
        """UIコンポーネントの配置と装飾。"""
        central = QWidget()
        central.setObjectName("central_widget")
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(40, 30, 40, 30)

        # ---- ヘッダーエリア ----
        header_layout = QHBoxLayout()
        
        title_label = QLabel("LibraMap 返却支援")
        title_label.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #38bdf8;")
        
        self._printer_status_label = QLabel(self._printer.get_status_message())
        self._printer_status_label.setFont(QFont("Segoe UI", 12))
        self._printer_status_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._printer_status_label.setStyleSheet("color: #94a3b8;")

        header_layout.addWidget(title_label)
        header_layout.addStretch(1)
        header_layout.addWidget(self._printer_status_label)
        main_layout.addLayout(header_layout)

        # ---- スキャン入力エリア ----
        input_container = QVBoxLayout()
        input_container.setSpacing(8)

        self._scan_label = QLabel("書籍のバーコードをスキャンしてください")
        self._scan_label.setFont(QFont("Segoe UI", 16))
        self._scan_label.setStyleSheet("color: #cbd5e1;")

        self._scan_input = QLineEdit()
        self._scan_input.setPlaceholderText("ISBN / JANコードを入力してください...")
        self._scan_input.setFixedHeight(55)
        self._scan_input.returnPressed.connect(self._on_scan_submitted)

        input_container.addWidget(self._scan_label)
        input_container.addWidget(self._scan_input)
        main_layout.addLayout(input_container)

        # ---- 結果表示エリア（大型フレーム） ----
        self._result_frame = QFrame()
        self._result_frame.setStyleSheet(self.FRAME_STYLE_NORMAL)
        self._result_frame.setMinimumHeight(320)
        
        frame_layout = QVBoxLayout(self._result_frame)
        frame_layout.setContentsMargins(25, 25, 25, 25)

        self._result_title_label = QLabel("待機中")
        self._result_title_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self._result_title_label.setStyleSheet("color: #94a3b8;")
        
        self._result_detail_label = QLabel("書籍のバーコードスキャンをお待ちしています。")
        self._result_detail_label.setFont(QFont("Segoe UI", 26, QFont.Weight.Bold))
        self._result_detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._result_detail_label.setWordWrap(True)

        frame_layout.addWidget(self._result_title_label)
        frame_layout.addWidget(self._result_detail_label, 1)
        main_layout.addWidget(self._result_frame)

        # ---- 下部ボタンエリア ----
        button_layout = QHBoxLayout()
        
        self._clear_btn = QPushButton("クリア (Esc)")
        self._clear_btn.setObjectName("clear_btn")
        self._clear_btn.setFixedHeight(50)
        self._clear_btn.clicked.connect(self._on_clear)
        
        button_layout.addWidget(self._clear_btn)
        main_layout.addLayout(button_layout)

    @Slot()
    def _on_scan_submitted(self) -> None:
        """スキャン入力確定時の処理。状態マシンに基づき処理を分岐する。"""
        raw = self._scan_input.text().strip()
        self._scan_input.clear()
        if not raw:
            return

        if self._state == UIState.WAITING_SCAN:
            result = self._barcode_processor.process(raw)
            
            if result.barcode_type == BarcodeType.ISBN13:
                self._process_isbn(result.isbn)
            elif result.barcode_type == BarcodeType.JAN_192:
                # 192系JANを一時保存し、追加スキャン待ちへ移行
                self._pending_jan = raw
                self._state = UIState.WAITING_ISBN_SCAN
                self._show_pending_message(
                    "JANコード（分類・価格）を受理しました。\n"
                    "続けて、書籍のもう一つのバーコード（ISBN-13）をスキャンしてください。"
                )
            elif result.barcode_type == BarcodeType.JAN_OTHER:
                self._show_error_message(
                    "非対応のJANコードです。\n"
                    "978/979から始まるISBNコードをスキャンしてください。"
                )
            else:
                self._show_error_message(
                    "無効な入力コードです。\n"
                    "書籍裏面のバーコードを正しくスキャンしてください。"
                )

        elif self._state == UIState.WAITING_ISBN_SCAN:
            # 追加のISBN-13を待ち受ける状態
            result = self._barcode_processor.process(raw)
            if result.barcode_type == BarcodeType.ISBN13:
                self._state = UIState.WAITING_SCAN
                self._pending_jan = None
                self._process_isbn(result.isbn)
            else:
                self._show_error_message(
                    "追加スキャンに失敗しました。ISBN-13をスキャンしてください。\n"
                    "（クリアするにはEscキーを押してください）"
                )

    def _process_isbn(self, isbn: str) -> None:
        """ISBNコードを元に、蔵書DB照合・API検索・配架判定・印刷を行う中核フロー。"""
        try:
            # 1. ローカル蔵書DBの照合
            record = self._local_db.find_by_isbn(isbn)
            if record is None:
                # 蔵書DB未登録の資料（配架支援対象外）
                self._show_error_message(
                    f"館内蔵書データベースに登録されていません。\n"
                    f"ISBN: {isbn}\n"
                    f"【対象外資料：要手動確認】"
                )
                
                # 対象外資料としてのレシート出力
                from libramap.core.placement_engine import PlacementResult
                dummy_placement = PlacementResult(found=False, message="館内蔵書未登録（対象外）")
                receipt_data = ReceiptData(
                    title="未登録書籍",
                    creator="",
                    isbn=isbn,
                    ndc="",
                    placement=dummy_placement,
                    shelf_rows=5,
                    shelf_cols=8,
                )
                self._printer.print_image(self._receipt_renderer.render(receipt_data))
                return

            # 2. 書誌情報の補完（DB優先、空ならキャッシュ、APIから取得）
            title = record.title
            creator = record.creator
            ndc = record.ndc

            if not title or not ndc:
                # キャッシュから検索
                cached = self._cache_manager.get(isbn)
                if cached:
                    title = title or cached.get("title", "")
                    creator = creator or cached.get("creator", "")
                    ndc = ndc or cached.get("ndc", "")
                else:
                    # NDL Search API経由で取得し、キャッシュへ保存
                    try:
                        ndl_info = self._ndl_api.search_by_isbn(isbn)
                        title = title or ndl_info.title
                        creator = creator or ndl_info.creator
                        ndc = ndc or ndl_info.ndc
                        
                        self._cache_manager.set(
                            isbn=isbn,
                            title=ndl_info.title,
                            creator=ndl_info.creator,
                            ndc=ndl_info.ndc,
                        )
                    except Exception as e:
                        print(f"NDL Search API 取得失敗 (ローカル情報優先): {e}")

            # 3. 配架位置判定
            is_restricted = record.is_restricted
            placement = self._placement_engine.determine(ndc, is_restricted=is_restricted)

            # 4. 書架サイズ（段数・列数）の解決
            rows, cols = 5, 8
            if placement.found and placement.segment:
                rows, cols = self._get_shelf_size(placement.segment.shelf_id)

            # 5. レシート描画と印刷
            receipt_data = ReceiptData(
                title=title or record.title or "書名不明の蔵書",
                creator=creator or record.creator or "",
                isbn=isbn,
                ndc=ndc or record.ndc or "",
                placement=placement,
                shelf_rows=rows,
                shelf_cols=cols,
            )
            
            rendered_image = self._receipt_renderer.render(receipt_data)
            save_path = self._printer.print_image(rendered_image)

            # 6. 画面表示の更新
            self._printer_status_label.setText(self._printer.get_status_message())
            
            # メッセージ構築
            msg = (
                f"【{receipt_data.title}】\n\n"
                f"配架先：{placement.message}\n"
                f"分類番号：{receipt_data.ndc}\n"
                f"レシート保存：{save_path.name}"
            )
            
            if is_restricted:
                self._show_restricted_message(msg)
            else:
                self._show_success_message(msg)

        except Exception as exc:
            self._show_error_message(f"配架処理エラー:\n{exc}")

    def _get_shelf_size(self, shelf_id: str) -> tuple[int, int]:
        """フロアデータから書架オブジェクトを探し、段数と列数を返す。"""
        for floor in self._floor_data.get("floors", []):
            for obj in floor.get("objects", []):
                if obj.get("type") == "shelf" and obj.get("id") == shelf_id:
                    return obj.get("rows", 5), obj.get("cols", 8)
        return 5, 8

    def _show_success_message(self, message: str) -> None:
        """配架特定成功時の表示（グリーン基調）。"""
        self._result_frame.setStyleSheet(self.FRAME_STYLE_SUCCESS)
        self._result_title_label.setText("配架判定完了")
        self._result_title_label.setStyleSheet("color: #10b981;")
        self._result_detail_label.setText(message)

    def _show_restricted_message(self, message: str) -> None:
        """禁帯出資料判定時の表示（オレンジ基調）。"""
        self._result_frame.setStyleSheet(self.FRAME_STYLE_RESTRICTED)
        self._result_title_label.setText("⚠ 禁帯出資料 判定")
        self._result_title_label.setStyleSheet("color: #f59e0b;")
        self._result_detail_label.setText(message)

    def _show_error_message(self, message: str) -> None:
        """エラー時の表示（レッド基調・要手動確認）。"""
        self._result_frame.setStyleSheet(self.FRAME_STYLE_ERROR)
        self._result_title_label.setText("❌ 判定エラー")
        self._result_title_label.setStyleSheet("color: #f87171;")
        self._result_detail_label.setText(f"{message}\n\n要手動確認")

    def _show_pending_message(self, message: str) -> None:
        """追加スキャン入力待ち時の表示（インディゴ基調）。"""
        self._result_frame.setStyleSheet(self.FRAME_STYLE_PENDING)
        self._result_title_label.setText("⏳ 追加スキャン待ち")
        self._result_title_label.setStyleSheet("color: #818cf8;")
        self._result_detail_label.setText(message)

    @Slot()
    def _on_clear(self) -> None:
        """入力と結果をリセットし、初期状態に戻す。"""
        self._scan_input.clear()
        self._state = UIState.WAITING_SCAN
        self._pending_jan = None
        
        self._result_frame.setStyleSheet(self.FRAME_STYLE_NORMAL)
        self._result_title_label.setText("待機中")
        self._result_title_label.setStyleSheet("color: #94a3b8;")
        self._result_detail_label.setText("書籍のバーコードスキャンをお待ちしています。")
        self._scan_input.setFocus()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Escapeキー押下時にクリア処理を呼び出す。"""
        if event.key() == Qt.Key.Key_Escape:
            self._on_clear()
        else:
            super().keyPressEvent(event)
