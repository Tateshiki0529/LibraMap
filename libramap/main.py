"""
libramap.main

LibraMap アプリケーションのエントリーポイント。
各モジュールの初期化と依存関係の注入を行い、メインUIを表示します。

仕様参照: specs.md
"""
import json
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from libramap.core.barcode import BarcodeProcessor
from libramap.core.cache import CacheManager
from libramap.core.local_db import LocalBookDatabase
from libramap.core.ndl_api import NdlSearchApi
from libramap.core.placement_engine import PlacementEngine
from libramap.printing.escpos_printer import EscPosPrinter
from libramap.printing.receipt_renderer import ReceiptRenderer
from libramap.ui.main_window import MainWindow


def main() -> None:
    """
    アプリケーションのメインエントリーポイント。
    """
    app = QApplication(sys.argv)
    app.setApplicationName("LibraMap")
    app.setApplicationVersion("0.1.0")

    # 1. プロジェクト関連パスの定義
    # リポジトリルートを基準にデータベース、キャッシュ、スキーマパスを決定
    base_dir = Path(__file__).parent.resolve()
    project_root = base_dir.parent.resolve()
    
    db_path = project_root / "data" / "libramap.db"
    cache_path = project_root / "data" / "cache.db"
    schema_path = base_dir / "data" / "schema.json"

    # 2. 各制御モジュールの初期化
    local_db = LocalBookDatabase(db_path=db_path)
    cache_manager = CacheManager(cache_path=cache_path)
    ndl_api = NdlSearchApi()
    barcode_processor = BarcodeProcessor()
    receipt_renderer = ReceiptRenderer()

    # 3. プリンタ初期化と接続 (共有プリンタ "\\localhost\RECEIPT" を指定)
    printer = EscPosPrinter()
    printer.connect(file_path=r"\\localhost\RECEIPT")

    # 4. 書架定義JSONのロード
    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            floor_data = json.load(f)
    except Exception as exc:
        print(f"書架スキーマデータのロードに失敗しました (フォールバックデータを使用します): {exc}")
        floor_data = {"floors": []}

    placement_engine = PlacementEngine(floor_data=floor_data)

    # 5. UIの構築と依存関係の注入
    window = MainWindow(
        barcode_processor=barcode_processor,
        local_db=local_db,
        ndl_api=ndl_api,
        cache_manager=cache_manager,
        placement_engine=placement_engine,
        receipt_renderer=receipt_renderer,
        printer=printer,
        floor_data=floor_data
    )
    window.show()

    # アプリケーション正常終了時にプリンタを切断
    try:
        sys.exit(app.exec())
    finally:
        printer.disconnect()


if __name__ == "__main__":
    main()
