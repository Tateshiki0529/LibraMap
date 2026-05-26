"""
libramap.ui.main_window

メインウィンドウモジュール。

PySide6 を使用した返却支援 GUI のメイン画面を提供する。
バーコードスキャン入力を受け取り、配架判定結果を大型文字で表示する。

UI/UX 方針（specs.md §20.0.5）:
    - 高視認性・大型文字表示
    - 高齢利用者への配慮
    - 直感的操作・低学習コスト
    - 誤操作防止
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QFont, QKeyEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class MainWindow(QMainWindow):
    """
    LibraMap メインウィンドウ。

    バーコードスキャナからの入力を受け取り、
    書架配架判定結果を大型文字で表示する。

    画面構成:
        - スキャン入力エリア（上部）
        - 結果表示エリア（中央・大型文字）
        - 操作ボタン（下部）
    """

    def __init__(self) -> None:
        """メインウィンドウを初期化する。"""
        super().__init__()
        self.setWindowTitle("LibraMap - 図書館返却支援システム")
        self.setMinimumSize(800, 600)

        self._setup_ui()

    def _setup_ui(self) -> None:
        """UI コンポーネントを配置する。"""
        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        # ---- スキャン入力エリア ----
        scan_label = QLabel("バーコードをスキャンしてください")
        scan_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scan_label.setFont(QFont("", 18))

        self._scan_input = QLineEdit()
        self._scan_input.setPlaceholderText("ISBN / JANコードを入力...")
        self._scan_input.setFont(QFont("", 20))
        self._scan_input.setFixedHeight(60)
        self._scan_input.returnPressed.connect(self._on_scan_submitted)

        # ---- 結果表示エリア ----
        self._result_label = QLabel("スキャンをお待ちしています")
        self._result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._result_label.setFont(QFont("", 28, QFont.Weight.Bold))
        self._result_label.setWordWrap(True)
        self._result_label.setMinimumHeight(200)

        # ---- 操作ボタン ----
        button_layout = QHBoxLayout()

        self._clear_button = QPushButton("クリア")
        self._clear_button.setFont(QFont("", 16))
        self._clear_button.setFixedHeight(50)
        self._clear_button.clicked.connect(self._on_clear)

        button_layout.addWidget(self._clear_button)

        # ---- レイアウト組み立て ----
        layout.addWidget(scan_label)
        layout.addWidget(self._scan_input)
        layout.addStretch(1)
        layout.addWidget(self._result_label)
        layout.addStretch(1)
        layout.addLayout(button_layout)

    @Slot()
    def _on_scan_submitted(self) -> None:
        """
        スキャン入力が確定されたときの処理。

        バーコード文字列を取得して配架判定フローを開始する。
        実処理は今後の実装フェーズで追加する。
        """
        raw = self._scan_input.text().strip()
        if not raw:
            return

        # TODO: BarcodeProcessor → LocalBookDatabase → NdlSearchApi →
        #       PlacementEngine → ReceiptRenderer → EscPosPrinter の順で処理
        self._show_result(f"スキャン受付: {raw}\n（配架判定処理は未実装）")
        self._scan_input.clear()

    @Slot()
    def _on_clear(self) -> None:
        """クリアボタン押下時の処理。入力欄と結果表示をリセットする。"""
        self._scan_input.clear()
        self._result_label.setText("スキャンをお待ちしています")
        self._scan_input.setFocus()

    def _show_result(self, message: str) -> None:
        """
        配架判定結果を大型文字で表示する。

        Args:
            message: 表示するメッセージ文字列
        """
        self._result_label.setText(message)

    def _show_error(self, message: str) -> None:
        """
        エラーメッセージを大型文字で強調表示する（specs.md §16.2）。

        Args:
            message: 表示するエラーメッセージ
        """
        self._result_label.setText(f"⚠ {message}\n要手動確認")

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """
        キーボードイベントを処理する。

        Escape キーで入力をクリアして誤操作を防止する。

        Args:
            event: キーイベント
        """
        if event.key() == Qt.Key.Key_Escape:
            self._on_clear()
        else:
            super().keyPressEvent(event)
