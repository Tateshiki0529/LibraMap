"""
libramap.printing.escpos_printer

ESC/POS 印刷モジュール。

python-escpos ライブラリを使用して 58mm 感熱レシートプリンタへ印刷する。
画像ラスタ印刷方式（specs.md §13.3）を採用する。
Windows の共有プリンタ（\\localhost\RECEIPT など）へのファイル接続において、
書き込みバッファによる印刷遅延を解消するため、印刷の都度オープン・クローズ制御を行います。
また、レシート画像は指示された場合、またはシミュレーションモードの時のみローカルに保存します。

仕様参照: specs.md §13
"""
from __future__ import annotations

from datetime import datetime
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

    python-escpos を使用して USB/シリアル/ファイル(共有プリンタ)接続の感熱レシートプリンタへ印刷する。
    画像ラスタ印刷方式を採用し、Pillow で生成した画像をそのまま送信する。

    共有プリンタ（ファイル接続）での書き込みバッファリングによる印刷遅延を防ぐため、
    印刷要求の都度、ファイルを接続・切断（オープン・クローズ）する設計としています。
    """

    def __init__(self) -> None:
        """プリンタインスタンスを初期化する。"""
        self._printer = None
        self._mode = "unconnected"
        self._connection_info = ""
        self._file_path = None

    def connect(
        self,
        vendor_id: int = 0x04b8,
        product_id: int = 0x0202,
        file_path: str | None = None,
        dummy: bool = False,
    ) -> None:
        """
        プリンタへ接続する。

        引数 `dummy=True` の場合はシミュレーションモードとして動作する。
        引数 `file_path` が指定された場合は Windows 共有プリンタ（例: \\\\localhost\\RECEIPT）
        などのファイル出力による接続を試みる。
        指定がない場合は USB 接続を試みる。
        接続に失敗した場合は、ダミーモード（シミュレーション）として動作する。

        Args:
            vendor_id: USB ベンダー ID
            product_id: USB プロダクト ID
            file_path: 共有プリンタのファイルパス（Windows名）
            dummy: シミュレーションモードを強制する場合 True
        """
        self.disconnect()

        # 0. 明示的なシミュレーションモードの指定
        if dummy:
            self._mode = "dummy"
            self._connection_info = "シミュレーションモード"
            return

        # 1. 共有プリンタ（ファイル接続）の試行
        if file_path:
            try:
                from escpos.printer import File  # type: ignore[import]
                # 接続テストのため一時的にオープンして即座にクローズ
                test_printer = File(file_path)
                test_printer.close()
                
                self._mode = "file"
                self._file_path = file_path
                self._connection_info = f"共有プリンタ ({file_path})"
                return
            except Exception as exc:
                print(f"共有プリンタへの接続テストに失敗しました: {exc}。USB接続を試みます。")

        # 2. USB 接続の試行
        try:
            from escpos.printer import Usb  # type: ignore[import]
            usb_printer = Usb(vendor_id, product_id)
            # 実際に接続（オープン）できるかテストし、例外を即時検知する
            usb_printer.open()
            usb_printer.close()

            self._printer = usb_printer
            self._mode = "usb"
            self._connection_info = f"USB プリンタ (ID: {hex(vendor_id)}:{hex(product_id)})"
            return
        except Exception as exc:
            # 接続失敗（pyusbライブラリの欠如や未接続）時はダミーモードへフォールバック
            self._printer = None
            self._mode = "dummy"
            self._connection_info = "シミュレーションモード"
            print(f"実機プリンタが見つかりません。シミュレーションモードで動作します: {exc}")

    def disconnect(self) -> None:
        """プリンタ接続を切断する。"""
        if self._printer is not None:
            try:
                self._printer.close()
            except Exception:
                pass
        self._printer = None
        self._mode = "unconnected"
        self._connection_info = ""
        self._file_path = None

    def print_image(self, image: Image.Image, save_image: bool = False) -> Path | None:
        """
        Pillow 画像をプリンタへ送信して印刷する。
        引数 `save_image=True` またはシミュレーションモードの場合に、
        `data/receipts/` フォルダへPNG画像として保存します。

        Args:
            image: 印刷する Pillow 画像オブジェクト
            save_image: 画像ファイルをローカル保存する場合 True

        Returns:
            Path | None: 保存されたレシート画像のパス。保存されなかった場合は None。

        Raises:
            PrinterError: 印刷処理中にエラーが発生した場合
        """
        save_path = None
        
        # 1. 保存指示があるか、シミュレーションモードの場合のみ画像としてローカル保存する
        if save_image or self._mode == "dummy":
            save_dir = Path("data") / "receipts"
            save_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            save_path = save_dir / f"receipt_{timestamp}.png"
            try:
                image.save(save_path, format="PNG")
            except Exception as exc:
                print(f"レシート画像の保存に失敗しました: {exc}")

        # 2. 共有プリンタ（ファイル接続）モードの場合:
        # 書き込みバッファ遅延を確実に解消するため、印刷の都度オープン・クローズする
        if self._mode == "file" and self._file_path:
            try:
                from escpos.printer import File  # type: ignore[import]
                printer_instance = File(self._file_path)
                printer_instance.image(image)
                printer_instance.cut()
                printer_instance.close()
            except Exception as exc:
                raise PrinterError(f"共有プリンタへの印刷中にエラーが発生しました: {exc}") from exc

        # 3. USB 接続モードの場合:
        # USBの再初期化オーバーヘッドを防ぐため、オープンした状態を維持して印刷
        elif self._mode == "usb" and self._printer is not None:
            try:
                self._printer.image(image)
                self._printer.cut()
                # バッファフラッシュを試みる
                if hasattr(self._printer, "device") and hasattr(self._printer.device, "flush"):
                    try:
                        self._printer.device.flush()
                    except Exception:
                        pass
            except Exception as exc:
                raise PrinterError(f"USBプリンタへの印刷中にエラーが発生しました: {exc}") from exc

        return save_path

    def print_image_from_file(self, image_path: Path, save_image: bool = False) -> Path | None:
        """
        画像ファイルを読み込んでプリンタへ送信する。

        Args:
            image_path: 印刷する画像ファイルのパス
            save_image: 画像ファイルを複製保存する場合 True

        Returns:
            Path | None: 保存されたレシート画像のパス
        """
        try:
            image = Image.open(image_path)
        except OSError as exc:
            raise PrinterError(f"画像ファイル読み込みエラー: {exc}") from exc

        return self.print_image(image, save_image=save_image)

    def is_connected(self) -> bool:
        """プリンタが接続済み（またはシミュレーション動作中）かどうかを返す。"""
        return self._mode != "unconnected"

    def get_status_message(self) -> str:
        """現在のプリンタ接続状態を表すメッセージを返す。"""
        if self._mode == "unconnected":
            return "プリンタ未接続"
        elif self._mode == "dummy":
            return "シミュレーションモード"
        return f"接続中: {self._connection_info}"

    def get_mode(self) -> str:
        """現在のプリンタ接続モードを返す ("file", "usb", "dummy", "unconnected")。"""
        return self._mode
