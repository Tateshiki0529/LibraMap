"""
libramap.printing.receipt_renderer

レシート描画モジュール。

Pillow を使用して 58mm 感熱紙向けのレシート画像を生成する。
書架位置マップ画像を含む ESC/POS 印刷用ラスタ画像を出力する。
日本語フォント（MS ゴシック等）に対応し、文字化けを防ぐ。

レシート構成（specs.md §13.1）:
    上部: タイトル・NDC・階数・書架コード
    中央: 大型書架コード表示
    下部: 書架位置マップ画像（対象セルを黒塗り強調）

仕様参照: specs.md §13, §14
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFont

if TYPE_CHECKING:
    from libramap.core.placement_engine import PlacementResult


# 58mm 用紙の印刷可能幅（ピクセル、203dpi 換算）
RECEIPT_WIDTH_PX = 384

# フォントサイズ設定
FONT_SIZE_TITLE = 20
FONT_SIZE_NORMAL = 16
FONT_SIZE_SHELF_CODE = 48

# 色定義
COLOR_WHITE = (255, 255, 255)
COLOR_BLACK = (0, 0, 0)
COLOR_GRAY = (180, 180, 180)
COLOR_HIGHLIGHT = (64, 64, 64)


@dataclass
class ReceiptData:
    """
    レシート描画に必要なデータを保持するデータクラス。

    Attributes:
        title: 書籍タイトル
        creator: 著者
        isbn: ISBN-13
        ndc: NDC 文字列
        placement: 配架判定結果
        shelf_rows: 書架の段数
        shelf_cols: 書架の列数
    """
    title: str
    creator: str
    isbn: str
    ndc: str
    placement: "PlacementResult"
    shelf_rows: int = 5
    shelf_cols: int = 8


class ReceiptRenderer:
    """
    レシート画像描画クラス。

    Pillow を使用して 58mm 幅のレシート用 PNG 画像を生成する。
    画像ラスタ印刷方式（specs.md §13.3）に対応した出力を行う。
    Windows環境の日本語フォント（MSゴシック/メイリオ等）を自動ロードして文字化けを防ぐ。
    """

    def render(self, data: ReceiptData) -> Image.Image:
        """
        レシート画像を生成して返す。

        Args:
            data: レシート描画データ

        Returns:
            Image.Image: 生成されたレシート画像
        """
        parts: list[Image.Image] = []

        parts.append(self._render_header(data))
        parts.append(self._render_shelf_code(data))
        parts.append(self._render_shelf_map(data))

        return self._concat_vertical(parts)

    def save(self, data: ReceiptData, output_path: Path) -> None:
        """
        レシート画像をファイルに保存する。

        Args:
            data: レシート描画データ
            output_path: 保存先ファイルパス（PNG 形式）
        """
        image = self.render(data)
        image.save(output_path, format="PNG")

    def _get_font(self, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        """
        利用可能な日本語フォントオブジェクトを取得する。
        OS標準のフォントファイル名からロードを試みる。
        """
        font_names = ["msgothic.ttc", "meiryo.ttc", "msgothic.ttf"]
        for name in font_names:
            try:
                return ImageFont.truetype(name, size)
            except OSError:
                continue
        # フォールバック
        return ImageFont.load_default()

    def _render_header(self, data: ReceiptData) -> Image.Image:
        """
        レシート上部（タイトル・NDC・階数・書架コード）を描画する。

        Args:
            data: レシート描画データ

        Returns:
            Image.Image: ヘッダー部分の画像
        """
        font = self._get_font(FONT_SIZE_NORMAL)
        lines: list[str] = []

        # タイトル
        lines.append(f"【{data.title}】")
        if data.creator:
            lines.append(data.creator)

        lines.append(f"NDC: {data.ndc}" if data.ndc else "NDC: 不明")

        if data.placement.found and data.placement.segment:
            seg = data.placement.segment
            lines.append(f"フロア: {seg.floor_name}")
            lines.append(f"書架: {seg.shelf_id}")
        elif data.placement.is_restricted:
            lines.append("【禁帯出資料】")
        else:
            lines.append("※ 要手動確認")

        # 行高さに合わせてキャンバスサイズを計算
        line_height = FONT_SIZE_NORMAL + 6
        height = line_height * len(lines) + 20
        img = Image.new("L", (RECEIPT_WIDTH_PX, height), 255)
        draw = ImageDraw.Draw(img)

        y = 10
        for line in lines:
            draw.text((10, y), line, fill=0, font=font)
            y += line_height

        return img

    def _render_shelf_code(self, data: ReceiptData) -> Image.Image:
        """
        レシート中央（大型書架コード）を描画する。

        Args:
            data: レシート描画データ

        Returns:
            Image.Image: 書架コード部分の画像
        """
        font = self._get_font(FONT_SIZE_SHELF_CODE)
        height = FONT_SIZE_SHELF_CODE + 30
        img = Image.new("L", (RECEIPT_WIDTH_PX, height), 255)
        draw = ImageDraw.Draw(img)

        if data.placement.found and data.placement.segment:
            code = data.placement.segment.shelf_id
        elif data.placement.is_restricted:
            code = "禁帯出"
        else:
            code = "手動確認"

        draw.text((10, 15), code, fill=0, font=font)

        return img

    def _render_shelf_map(self, data: ReceiptData) -> Image.Image:
        """
        レシート下部（書架位置マップ画像）を描画する。

        対象セルを黒塗りで強調表示する。

        Args:
            data: レシート描画データ

        Returns:
            Image.Image: 書架マップ部分の画像
        """
        cell_w = RECEIPT_WIDTH_PX // (data.shelf_cols + 1)
        cell_h = 24
        margin = 10

        map_height = cell_h * data.shelf_rows + margin * 2
        img = Image.new("L", (RECEIPT_WIDTH_PX, map_height), 255)
        draw = ImageDraw.Draw(img)

        seg = data.placement.segment if data.placement.found else None

        for row in range(data.shelf_rows):
            for col in range(data.shelf_cols):
                x1 = margin + col * cell_w
                y1 = margin + row * cell_h
                x2 = x1 + cell_w - 2
                y2 = y1 + cell_h - 2

                # 対象セルかどうかを判定して色分け
                is_target = (
                    seg is not None
                    and row == seg.row
                    and seg.col_start <= col <= seg.col_end
                )

                fill = 0 if is_target else 180
                draw.rectangle([x1, y1, x2, y2], fill=fill, outline=0)

        return img

    @staticmethod
    def _concat_vertical(images: list[Image.Image]) -> Image.Image:
        """
        複数の画像を縦方向に結合する。

        Args:
            images: 結合する画像のリスト

        Returns:
            Image.Image: 結合後の画像
        """
        total_height = sum(img.height for img in images)
        result = Image.new("L", (RECEIPT_WIDTH_PX, total_height), 255)

        y_offset = 0
        for img in images:
            result.paste(img, (0, y_offset))
            y_offset += img.height

        return result
