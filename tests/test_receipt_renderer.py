from __future__ import annotations

import unittest

from libramap.printing.receipt_renderer import _format_ndc_line


class ReceiptRendererFormattingTest(unittest.TestCase):
    def test_ndc_line_includes_label_when_available(self) -> None:
        self.assertEqual(_format_ndc_line("913.6"), "NDC: 913.6 (小説. 物語)")

    def test_ndc_line_falls_back_to_code_only_when_label_missing(self) -> None:
        self.assertEqual(_format_ndc_line("062.1"), "NDC: 062.1")

    def test_ndc_line_handles_blank_value(self) -> None:
        self.assertEqual(_format_ndc_line(""), "NDC: 未取得")


if __name__ == "__main__":
    unittest.main()
