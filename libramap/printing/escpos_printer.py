"""
libramap.printing.escpos_printer

ESC/POS 印刷モジュール。

python-escpos ライブラリを使用して 58mm 感熱レシートプリンタへ印刷する。
画像ラスタ印刷方式（specs.md §13.3）を採用する。

仕様参照: specs.md §13
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image

if TYPE_CHECKING:
    pass


class PrinterError(Exception):
    """プリンタ接続・印刷エラーを表す例外クラス。"""


class EscPosPrinter:
    """
    ESC/POS レシートプリンタ制御クラス。

    python-escpos を使用して USB/シリアル接続の感熱レシートプリンタへ印刷する。
    画像ラスタ印刷方式を採用し、Pillow で生成した画像をそのまま送信する。

    実機確認事項（specs.md §20.0.3）:
        - ESC/POS 制御は実機プリンタで必ず検証すること
        - 用紙幅 58mm・感熱ロール紙への適合を確認すること

    使用方法:
        printer = EscPosPrinter()
        printer.connect(vendor_id=0x04b8, product_id=0x0202)
        printer.print_image(image)
        printer.disconnect()
    """

    def __init__(self) -> None:
        """プリンタインスタンスを初期化する。接続は connect() で行う。"""
        self._printer = None

    def connect(self, vendor_id: int, product_id: int) -> None:
        """
        USB 接続のプリンタへ接続する。

        Args:
            vendor_id: USB ベンダー ID（16 進数）
            product_id: USB プロダクト ID（16 進数）

        Raises:
            PrinterError: 接続に失敗した場合
        """
        try:
            from escpos.printer import Usb  # type: ignore[import]
            self._printer = Usb(vendor_id, product_id)
        except Exception as exc:
            raise PrinterError(f"プリンタ接続エラー: {exc}") from exc

    def disconnect(self) -> None:
        """プリンタ接続を切断する。接続されていない場合は何もしない。"""
        if self._printer is not None:
            try:
                self._printer.close()
            except Exception:
                pass
            finally:
                self._printer = None

    def print_image(self, image: Image.Image) -> None:
        """
        Pillow 画像をプリンタへ送信して印刷する（画像ラスタ印刷）。

        Args:
            image: 印刷する Pillow 画像オブジェクト

        Raises:
            PrinterError: プリンタ未接続または印刷失敗の場合
        """
        if self._printer is None:
            raise PrinterError("プリンタが接続されていません。connect() を先に呼び出してください。")

        try:
            self._printer.image(image)
            self._printer.cut()
        except Exception as exc:
            raise PrinterError(f"印刷エラー: {exc}") from exc

    def print_image_from_file(self, image_path: Path) -> None:
        """
        画像ファイルを指定してプリンタへ送信する。

        Args:
            image_path: 印刷する画像ファイルのパス

        Raises:
            PrinterError: ファイル読み込み失敗またはプリンタエラーの場合
        """
        try:
            image = Image.open(image_path)
        except OSError as exc:
            raise PrinterError(f"画像ファイル読み込みエラー: {exc}") from exc

        self.print_image(image)

    def is_connected(self) -> bool:
        """
        プリンタが接続済みかどうかを返す。

        Returns:
            bool: 接続済みの場合 True
        """
        return self._printer is not None
