"""
libramap.printing.receipt_renderer

レシート描画モジュール。

Pillow を使用して 58mm 感熱紙向けのレシート画像を生成する。
また、GUI画面上および印刷レシート上に表示・出力するための「簡易フロアマップ平面図」のレンダリングも行います。
日本語フォント（MS ゴシック等）に対応し、文字化けを防ぎます。
感熱印刷時の視認性を高めるため、白黒2値（モノクロ線画）かつ対象箇所を斜線ハッチングで表現する機能を搭載。

レシート構成（specs.md §13.1）:
    上部: タイトル・NDC・階数・書架コード
    中央: 大型書架コード表示
    下部: 1. 全体俯瞰図 (平面図レイアウト、対象書架は斜線ハッチング)
          2. 対象書架内詳細位置 (グリッド表示、対象セルは斜線ハッチング)

仕様参照: specs.md §13, §14
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

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
    下部マップは、視認性と文字可読性を高めるため「全体俯瞰図」と「書架詳細」の2種を
    完全な白黒2値（強調箇所は斜線ハッチング）で並置出力します。
    """

    def __init__(self, floor_data: dict) -> None:
        """
        初期化。

        Args:
            floor_data: floor_data JSON 辞書
        """
        self._floor_data = floor_data
        self._floor_map_renderer = FloorMapRenderer(floor_data)

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
        
        # 配架先が特定されている、または禁帯出の場合のみマップを出力（未登録時は白紙）
        if data.placement.found or data.placement.is_restricted:
            parts.append(self._render_floor_map(data))
            parts.append(self._render_shelf_grid(data))
        else:
            # 最小限の余白
            parts.append(Image.new("L", (RECEIPT_WIDTH_PX, 20), 255))

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

    def _render_floor_map(self, data: ReceiptData) -> Image.Image:
        """
        a. 図書館上からの全体俯瞰図 (フロア簡易平面図) をモノクロ線画・ハッチング仕様で描画する。
        """
        seg = data.placement.segment if data.placement.found else None

        if data.placement.is_restricted:
            floor_id = "2f"
            map_img = self._floor_map_renderer.render(floor_id, highlight_restricted=True, monochrome=True)
        elif seg:
            floor_id = seg.floor_id
            map_img = self._floor_map_renderer.render(
                floor_id,
                highlight_shelf_id=seg.shelf_id,
                highlight_segment=seg,
                monochrome=True
            )
        else:
            return Image.new("L", (RECEIPT_WIDTH_PX, 10), 255)

        # レシート印刷幅（384px）に合わせて縮小（高さ192px）
        if map_img.mode != "L":
            map_img = map_img.convert("L")
            
        return map_img.resize((RECEIPT_WIDTH_PX, 192), Image.Resampling.LANCZOS)

    def _render_shelf_grid(self, data: ReceiptData) -> Image.Image:
        """
        b. 対象書架内での位置 (詳細グリッド) をモノクロ線画・ハッチング仕様で描画する。
        """
        seg = data.placement.segment if data.placement.found else None
        
        # 禁帯出の場合は詳細グリッドを描画せず、最小余白のみ返す
        if data.placement.is_restricted or not seg:
            return Image.new("L", (RECEIPT_WIDTH_PX, 10), 255)

        # 384 x 120 のキャンバスを作成（白背景）
        height = 120
        img = Image.new("RGB", (RECEIPT_WIDTH_PX, height), (255, 255, 255))
        draw = ImageDraw.Draw(img)
        font = self._get_font(12)

        # グリッド配置パラメータ
        margin_x = 10
        margin_y = 20
        grid_w = RECEIPT_WIDTH_PX - margin_x * 2
        grid_h = height - margin_y * 2
        
        cell_w = grid_w / data.shelf_cols
        cell_h = grid_h / data.shelf_rows

        target_row = seg.row
        target_col_start = seg.col_start
        target_col_end = seg.col_end

        # グリッドの外枠ラベル描画
        draw.text((margin_x, 3), f"書架 {seg.shelf_id} 内 詳細位置 (ハッチング箇所)", fill=(0, 0, 0), font=font)

        # 各セルの描画
        for r_idx in range(data.shelf_rows):
            for c_idx in range(data.shelf_cols):
                x1 = margin_x + c_idx * cell_w
                y1 = margin_y + r_idx * cell_h
                x2 = x1 + cell_w
                y2 = y1 + cell_h
                
                is_target_cell = (
                    r_idx == target_row
                    and target_col_start <= c_idx <= target_col_end
                )

                rect = [x1, y1, x2, y2]

                if is_target_cell:
                    # 対象セル：白黒2値の斜線ハッチング（太さ2、間隔8）
                    self._floor_map_renderer.draw_hatching_on_image(img, rect, interval=8, color=(0, 0, 0), line_width=2)
                    # ハッチングされたセルの外枠を太めの黒線（太さ3）で描く
                    draw.rectangle(rect, outline=(0, 0, 0), width=3)
                else:
                    # 通常セル：白背景に黒枠（太さ2）
                    draw.rectangle(rect, fill=(255, 255, 255), outline=(0, 0, 0), width=2)

        # モノクロ（L）モードに変換して返す
        return img.convert("L")

    @staticmethod
    def _concat_vertical(images: list[Image.Image]) -> Image.Image:
        """
        複数の画像を縦方向に結合する。
        """
        total_height = sum(img.height for img in images)
        result = Image.new("L", (RECEIPT_WIDTH_PX, total_height), 255)

        y_offset = 0
        for img in images:
            result.paste(img, (0, y_offset))
            y_offset += img.height

        return result


class FloorMapRenderer:
    """
    フロアマップ簡易イラスト描画クラス。

    Pillow を使用して、指定フロアの平面レイアウト図（壁、カウンター、書架、階段、禁帯出等）を描画する。
    カラー表示（GUI用）とモノクロハッチング表示（レシート印刷用）の両方に対応。
    """

    def __init__(self, floor_data: dict) -> None:
        """
        初期化。

        Args:
            floor_data: floor_data JSON 辞書
        """
        self._floor_data = floor_data

    def _get_font(self, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        """
        利用可能な日本語フォントオブジェクトを取得する。
        """
        font_names = ["msgothic.ttc", "meiryo.ttc", "msgothic.ttf"]
        for name in font_names:
            try:
                return ImageFont.truetype(name, size)
            except OSError:
                continue
        # フォールバック
        return ImageFont.load_default()

    def draw_hatching_on_image(
        self,
        img: Image.Image,
        rect: list[float] | tuple[float, float, float, float],
        interval: int = 10,
        color: tuple[int, int, int] = (0, 0, 0),
        line_width: int = 1
    ) -> None:
        """
        指定した長方形の範囲内からはみ出さずに、斜線ハッチングを描画するヘルパー。
        """
        x1, y1, x2, y2 = int(rect[0]), int(rect[1]), int(rect[2]), int(rect[3])
        w = x2 - x1
        h = y2 - y1
        if w <= 0 or h <= 0:
            return

        # 斜線パターンをマスクとして生成
        mask = Image.new("L", (w, h), 0)
        mask_draw = ImageDraw.Draw(mask)
        for offset in range(-h, w, interval):
            mask_draw.line([(offset, 0), (offset + h, h)], fill=255, width=line_width)
        
        # 斜線を描いたカラーのテンポラリ画像
        temp_img = Image.new("RGB", (w, h), (255, 255, 255))
        temp_draw = ImageDraw.Draw(temp_img)
        for offset in range(-h, w, interval):
            temp_draw.line([(offset, 0), (offset + h, h)], fill=color, width=line_width)
        
        # マスクを適用してペースト
        img.paste(temp_img, (x1, y1), mask=mask)

    def render(
        self,
        floor_id: str,
        highlight_shelf_id: str | None = None,
        highlight_segment: Any | None = None,
        highlight_restricted: bool = False,
        monochrome: bool = False,
    ) -> Image.Image:
        """
        指定フロアの平面イラストを描画し、対象箇所を強調した画像を返す。

        Args:
            floor_id: 描画対象のフロア ID ("1f", "2f" など)
            highlight_shelf_id: 強調する書架 ID
            highlight_segment: 強調する書架の NDC セグメント情報 (ShelfSegment)
            highlight_restricted: 禁帯出エリア全体を赤くハイライトする場合 True
            monochrome: レシート印刷用の白黒2値（線画・斜線ハッチング）にする場合 True

        Returns:
            Image.Image: レンダリングされた 800x400 ピクセルの画像
        """
        width = 800
        height = 400
        # 白背景でキャンバスを生成
        img = Image.new("RGB", (width, height), (255, 255, 255))
        draw = ImageDraw.Draw(img)

        # 該当フロアのデータを取得
        floor = None
        for f in self._floor_data.get("floors", []):
            if f.get("id") == floor_id:
                floor = f
                break

        if not floor:
            return img

        font_sm = self._get_font(12)
        font_md = self._get_font(16)

        # 1. 各オブジェクトを描画（背景と形状）
        for obj in floor.get("objects", []):
            obj_type = obj.get("type", "")
            obj_id = obj.get("id", "")
            x = obj.get("x", 0)
            y = obj.get("y", 0)
            w = obj.get("width", 0)
            h = obj.get("height", 0)

            rect = [x, y, x + w, y + h]

            if obj_type == "wall":
                # 壁: 太い黒線（モノクロ時は完全な黒）
                fill_color = (0, 0, 0) if monochrome else (15, 23, 42)
                draw.rectangle(rect, fill=fill_color)

            elif obj_type == "desk":
                # カウンター: 白または薄い灰色 ＋ 黒枠（モノクロ時は太さ2）
                fill = (255, 255, 255) if monochrome else (241, 245, 249)
                width_border = 2 if monochrome else 1
                draw.rectangle(rect, fill=fill, outline=(0, 0, 0), width=width_border)

            elif obj_type == "return_box":
                # 返却BOX（モノクロ時は太さ2）
                fill = (255, 255, 255) if monochrome else (241, 245, 249)
                width_border = 2 if monochrome else 1
                draw.rectangle(rect, fill=fill, outline=(0, 0, 0), width=width_border)

            elif obj_type == "stairs":
                # 階段: 斜線ハッチング（モノクロ時は太さ2）
                width_border = 2 if monochrome else 1
                draw.rectangle(rect, fill=(255, 255, 255), outline=(0, 0, 0), width=width_border)
                
                # 階段用の斜線をハッチングヘルパーで描画（モノクロ時は太さ2）
                color_line = (148, 163, 184) if not monochrome else (0, 0, 0)
                line_w = 1 if not monochrome else 2
                self.draw_hatching_on_image(img, rect, interval=15, color=color_line, line_width=line_w)

            elif obj_type == "restricted":
                # 禁帯出エリア
                if monochrome:
                    # モノクロ印刷用：枠線太さ2
                    draw.rectangle(rect, fill=(255, 255, 255), outline=(0, 0, 0), width=2)
                    if highlight_restricted:
                        # 禁帯出判定時：黒の斜線ハッチングで強調（太さ2、間隔12）
                        self.draw_hatching_on_image(img, rect, interval=12, color=(0, 0, 0), line_width=2)
                        draw.rectangle(rect, outline=(0, 0, 0), width=3)
                else:
                    # カラー画面用：
                    if highlight_restricted:
                        fill_color = (254, 226, 226)
                        border_color = (239, 68, 68)
                        width_border = 3
                    else:
                        fill_color = (254, 243, 199)
                        border_color = (245, 158, 11)
                        width_border = 1
                    draw.rectangle(rect, fill=fill_color, outline=border_color, width=width_border)

            elif obj_type == "shelf":
                rows = obj.get("rows", 5)
                cols = obj.get("cols", 8)
                
                is_target_shelf = (highlight_shelf_id == obj_id)

                if is_target_shelf and highlight_segment:
                    if monochrome:
                        # モノクロ印刷用：対象書架全体を斜線ハッチングで覆う（太さ2、間隔12）
                        draw.rectangle(rect, fill=(255, 255, 255), outline=(0, 0, 0), width=3)
                        self.draw_hatching_on_image(img, rect, interval=12, color=(0, 0, 0), line_width=2)
                    else:
                        # カラー画面用：対象セルの赤色ハイライト
                        draw.rectangle(rect, fill=(255, 255, 255), outline=(59, 130, 246), width=3)
                        
                        cell_w = w / cols
                        cell_h = h / rows
                        
                        target_row = highlight_segment.row
                        target_col_start = highlight_segment.col_start
                        target_col_end = highlight_segment.col_end

                        for r_idx in range(rows):
                            for c_idx in range(cols):
                                cx1 = x + c_idx * cell_w
                                cy1 = y + r_idx * cell_h
                                cx2 = cx1 + cell_w
                                cy2 = cy1 + cell_h
                                
                                is_target_cell = (
                                    r_idx == target_row
                                    and target_col_start <= c_idx <= target_col_end
                                )

                                if is_target_cell:
                                    draw.rectangle([cx1, cy1, cx2, cy2], fill=(239, 68, 68), outline=(0, 0, 0))
                                else:
                                    draw.rectangle([cx1, cy1, cx2, cy2], fill=(248, 250, 252), outline=(226, 232, 240))
                else:
                    # 通常書架:
                    fill = (255, 255, 255) if monochrome else (226, 232, 240)
                    outline_color = (0, 0, 0) if monochrome else (148, 163, 184)
                    width_border = 2 if monochrome else 1
                    draw.rectangle(rect, fill=fill, outline=outline_color, width=width_border)

        # 2. テキストおよびラベルを上に重ねて描画（ハッチングで文字が消えないように最後に描画）
        for obj in floor.get("objects", []):
            obj_type = obj.get("type", "")
            obj_id = obj.get("id", "")
            x = obj.get("x", 0)
            y = obj.get("y", 0)
            w = obj.get("width", 0)
            h = obj.get("height", 0)

            # テキスト描画色の決定
            if monochrome:
                text_color = (0, 0, 0)
            else:
                text_color = (71, 85, 105)

            if obj_type == "desk":
                draw.text((x + 10, y + h // 2 - 8), "カウンター", fill=text_color, font=font_sm)
            elif obj_type == "return_box":
                draw.text((x + 5, y + h // 2 - 8), "返却BOX", fill=text_color, font=font_sm)
            elif obj_type == "stairs":
                draw.text((x + 5, y + 5), "階段", fill=text_color, font=font_sm)
            elif obj_type == "restricted":
                if not monochrome and highlight_restricted:
                    t_color = (185, 28, 28)
                elif not monochrome:
                    t_color = (180, 83, 9)
                else:
                    t_color = (0, 0, 0)
                draw.text((x + w // 2 - 18, y + h // 2 - 8), "禁帯出", fill=t_color, font=font_sm)
            elif obj_type == "shelf":
                is_target_shelf = (highlight_shelf_id == obj_id)
                if is_target_shelf and highlight_segment:
                    t_color = (0, 0, 0) if monochrome else (29, 78, 216)
                    draw.text((x + 2, y - 18), f"★書架 {obj_id}", fill=t_color, font=font_md)
                else:
                    draw.text((x + 2, y + 2), obj_id, fill=text_color, font=font_sm)

        return img
