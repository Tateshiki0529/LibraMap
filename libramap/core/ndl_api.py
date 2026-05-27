from __future__ import annotations

from dataclasses import dataclass, field

import requests
from lxml import etree


NDL_API_ENDPOINT = "https://ndlsearch.ndl.go.jp/api/opensearch"
REQUEST_TIMEOUT_SEC = 10


@dataclass(frozen=True)
class BookInfo:
    isbn: str
    title: str = ""
    creator: str = ""
    publisher: str = ""
    ndc: str = ""
    raw_ndcs: list[str] = field(default_factory=list)


class NdlApiError(Exception):
    pass


class NdlSearchApi:
    _NS = {
        "dc": "http://purl.org/dc/elements/1.1/",
        "dcndl": "http://ndl.go.jp/dcndl/terms/",
    }

    def search_by_isbn(self, isbn: str) -> BookInfo:
        try:
            response = requests.get(
                NDL_API_ENDPOINT,
                params={"isbn": isbn, "cnt": 1},
                timeout=REQUEST_TIMEOUT_SEC,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise NdlApiError(f"NDL Search APIへの接続に失敗しました: {exc}") from exc

        return self._parse_response(isbn, response.content)

    def _parse_response(self, isbn: str, xml_bytes: bytes) -> BookInfo:
        try:
            root = etree.fromstring(xml_bytes)
        except etree.XMLSyntaxError as exc:
            raise NdlApiError(f"NDL Search APIのXMLを解析できません: {exc}") from exc

        items = root.findall(".//item")
        if not items:
            raise NdlApiError(f"ISBN {isbn} の書誌情報が見つかりません")

        item = items[0]
        raw_ndcs, ndc = self._extract_ndc(item)

        return BookInfo(
            isbn=isbn,
            title=self._text(item, "title"),
            creator=self._text(item, "dc:creator"),
            publisher=self._text(item, "dc:publisher"),
            ndc=ndc,
            raw_ndcs=raw_ndcs,
        )

    def _extract_ndc(self, item: etree._Element) -> tuple[list[str], str]:
        ndc10 = [
            value
            for value in (self._clean_ndc(el.text) for el in item.findall("dcndl:NDC", namespaces=self._NS))
            if value
        ]
        ndc9 = [
            value
            for value in (self._clean_ndc(el.text) for el in item.findall("dc:subject", namespaces=self._NS))
            if value
        ]

        candidates = ndc10 or ndc9
        if not candidates:
            return [], ""

        chosen = max(candidates, key=lambda value: (len(value.replace(".", "")), len(value)))
        return ndc10 + ndc9, chosen

    def _text(self, item: etree._Element, xpath: str) -> str:
        el = item.find(xpath, namespaces=self._NS)
        return el.text.strip() if el is not None and el.text else ""

    @staticmethod
    def _clean_ndc(value: str | None) -> str:
        if not value:
            return ""
        cleaned = value.strip()
        return cleaned if cleaned.replace(".", "").isdigit() else ""
