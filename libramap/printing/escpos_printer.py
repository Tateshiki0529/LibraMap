from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image


RECEIPT_PROFILE = "POS-5890"


class PrinterError(Exception):
    pass


class EscPosPrinter:
    def __init__(self) -> None:
        self._mode = "dummy"
        self._printer: Any = None
        self._file_path: str | None = None
        self._connection_info = "Dummy printer"

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

                test_printer = File(file_path, profile=RECEIPT_PROFILE)
                test_printer.close()
                self._mode = "file"
                self._file_path = file_path
                self._connection_info = f"Shared printer: {file_path}"
                return
            except Exception:
                self._set_dummy()
                return

        if not self._usb_backend_available():
            self._set_dummy()
            return

        try:
            from escpos.printer import Usb

            printer = Usb(vendor_id, product_id, profile=RECEIPT_PROFILE)
            printer.open()
            printer.close()
            self._printer = printer
            self._mode = "usb"
            self._connection_info = f"USB printer: {hex(vendor_id)}:{hex(product_id)}"
        except Exception:
            self._set_dummy()

    def disconnect(self) -> None:
        if self._printer is not None:
            self._safe_close(self._printer)
        self._printer = None
        self._file_path = None
        self._mode = "unconnected"
        self._connection_info = ""

    def print_image(self, image: Image.Image, save_image: bool = False) -> Path | None:
        save_path = self._save_image(image) if save_image or self._mode in {"dummy", "unconnected"} else None

        if self._mode == "file" and self._file_path:
            try:
                from escpos.printer import File

                printer = File(self._file_path, profile=RECEIPT_PROFILE)
                printer.image(image)
                self._cut(printer)
                self._safe_close(printer)
            except Exception as exc:
                raise PrinterError(f"Shared printer print failed: {exc}") from exc

        elif self._mode == "usb" and self._printer is not None:
            try:
                self._printer.open()
                self._printer.image(image)
                self._cut(self._printer)
                self._safe_close(self._printer)
            except Exception as exc:
                raise PrinterError(f"USB print failed: {exc}") from exc

        return save_path

    def is_connected(self) -> bool:
        return self._mode != "unconnected"

    def get_status_message(self) -> str:
        if self._mode == "unconnected":
            return "Printer not connected"
        if self._mode == "dummy":
            return "Dummy printer mode"
        return f"Connected: {self._connection_info}"

    def get_mode(self) -> str:
        return self._mode

    def _set_dummy(self) -> None:
        self._mode = "dummy"
        self._connection_info = "Dummy printer"

    @staticmethod
    def _usb_backend_available() -> bool:
        try:
            import usb.backend.libusb1
            import usb.core
        except Exception:
            return False
        return usb.backend.libusb1.get_backend() is not None

    @staticmethod
    def _save_image(image: Image.Image) -> Path:
        output_dir = Path("data") / "receipts"
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"receipt_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.png"
        output_path = output_dir / filename
        image.save(output_path, format="PNG")
        return output_path

    @staticmethod
    def _safe_close(printer: Any) -> None:
        try:
            printer.close()
        except Exception:
            pass

    @staticmethod
    def _cut(printer: Any) -> None:
        # Feed first for 58mm devices that ignore cut near bottom edge.
        try:
            printer.feed(6)
        except Exception:
            try:
                printer._raw(b"\n\n\n\n\n\n")
            except Exception:
                pass

        # Try library cut API first.
        try:
            printer.cut(mode="FULL")
            return
        except Exception:
            pass

        try:
            printer.cut()
            return
        except Exception:
            pass

        # Final fallback: ESC/POS GS V full-cut command.
        if hasattr(printer, "_raw"):
            printer._raw(b"\x1d\x56\x00")
