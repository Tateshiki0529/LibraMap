from __future__ import annotations

import unittest

from libramap.ndc_map import get_ndc_label


class NdcMapTest(unittest.TestCase):
    def test_three_digit_lookup(self) -> None:
        self.assertEqual(get_ndc_label("913"), "\u5c0f\u8aac. \u7269\u8a9e")

    def test_decimal_lookup_uses_first_three_digits(self) -> None:
        self.assertEqual(get_ndc_label("913.6"), "\u5c0f\u8aac. \u7269\u8a9e")

    def test_last_code(self) -> None:
        self.assertEqual(get_ndc_label("999"), "\u56fd\u969b\u8a9e\uff3b\u4eba\u5de5\u8a9e\uff3d\u306b\u3088\u308b\u6587\u5b66")

    def test_unknown_or_blank_returns_none(self) -> None:
        self.assertIsNone(get_ndc_label(""))
        self.assertIsNone(get_ndc_label("abc"))
        self.assertIsNone(get_ndc_label(None))


if __name__ == "__main__":
    unittest.main()
