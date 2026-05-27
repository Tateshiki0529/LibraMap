from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PIL import Image


class PrinterError(Exception):
    pass


class EscPosPrinter:
    def __init__(self) -> None:
        self._mode = "dummy"
        self._printer = None
        self._file_path: str | None = None
        self._connection_info = "シミュレーション"

    def connect(
        self,
        vendor_id: int = 0x04B8,
        product_id: int = 0x0202,
        file_path: str | None = None,
        dummy: bool = False,
    ) -> None:
        self.disconnect()
        if dummy:
            self._set_dummy()
            return

        if file_path:
            try:
                from escpos.printer import File

                test_printer = File(file_path)
                test_printer.close()
                self._mode = "file"
                self._file_path = file_path
                self._connection_info = f"共有プリンタ: {file_path}"
                return
            except Exception:
                self._set_dummy()
                return

        try:
            from escpos.printer import Usb

            printer = Usb(vendor_id, product_id)
            printer.open()
            printer.close()
            self._printer = printer
            self._mode = "usb"
            self._connection_info = f"USBプリンタ: {hex(vendor_id)}:{hex(product_id)}"
        except Exception:
            self._set_dummy()

    def disconnect(self) -> None:
        if self._printer is not None:
            try:
                self._printer.close()
            except Exception:
                pass
        self._printer = None
        self._file_path = None
        self._mode = "unconnected"
        self._connection_info = ""

    def print_image(self, image: Image.Image, save_image: bool = False) -> Path | None:
        save_path = self._save_image(image) if save_image or self._mode in {"dummy", "unconnected"} else None

        if self._mode == "file" and self._file_path:
            try:
                from escpos.printer import File

                printer = File(self._file_path)
                printer.image(image)
                printer.cut()
                printer.close()
            except Exception as exc:
                raise PrinterError(f"共有プリンタへの印刷に失敗しました: {exc}") from exc
        elif self._mode == "usb" and self._printer is not None:
            try:
                self._printer.image(image)
                self._printer.cut()
            except Exception as exc:
                raise PrinterError(f"USBプリンタへの印刷に失敗しました: {exc}") from exc

        return save_path

    def is_connected(self) -> bool:
        return self._mode != "unconnected"

    def get_status_message(self) -> str:
        if self._mode == "unconnected":
            return "プリンタ未接続"
        if self._mode == "dummy":
            return "シミュレーション中"
        return f"接続中: {self._connection_info}"

    def get_mode(self) -> str:
        return self._mode

    def _set_dummy(self) -> None:
        self._mode = "dummy"
        self._connection_info = "シミュレーション"

    @staticmethod
    def _save_image(image: Image.Image) -> Path:
        output_dir = Path("data") / "receipts"
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"receipt_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.png"
        output_path = output_dir / filename
        image.save(output_path, format="PNG")
        return output_path
