from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from libramap_editor.model import MapDataError, ShelfMapDocument


class ShelfMapDocumentTest(unittest.TestCase):
    def test_add_floor_object_segment_and_save(self) -> None:
        document = ShelfMapDocument.empty()
        document.add_floor("1f", "1階")
        shelf = document.add_object("1f", "shelf", "A-01")
        document.update_object(
            "1f",
            shelf["id"],
            {
                "id": "A-01",
                "type": "shelf",
                "x": 10,
                "y": 20,
                "width": 80,
                "height": 200,
                "rows": 5,
                "cols": 8,
            },
        )
        document.add_segment("1f", "A-01", 2, 3, 5, "913.6", "913.8")

        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "schema.json"
            document.save(output)
            loaded = ShelfMapDocument.load(output)

        self.assertEqual(loaded.floors()[0]["id"], "1f")
        self.assertEqual(loaded.objects("1f")[0]["id"], "A-01")
        self.assertEqual(loaded.objects("1f")[0]["segments"][0]["ndc_start"], "913.6")

    def test_reject_duplicate_floor_id(self) -> None:
        document = ShelfMapDocument.empty()
        document.add_floor("1f", "1階")
        with self.assertRaises(MapDataError):
            document.add_floor("1f", "別フロア")

    def test_reject_segment_outside_shelf_grid(self) -> None:
        document = ShelfMapDocument.empty()
        document.add_floor("1f", "1階")
        document.add_object("1f", "shelf", "A-01")
        with self.assertRaises(MapDataError):
            document.add_segment("1f", "A-01", 9, 0, 1, "000", "099")


if __name__ == "__main__":
    unittest.main()
