"""
libramap.core.barcode

バーコード処理モジュール。

入力されたバーコード文字列が ISBN-13 か JAN コードかを判定し、
192 系 JAN コードの場合は ISBN-13 の追加スキャンを要求する。

仕様参照: specs.md §6
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class BarcodeType(Enum):
    """バーコード種別を表す列挙型。"""
    ISBN13 = auto()       # ISBN-13 コード
    JAN_192 = auto()      # 192 系 独自 JAN コード
    JAN_OTHER = auto()    # その他の JAN コード（非対応）
    UNKNOWN = auto()      # 判定不能


@dataclass
class BarcodeResult:
    """
    バーコード判定結果を保持するデータクラス。

    Attributes:
        raw: 入力されたバーコード文字列（生データ）
        barcode_type: 判定されたバーコード種別
        isbn: 抽出または紐付けられた ISBN-13（取得できない場合は None）
    """
    raw: str
    barcode_type: BarcodeType
    isbn: str | None = None


class BarcodeProcessor:
    """
    バーコード処理クラス。

    スキャナから取得したバーコード文字列を受け取り、
    種別判定・ISBN抽出を行う。

    仕様:
        - ISBN-13（978/979 始まり、13 桁）はそのまま処理継続
        - 192 系 JAN（192 始まり）は ISBN-13 追加スキャンを要求
        - それ以外の JAN コードはエラー対象として処理を中断する
    """

    # ISBN-13 の先頭プレフィックス（978 系・979 系）
    ISBN13_PREFIXES: tuple[str, ...] = ("978", "979")

    # 192 系 JAN の先頭プレフィックス
    JAN_192_PREFIX: str = "192"

    def process(self, raw: str) -> BarcodeResult:
        """
        バーコード文字列を受け取り、種別を判定して結果を返す。

        Args:
            raw: スキャナから入力されたバーコード文字列

        Returns:
            BarcodeResult: 判定結果
        """
        code = raw.strip()

        if self._is_isbn13(code):
            return BarcodeResult(raw=code, barcode_type=BarcodeType.ISBN13, isbn=code)

        if self._is_jan_192(code):
            return BarcodeResult(raw=code, barcode_type=BarcodeType.JAN_192, isbn=None)

        if self._is_jan(code):
            return BarcodeResult(raw=code, barcode_type=BarcodeType.JAN_OTHER, isbn=None)

        return BarcodeResult(raw=code, barcode_type=BarcodeType.UNKNOWN, isbn=None)

    def _is_isbn13(self, code: str) -> bool:
        """
        コードが ISBN-13 形式かどうかを判定する。

        13 桁かつ 978/979 始まりの場合に True を返す。

        Args:
            code: 判定対象の文字列

        Returns:
            bool: ISBN-13 形式の場合 True
        """
        return (
            len(code) == 13
            and code.isdigit()
            and code.startswith(self.ISBN13_PREFIXES)
        )

    def _is_jan_192(self, code: str) -> bool:
        """
        コードが 192 系 JAN コードかどうかを判定する。

        13 桁かつ 192 始まりの場合に True を返す。

        Args:
            code: 判定対象の文字列

        Returns:
            bool: 192 系 JAN の場合 True
        """
        return (
            len(code) == 13
            and code.isdigit()
            and code.startswith(self.JAN_192_PREFIX)
        )

    def _is_jan(self, code: str) -> bool:
        """
        コードが一般的な JAN コード形式かどうかを判定する。

        8 桁または 13 桁の数字文字列を JAN と見なす。

        Args:
            code: 判定対象の文字列

        Returns:
            bool: JAN コード形式の場合 True
        """
        return len(code) in (8, 13) and code.isdigit()
