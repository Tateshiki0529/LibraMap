from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class BarcodeType(Enum):
    ISBN13 = auto()
    JAN_192 = auto()
    JAN_OTHER = auto()
    UNKNOWN = auto()


@dataclass(frozen=True)
class BarcodeResult:
    raw: str
    barcode_type: BarcodeType
    isbn: str | None = None


class BarcodeProcessor:
    ISBN13_PREFIXES = ("978", "979")
    JAN_192_PREFIX = "192"

    def process(self, raw: str) -> BarcodeResult:
        code = "".join(ch for ch in raw.strip().upper() if ch.isdigit() or ch == "X")

        if self._is_isbn13(code):
            return BarcodeResult(raw=code, barcode_type=BarcodeType.ISBN13, isbn=code)
        if self._is_isbn10(code):
            isbn13 = self._isbn10_to_isbn13(code)
            return BarcodeResult(raw=code, barcode_type=BarcodeType.ISBN13, isbn=isbn13)
        if self._is_jan_192(code):
            return BarcodeResult(raw=code, barcode_type=BarcodeType.JAN_192)
        if self._is_jan(code):
            return BarcodeResult(raw=code, barcode_type=BarcodeType.JAN_OTHER)
        return BarcodeResult(raw=code, barcode_type=BarcodeType.UNKNOWN)

    def _is_isbn13(self, code: str) -> bool:
        return (
            len(code) == 13
            and code.startswith(self.ISBN13_PREFIXES)
            and self._has_valid_ean13_check_digit(code)
        )

    def _is_jan_192(self, code: str) -> bool:
        return (
            len(code) == 13
            and code.startswith(self.JAN_192_PREFIX)
            and self._has_valid_ean13_check_digit(code)
        )

    @staticmethod
    def _is_jan(code: str) -> bool:
        if len(code) == 13:
            return BarcodeProcessor._has_valid_ean13_check_digit(code)
        return len(code) == 8 and code.isdigit()

    @staticmethod
    def _is_isbn10(code: str) -> bool:
        if len(code) != 10 or not code[:9].isdigit():
            return False
        check_char = code[-1]
        if not (check_char.isdigit() or check_char == "X"):
            return False
        total = sum((10 - index) * int(char) for index, char in enumerate(code[:9]))
        total += 10 if check_char == "X" else int(check_char)
        return total % 11 == 0

    @staticmethod
    def _isbn10_to_isbn13(code: str) -> str:
        body = f"978{code[:9]}"
        check_digit = BarcodeProcessor._ean13_check_digit(body)
        return f"{body}{check_digit}"

    @staticmethod
    def _ean13_check_digit(first_12_digits: str) -> int:
        total = 0
        for index, char in enumerate(first_12_digits):
            weight = 1 if index % 2 == 0 else 3
            total += int(char) * weight
        return (10 - (total % 10)) % 10

    @staticmethod
    def _has_valid_ean13_check_digit(code: str) -> bool:
        if len(code) != 13 or not code.isdigit():
            return False
        expected = BarcodeProcessor._ean13_check_digit(code[:12])
        return expected == int(code[-1])
