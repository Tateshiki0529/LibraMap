from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from libramap.core.placement_engine import PlacementResult, ShelfSegment
from libramap.ndc_map import get_ndc_label


RECEIPT_WIDTH_PX = 384


@dataclass(frozen=True)
class ReceiptData:
    title: str
    creator: str
    isbn: str
    ndc: str
    placement: PlacementResult
    shelf_rows: int = 5
    shelf_cols: int = 8


class ReceiptRenderer:
    def __init__(self, floor_data: dict[str, Any]) -> None:
        self._floor_data = floor_data
        self._floor_renderer = FloorMapRenderer(floor_data)

    def render(self, data: ReceiptData) -> Image.Image:
        parts = [
            self._render_header(data),
            self._render_shelf_code(data),
            self._render_floor_map(data),
            self._render_shelf_grid(data),
            self._render_footer(data),
        ]
        return self._concat_vertical(parts)

    def save(self, data: ReceiptData, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.render(data).save(output_path, format="PNG")

    def _render_header(self, data: ReceiptData) -> Image.Image:
        font = _font(18)
        small = _font(14)
        lines = [
            _truncate(data.title or "書名不明", 22),
            _truncate(data.creator, 26) if data.creator else "",
            f"ISBN: {data.isbn}",
            _format_ndc_line(data.ndc),
        ]
        if data.placement.segment:
            lines.append(f"{data.placement.segment.floor_name} / 書架 {data.placement.segment.shelf_id}")
        elif data.placement.is_restricted:
            lines.append("禁帯出エリアへ返却")
        else:
            lines.append("要手動確認")

        height = 18 + sum(24 if i == 0 else 20 for i, line in enumerate(lines) if line)
        img = Image.new("L", (RECEIPT_WIDTH_PX, height), 255)
        draw = ImageDraw.Draw(img)
        y = 8
        for index, line in enumerate(lines):
            if not line:
                continue
            draw.text((12, y), line, fill=0, font=font if index == 0 else small)
            y += 24 if index == 0 else 20
        return img

    def _render_shelf_code(self, data: ReceiptData) -> Image.Image:
        img = Image.new("L", (RECEIPT_WIDTH_PX, 90), 255)
        draw = ImageDraw.Draw(img)
        code = "手動確認"
        if data.placement.segment:
            code = data.placement.segment.shelf_id
        elif data.placement.is_restricted:
            code = "禁帯出"

        font = _font(54)
        bbox = draw.textbbox((0, 0), code, font=font)
        x = max(8, (RECEIPT_WIDTH_PX - (bbox[2] - bbox[0])) // 2)
        draw.text((x, 14), code, fill=0, font=font)
        draw.line((12, 84, RECEIPT_WIDTH_PX - 12, 84), fill=0, width=2)
        return img

    def _render_floor_map(self, data: ReceiptData) -> Image.Image:
        if data.placement.is_restricted:
            floor_id = self._first_floor_with_type("restricted") or "1f"
            image = self._floor_renderer.render(floor_id, highlight_restricted=True, monochrome=True)
        elif data.placement.segment:
            image = self._floor_renderer.render(
                data.placement.segment.floor_id,
                highlight_shelf_id=data.placement.segment.shelf_id,
                highlight_segment=data.placement.segment,
                monochrome=True,
            )
        else:
            return Image.new("L", (RECEIPT_WIDTH_PX, 24), 255)
        return image.convert("L").resize((RECEIPT_WIDTH_PX, 190), Image.Resampling.LANCZOS)

    def _render_shelf_grid(self, data: ReceiptData) -> Image.Image:
        segment = data.placement.segment
        if not segment:
            return Image.new("L", (RECEIPT_WIDTH_PX, 22), 255)

        img = Image.new("L", (RECEIPT_WIDTH_PX, 140), 255)
        draw = ImageDraw.Draw(img)
        draw.text((12, 6), "書架内の目安位置", fill=0, font=_font(14))

        margin_x = 18
        margin_y = 32
        width = RECEIPT_WIDTH_PX - margin_x * 2
        height = 92
        cell_w = width / data.shelf_cols
        cell_h = height / data.shelf_rows

        for row in range(data.shelf_rows):
            for col in range(data.shelf_cols):
                rect = [
                    margin_x + col * cell_w,
                    margin_y + row * cell_h,
                    margin_x + (col + 1) * cell_w,
                    margin_y + (row + 1) * cell_h,
                ]
                is_target = row == segment.row and segment.col_start <= col <= segment.col_end
                if is_target:
                    draw.rectangle(rect, fill=0, outline=0)
                else:
                    draw.rectangle(rect, outline=0, width=1)
        return img

    def _render_footer(self, data: ReceiptData) -> Image.Image:
        img = Image.new("L", (RECEIPT_WIDTH_PX, 54), 255)
        draw = ImageDraw.Draw(img)
        message = data.placement.message or "司書が最終確認してください。"
        draw.text((12, 8), _truncate(message, 28), fill=0, font=_font(13))
        draw.text((12, 30), "最終判断は司書が行ってください。", fill=0, font=_font(13))
        return img

    def _first_floor_with_type(self, obj_type: str) -> str | None:
        for floor in self._floor_data.get("floors", []):
            if any(obj.get("type") == obj_type for obj in floor.get("objects", [])):
                return floor.get("id")
        return None

    @staticmethod
    def _concat_vertical(images: list[Image.Image]) -> Image.Image:
        height = sum(image.height for image in images)
        result = Image.new("L", (RECEIPT_WIDTH_PX, height), 255)
        y = 0
        for image in images:
            result.paste(image.convert("L"), (0, y))
            y += image.height
        return result


class FloorMapRenderer:
    def __init__(self, floor_data: dict[str, Any]) -> None:
        self._floor_data = floor_data

    def render(
        self,
        floor_id: str,
        highlight_shelf_id: str | None = None,
        highlight_segment: ShelfSegment | None = None,
        highlight_restricted: bool = False,
        monochrome: bool = False,
    ) -> Image.Image:
        img = Image.new("RGB", (800, 400), (255, 255, 255))
        draw = ImageDraw.Draw(img)
        floor = self._find_floor(floor_id)
        if not floor:
            return img

        for obj in floor.get("objects", []):
            self._draw_object(draw, obj, highlight_shelf_id, highlight_segment, highlight_restricted, monochrome)

        font = _font(15)
        for obj in floor.get("objects", []):
            obj_type = obj.get("type", "")
            label = obj.get("id", "")
            if obj_type == "desk":
                label = "カウンター"
            elif obj_type == "return_box":
                label = "返却BOX"
            elif obj_type == "stairs":
                label = "階段"
            elif obj_type == "restricted":
                label = "禁帯出"
            x, y = int(obj.get("x", 0)), int(obj.get("y", 0))
            if obj_type != "wall":
                draw.text((x + 4, y + 4), label, fill=(0, 0, 0), font=font)
        return img

    def _draw_object(
        self,
        draw: ImageDraw.ImageDraw,
        obj: dict[str, Any],
        highlight_shelf_id: str | None,
        highlight_segment: ShelfSegment | None,
        highlight_restricted: bool,
        monochrome: bool,
    ) -> None:
        obj_type = obj.get("type", "")
        obj_id = obj.get("id", "")
        x, y = int(obj.get("x", 0)), int(obj.get("y", 0))
        w, h = int(obj.get("width", 0)), int(obj.get("height", 0))
        rect = [x, y, x + w, y + h]

        if obj_type == "wall":
            draw.rectangle(rect, fill=(0, 0, 0))
        elif obj_type == "restricted":
            fill = (255, 255, 255) if monochrome else (255, 238, 210)
            outline = (0, 0, 0) if monochrome else (217, 119, 6)
            width = 4 if highlight_restricted else 2
            draw.rectangle(rect, fill=fill, outline=outline, width=width)
            if highlight_restricted:
                draw.line((x, y, x + w, y + h), fill=outline, width=3)
                draw.line((x + w, y, x, y + h), fill=outline, width=3)
        elif obj_type == "stairs":
            draw.rectangle(rect, fill=(255, 255, 255), outline=(0, 0, 0), width=2)
            for offset in range(-h, w, 14):
                draw.line((x + offset, y, x + offset + h, y + h), fill=(0, 0, 0), width=1)
        elif obj_type == "shelf":
            is_target = highlight_shelf_id == obj_id
            fill = (255, 255, 255) if monochrome else (226, 232, 240)
            outline = (0, 0, 0) if monochrome else (71, 85, 105)
            draw.rectangle(rect, fill=fill, outline=outline, width=4 if is_target else 2)
            if is_target and highlight_segment and not monochrome:
                self._draw_shelf_cells(draw, obj, highlight_segment)
            elif is_target:
                draw.rectangle(rect, outline=(0, 0, 0), width=6)
        else:
            fill = (255, 255, 255) if monochrome else (241, 245, 249)
            draw.rectangle(rect, fill=fill, outline=(0, 0, 0), width=2)

    @staticmethod
    def _draw_shelf_cells(draw: ImageDraw.ImageDraw, obj: dict[str, Any], segment: ShelfSegment) -> None:
        x, y = int(obj.get("x", 0)), int(obj.get("y", 0))
        w, h = int(obj.get("width", 0)), int(obj.get("height", 0))
        rows, cols = int(obj.get("rows", 5)), int(obj.get("cols", 8))
        cell_w = w / cols
        cell_h = h / rows
        for row in range(rows):
            for col in range(cols):
                rect = [x + col * cell_w, y + row * cell_h, x + (col + 1) * cell_w, y + (row + 1) * cell_h]
                if row == segment.row and segment.col_start <= col <= segment.col_end:
                    draw.rectangle(rect, fill=(220, 38, 38), outline=(0, 0, 0))
                else:
                    draw.rectangle(rect, outline=(148, 163, 184))

    def _find_floor(self, floor_id: str) -> dict[str, Any] | None:
        for floor in self._floor_data.get("floors", []):
            if floor.get("id") == floor_id:
                return floor
        return None


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in ("meiryo.ttc", "msgothic.ttc", "YuGothM.ttc", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _truncate(text: str, length: int) -> str:
    return text if len(text) <= length else f"{text[: length - 1]}…"


def _format_ndc_line(ndc: str | None) -> str:
    if not ndc:
        return "NDC: 未取得"

    label = get_ndc_label(ndc)
    if label is None:
        return f"NDC: {ndc}"
    return f"NDC: {ndc} ({label})"
