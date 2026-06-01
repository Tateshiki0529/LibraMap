from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
import sys
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
        self._debug = os.getenv("LIBRAMAP_PRINTER_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}

    def connect(
        self,
        vendor_id: int = 0x04B8,
        product_id: int = 0x0202,
        file_path: str | None = None,
        dummy: bool = False,
    ) -> None:
        self._log(
            f"connect(dummy={dummy}, file_path={file_path}, vendor_id={hex(vendor_id)}, product_id={hex(product_id)})"
        )
        self.disconnect()
        if dummy:
            self._set_dummy()
            self._log("mode=dummy")
            return

        if file_path:
            try:
                from escpos.printer import File

                test_printer = File(file_path, profile=RECEIPT_PROFILE)
                test_printer.close()
                self._mode = "file"
                self._file_path = file_path
                self._connection_info = f"Shared printer: {file_path}"
                self._log(f"mode=file, connection={self._connection_info}")
                return
            except Exception as exc:
                self._log(f"file mode connect failed: {exc!r}")
                self._set_dummy()
                return

        if not self._usb_backend_available():
            self._log("usb backend unavailable -> fallback dummy")
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
            self._log(f"mode=usb, connection={self._connection_info}")
        except Exception as exc:
            self._log(f"usb mode connect failed: {exc!r}")
            self._set_dummy()

    def disconnect(self) -> None:
        self._log(f"disconnect(mode={self._mode})")
        if self._printer is not None:
            self._safe_close(self._printer)
        self._printer = None
        self._file_path = None
        self._mode = "unconnected"
        self._connection_info = ""

    def print_image(self, image: Image.Image, save_image: bool = False) -> Path | None:
        self._log(f"print_image(mode={self._mode}, save_image={save_image}, size={image.size})")
        save_path = self._save_image(image) if save_image or self._mode in {"dummy", "unconnected"} else None

        if self._mode == "file" and self._file_path:
            try:
                from escpos.printer import File

                printer = File(self._file_path, profile=RECEIPT_PROFILE)
                printer.image(image)
                self._cut(printer)
                self._safe_close(printer)
            except Exception as exc:
                self._log(f"file print failed: {exc!r}")
                raise PrinterError(f"Shared printer print failed: {exc}") from exc

        elif self._mode == "usb" and self._printer is not None:
            try:
                self._printer.open()
                self._printer.image(image)
                self._cut(self._printer)
                self._safe_close(self._printer)
            except Exception as exc:
                self._log(f"usb print failed: {exc!r}")
                raise PrinterError(f"USB print failed: {exc}") from exc

        self._log(f"print_image complete, save_path={save_path}")
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
        self._log("set dummy mode")

    def _log(self, message: str) -> None:
        if not self._debug:
            return
        now = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[EscPosPrinter {now}] {message}", file=sys.stderr, flush=True)

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

    def _cut(self, printer: Any) -> None:
        # Feed first for 58mm devices that ignore cut near bottom edge.
        try:
            printer.feed(6)
            self._log("cut: feed(6) ok")
        except Exception:
            self._log("cut: feed(6) failed, trying raw newlines")
            try:
                printer._raw(b"\n\n\n\n\n\n")
                self._log("cut: raw newlines ok")
            except Exception:
                self._log("cut: raw newlines failed")

        # Try library cut API first.
        try:
            printer.cut(mode="FULL")
            self._log("cut: cut(mode='FULL') ok")
            return
        except Exception:
            self._log("cut: cut(mode='FULL') failed")

        try:
            printer.cut()
            self._log("cut: cut() ok")
            return
        except Exception:
            self._log("cut: cut() failed")

        # Final fallback: ESC/POS GS V full-cut command.
        if hasattr(printer, "_raw"):
            self._log("cut: trying raw GS V 00")
            printer._raw(b"\x1d\x56\x00")
            self._log("cut: raw GS V 00 sent")
