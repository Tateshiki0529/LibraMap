"""
libramap.core.ndl_api

国立国会図書館サーチ（NDL Search）API 連携モジュール。

ISBN-13 を元に書誌情報（タイトル・著者・出版社・NDC）を取得する。
NDC は NDC(10) を優先し、存在しない場合は NDC(9) を使用する。
複数 NDC が存在する場合は最も詳細な分類を採用する。

仕様参照: specs.md §7
"""
from __future__ import annotations

from dataclasses import dataclass, field

import requests
from lxml import etree


# NDL Search OpenSearch API エンドポイント
NDL_API_ENDPOINT = "https://ndlsearch.ndl.go.jp/api/opensearch"

# HTTP リクエストタイムアウト秒数
REQUEST_TIMEOUT_SEC = 10


@dataclass
class BookInfo:
    """
    書誌情報を保持するデータクラス。

    Attributes:
        isbn: ISBN-13 文字列
        title: タイトル
        creator: 著者
        publisher: 出版社
        ndc: 日本十進分類番号（文字列管理。float は使用しない）
        raw_ndcs: API から取得した NDC の全候補リスト
    """
    isbn: str
    title: str = ""
    creator: str = ""
    publisher: str = ""
    ndc: str = ""
    raw_ndcs: list[str] = field(default_factory=list)


class NdlApiError(Exception):
    """NDL Search API 通信エラーを表す例外クラス。"""


class NdlSearchApi:
    """
    NDL Search OpenSearch API 連携クラス。

    ISBN を指定して書誌情報を検索・取得する。
    NDC は文字列として管理し、浮動小数点誤差を回避する。

    仕様:
        - NDC(10) 優先・存在しない場合は NDC(9)
        - 複数 NDC は最も詳細（文字列長が最大）なものを採用
        - API 失敗時は NdlApiError を送出し、呼び出し側でフォールバックを実施する
    """

    # NDC の XML 名前空間と要素名
    _NS = {
        "dc": "http://purl.org/dc/elements/1.1/",
        "dcndl": "http://ndl.go.jp/dcndl/terms/",
        "rss": "http://purl.org/rss/1.0/",
    }

    def search_by_isbn(self, isbn: str) -> BookInfo:
        """
        ISBN-13 で NDL Search API を検索し、書誌情報を返す。

        Args:
            isbn: 検索対象の ISBN-13 文字列

        Returns:
            BookInfo: 取得した書誌情報

        Raises:
            NdlApiError: API 通信失敗・書誌情報未取得の場合
        """
        params = {"isbn": isbn, "cnt": 1}

        try:
            response = requests.get(
                NDL_API_ENDPOINT, params=params, timeout=REQUEST_TIMEOUT_SEC
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise NdlApiError(f"NDL Search API 通信エラー: {exc}") from exc

        return self._parse_response(isbn, response.content)

    def _parse_response(self, isbn: str, xml_bytes: bytes) -> BookInfo:
        """
        API レスポンス XML を解析して BookInfo を生成する。

        Args:
            isbn: 検索に使用した ISBN-13
            xml_bytes: API レスポンスの XML バイト列

        Returns:
            BookInfo: 解析結果

        Raises:
            NdlApiError: 書誌情報が見つからない場合
        """
        try:
            root = etree.fromstring(xml_bytes)
        except etree.XMLSyntaxError as exc:
            raise NdlApiError(f"XML 解析エラー: {exc}") from exc

        # RSS アイテム要素を取得
        items = root.findall(".//item", namespaces=self._NS)
        if not items:
            raise NdlApiError(f"ISBN {isbn} の書誌情報が見つかりませんでした")

        item = items[0]
        info = BookInfo(isbn=isbn)

        # タイトル取得
        title_el = item.find("title")
        if title_el is not None and title_el.text:
            info.title = title_el.text.strip()

        # 著者取得
        creator_el = item.find("dc:creator", namespaces=self._NS)
        if creator_el is not None and creator_el.text:
            info.creator = creator_el.text.strip()

        # 出版社取得
        publisher_el = item.find("dc:publisher", namespaces=self._NS)
        if publisher_el is not None and publisher_el.text:
            info.publisher = publisher_el.text.strip()

        # NDC 取得（NDC(10) 優先）
        info.raw_ndcs, info.ndc = self._extract_ndc(item)

        return info

    def _extract_ndc(self, item: etree._Element) -> tuple[list[str], str]:
        """
        XML アイテム要素から NDC を抽出し、最適な NDC を選択する。

        NDC(10) を優先し、存在しない場合は NDC(9) を使用する。
        複数候補がある場合は最も詳細（文字列長が最大）なものを採用する。

        Args:
            item: RSS アイテムの XML 要素

        Returns:
            tuple[list[str], str]: (全 NDC 候補リスト, 採用 NDC)
        """
        # NDC(10) の候補を収集
        ndc10_list = [
            el.text.strip()
            for el in item.findall("dcndl:NDC", namespaces=self._NS)
            if el.text
        ]

        # NDC(9) の候補を収集
        ndc9_list = [
            el.text.strip()
            for el in item.findall("dc:subject", namespaces=self._NS)
            if el.text and el.text.strip().replace(".", "").isdigit()
        ]

        all_ndcs = ndc10_list + ndc9_list

        if ndc10_list:
            # NDC(10) 優先：最も詳細（文字列長最大）を採用
            chosen = max(ndc10_list, key=len)
        elif ndc9_list:
            chosen = max(ndc9_list, key=len)
        else:
            chosen = ""

        return all_ndcs, chosen
