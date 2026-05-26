"""
libramap.core.placement_engine

配架判定エンジン。

NDC 文字列と書架データ（JSON）を照合し、返却対象書架を特定する。
NDC は文字列として管理し、最長一致方式で最も詳細な書架セルを選択する。

判定優先順位（specs.md §9.3）:
    1. 禁帯出ルール
    2. 個別例外
    3. 詳細 NDC（最長一致）
    4. 通常 NDC

仕様参照: specs.md §9
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ShelfSegment:
    """
    書架の NDC セグメント情報を表すデータクラス。

    Attributes:
        shelf_id: 書架 ID（例: "B-12"）
        floor_id: フロア ID（例: "2f"）
        floor_name: フロア名（例: "2階"）
        row: 段番号（0 始まり）
        col_start: 開始列番号（0 始まり）
        col_end: 終了列番号（0 始まり）
        ndc_start: NDC 範囲の開始（文字列）
        ndc_end: NDC 範囲の終了（文字列）
    """
    shelf_id: str
    floor_id: str
    floor_name: str
    row: int
    col_start: int
    col_end: int
    ndc_start: str
    ndc_end: str


@dataclass
class PlacementResult:
    """
    配架判定結果を保持するデータクラス。

    Attributes:
        found: 書架位置が特定できた場合 True
        segment: 特定された書架セグメント（未特定の場合は None）
        is_restricted: 禁帯出資料の場合 True
        message: 表示用メッセージ
    """
    found: bool
    segment: ShelfSegment | None = None
    is_restricted: bool = False
    message: str = ""


class PlacementEngine:
    """
    配架判定エンジンクラス。

    書架データ（JSON 形式）を元に、NDC 文字列から返却書架位置を特定する。

    最長一致方式:
        NDC 範囲に対して前方一致で照合し、
        より詳細な NDC 範囲（文字列が長い方）を優先する。

        例: ndc_start="913.6" は ndc_start="913" より優先される。

    NDC 文字列管理:
        float を使用せず文字列として管理する。
        これにより float 比較誤差・桁落ちを防ぐ。
    """

    def __init__(self, floor_data: dict[str, Any]) -> None:
        """
        書架データを受け取って配架エンジンを初期化する。

        Args:
            floor_data: JSON から読み込んだ書架データ辞書（specs.md §11.2 形式）
        """
        self._floor_data = floor_data
        self._segments: list[ShelfSegment] = self._load_segments(floor_data)

    def determine(
        self, ndc: str, is_restricted: bool = False
    ) -> PlacementResult:
        """
        NDC と禁帯出フラグを元に書架位置を特定する。

        判定優先順位:
            1. 禁帯出ルール（is_restricted=True の場合は禁帯出エリアを返す）
            2. NDC 最長一致で書架セグメントを選択

        Args:
            ndc: 判定対象の NDC 文字列（例: "913.6"）
            is_restricted: 禁帯出資料の場合 True

        Returns:
            PlacementResult: 配架判定結果
        """
        if is_restricted:
            return PlacementResult(
                found=True,
                is_restricted=True,
                message="禁帯出資料です。禁帯出エリアへ返却してください。",
            )

        if not ndc:
            return PlacementResult(
                found=False,
                message="NDC が取得できませんでした。手動で返却先を確認してください。",
            )

        segment = self._find_best_segment(ndc)
        if segment is None:
            return PlacementResult(
                found=False,
                message=f"NDC {ndc} に対応する書架が見つかりませんでした。",
            )

        return PlacementResult(
            found=True,
            segment=segment,
            message=(
                f"{segment.floor_name} / 書架 {segment.shelf_id} "
                f"（{segment.row + 1} 段 / "
                f"{segment.col_start + 1}〜{segment.col_end + 1} 列）"
            ),
        )

    def _find_best_segment(self, ndc: str) -> ShelfSegment | None:
        """
        NDC に最も詳細に一致するセグメントを返す（最長一致方式）。

        NDC の先頭文字列が ndc_start と ndc_end の範囲内にある
        セグメントのうち、ndc_start が最も長い（詳細な）ものを選ぶ。

        Args:
            ndc: 判定対象の NDC 文字列

        Returns:
            ShelfSegment | None: 最適なセグメント。見つからない場合は None。
        """
        candidates: list[ShelfSegment] = []

        for seg in self._segments:
            if self._ndc_in_range(ndc, seg.ndc_start, seg.ndc_end):
                candidates.append(seg)

        if not candidates:
            return None

        # 最長一致: ndc_start の文字列長が最大のものを選ぶ
        return max(candidates, key=lambda s: len(s.ndc_start))

    @staticmethod
    def _ndc_in_range(ndc: str, ndc_start: str, ndc_end: str) -> bool:
        """
        NDC 文字列が指定範囲内にあるかどうかを判定する。

        文字列比較で範囲チェックを行い、float 変換は行わない。

        Args:
            ndc: 判定対象の NDC
            ndc_start: 範囲の下限 NDC
            ndc_end: 範囲の上限 NDC

        Returns:
            bool: 範囲内の場合 True
        """
        return ndc_start <= ndc <= ndc_end

    @staticmethod
    def _load_segments(floor_data: dict[str, Any]) -> list[ShelfSegment]:
        """
        フロアデータ辞書から ShelfSegment リストを生成する。

        Args:
            floor_data: JSON 書架データ

        Returns:
            list[ShelfSegment]: セグメントの一覧
        """
        segments: list[ShelfSegment] = []

        for floor in floor_data.get("floors", []):
            floor_id = floor.get("id", "")
            floor_name = floor.get("name", "")

            for obj in floor.get("objects", []):
                if obj.get("type") != "shelf":
                    continue

                shelf_id = obj.get("id", "")

                for seg in obj.get("segments", []):
                    segments.append(
                        ShelfSegment(
                            shelf_id=shelf_id,
                            floor_id=floor_id,
                            floor_name=floor_name,
                            row=seg.get("row", 0),
                            col_start=seg.get("col_start", 0),
                            col_end=seg.get("col_end", 0),
                            ndc_start=seg.get("ndc_start", ""),
                            ndc_end=seg.get("ndc_end", ""),
                        )
                    )

        return segments
