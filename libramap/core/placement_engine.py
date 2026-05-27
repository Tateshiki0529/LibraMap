from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ShelfSegment:
    shelf_id: str
    floor_id: str
    floor_name: str
    row: int
    col_start: int
    col_end: int
    ndc_start: str
    ndc_end: str


@dataclass(frozen=True)
class PlacementResult:
    found: bool
    segment: ShelfSegment | None = None
    is_restricted: bool = False
    message: str = ""


class PlacementEngine:
    def __init__(self, floor_data: dict[str, Any]) -> None:
        self._floor_data = floor_data
        self._segments = self._load_segments(floor_data)

    def determine(self, ndc: str, is_restricted: bool = False) -> PlacementResult:
        if is_restricted:
            return PlacementResult(
                found=True,
                is_restricted=True,
                message="禁帯出資料です。禁帯出エリアへ返却してください。",
            )

        if not ndc:
            return PlacementResult(
                found=False,
                message="NDCを取得できません。手動で返却先を確認してください。",
            )

        segment = self._find_best_segment(ndc)
        if not segment:
            return PlacementResult(
                found=False,
                message=f"NDC {ndc} に対応する書架が未定義です。",
            )

        return PlacementResult(
            found=True,
            segment=segment,
            message=(
                f"{segment.floor_name} / 書架 {segment.shelf_id} / "
                f"{segment.row + 1}段 / {segment.col_start + 1}-{segment.col_end + 1}列"
            ),
        )

    def _find_best_segment(self, ndc: str) -> ShelfSegment | None:
        candidates = [
            segment
            for segment in self._segments
            if self._ndc_in_range(ndc, segment.ndc_start, segment.ndc_end)
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda segment: self._specificity(segment.ndc_start))

    @staticmethod
    def _load_segments(floor_data: dict[str, Any]) -> list[ShelfSegment]:
        segments: list[ShelfSegment] = []
        for floor in floor_data.get("floors", []):
            for obj in floor.get("objects", []):
                if obj.get("type") != "shelf":
                    continue
                for segment in obj.get("segments", []):
                    segments.append(
                        ShelfSegment(
                            shelf_id=obj.get("id", ""),
                            floor_id=floor.get("id", ""),
                            floor_name=floor.get("name", ""),
                            row=int(segment.get("row", 0)),
                            col_start=int(segment.get("col_start", 0)),
                            col_end=int(segment.get("col_end", 0)),
                            ndc_start=str(segment.get("ndc_start", "")),
                            ndc_end=str(segment.get("ndc_end", "")),
                        )
                    )
        return segments

    @classmethod
    def _ndc_in_range(cls, ndc: str, ndc_start: str, ndc_end: str) -> bool:
        return cls._ndc_key(ndc_start) <= cls._ndc_key(ndc) <= cls._ndc_key(ndc_end)

    @staticmethod
    def _specificity(ndc: str) -> int:
        return len(ndc.replace(".", ""))

    @staticmethod
    def _ndc_key(ndc: str) -> tuple[int, int]:
        left, _, right = ndc.partition(".")
        left_value = int(left) if left.isdigit() else 0
        right_digits = "".join(ch for ch in right if ch.isdigit())
        right_value = int(right_digits.ljust(6, "0")[:6]) if right_digits else 0
        return left_value, right_value
