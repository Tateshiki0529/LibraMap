from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from libramap.core.barcode import BarcodeProcessor, BarcodeType
from libramap.core.local_db import BookRecord, LocalBookDatabase
from libramap.core.placement_engine import PlacementEngine
from libramap.printing.receipt_renderer import ReceiptData, ReceiptRenderer


class BarcodeProcessorTest(unittest.TestCase):
    def test_isbn13(self) -> None:
        result = BarcodeProcessor().process("9784101010113")
        self.assertEqual(result.barcode_type, BarcodeType.ISBN13)
        self.assertEqual(result.isbn, "9784101010113")

    def test_unsupported_jan(self) -> None:
        result = BarcodeProcessor().process("4901234567894")
        self.assertEqual(result.barcode_type, BarcodeType.JAN_OTHER)


class PlacementEngineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.floor_data = json.loads(Path("libramap/data/schema.json").read_text(encoding="utf-8"))

    def test_uses_most_specific_segment(self) -> None:
        result = PlacementEngine(self.floor_data).determine("913.6")
        self.assertTrue(result.found)
        self.assertIsNotNone(result.segment)
        self.assertEqual(result.segment.shelf_id, "B-12")
        self.assertEqual(result.segment.row, 2)

    def test_restricted_takes_priority(self) -> None:
        result = PlacementEngine(self.floor_data).determine("913.6", is_restricted=True)
        self.assertTrue(result.found)
        self.assertTrue(result.is_restricted)
        self.assertIsNone(result.segment)


class LocalBookDatabaseTest(unittest.TestCase):
    def test_upsert_and_find(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db = LocalBookDatabase(Path(temp_dir) / "books.db")
            db.upsert(BookRecord(isbn="9780000000002", title="テスト", ndc="913.6"))
            found = db.find_by_isbn("9780000000002")
            self.assertIsNotNone(found)
            self.assertEqual(found.title, "テスト")

    def test_t11_sample_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db = LocalBookDatabase(Path(temp_dir) / "books.db")
            found = db.find_by_isbn("9784947017377")
            self.assertIsNotNone(found)
            self.assertEqual(found.title, "ホームレス中学生")
            self.assertEqual(found.ndc, "999.9")


class ReceiptRendererTest(unittest.TestCase):
    def test_render_receipt_image(self) -> None:
        floor_data = json.loads(Path("libramap/data/schema.json").read_text(encoding="utf-8"))
        placement = PlacementEngine(floor_data).determine("913.6")
        image = ReceiptRenderer(floor_data).render(
            ReceiptData(
                title="吾輩は猫である",
                creator="夏目漱石",
                isbn="9784101010113",
                ndc="913.6",
                placement=placement,
            )
        )
        self.assertEqual(image.width, 384)
        self.assertGreater(image.height, 300)


if __name__ == "__main__":
    unittest.main()
