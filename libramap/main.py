from __future__ import annotations

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
    app = QApplication(sys.argv)
    app.setApplicationName("LibraMap")
    app.setApplicationVersion("0.1.0")

    project_root = Path(__file__).resolve().parents[1]
    data_dir = project_root / "data"
    schema_path = Path(__file__).resolve().parent / "data" / "schema.json"

    floor_data = _load_floor_data(schema_path)

    printer = EscPosPrinter()
    printer.connect(dummy=True)

    window = MainWindow(
        barcode_processor=BarcodeProcessor(),
        local_db=LocalBookDatabase(data_dir / "libramap.db"),
        ndl_api=NdlSearchApi(),
        cache_manager=CacheManager(data_dir / "cache.db"),
        placement_engine=PlacementEngine(floor_data),
        receipt_renderer=ReceiptRenderer(floor_data),
        printer=printer,
        floor_data=floor_data,
    )
    window.show()
    sys.exit(app.exec())


def _load_floor_data(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


if __name__ == "__main__":
    main()
