from pathlib import Path

from PIL import Image, ImageDraw

from src.layouts.base import BaseLayout, _get_font, _hex_to_rgb, _text_width, _wrap_text
from src.parser import Segment


class TableLayout(BaseLayout):
    def render(self, segment: Segment, cfg: dict, output_dir: Path) -> str:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"segment_{segment.index:04d}.png"
        width, height = cfg["width"], cfg["height"]
        bg = _hex_to_rgb(cfg["bg_color"])
        accent = _hex_to_rgb(cfg["accent_color"])
        text_color = _hex_to_rgb(cfg["text_color"])

        image = Image.new("RGB", (width, height), bg)
        draw = ImageDraw.Draw(image)
        draw.rectangle([0, 0, width, 8], fill=accent)

        title_font = _get_font(cfg["font_family"], cfg["font_size_title"])
        cell_font = _get_font(
            cfg["font_family"],
            max(18, int(cfg["font_size_body"] * 0.72)),
        )
        header_font = _get_font(
            cfg["font_family"],
            max(20, int(cfg["font_size_body"] * 0.78)),
        )

        y = 70
        if segment.title:
            draw.text((70, y), segment.title, font=title_font, fill=text_color)
            y += cfg["font_size_title"] + 50

        rows = segment.table_data or []
        if rows:
            _draw_table(
                draw,
                rows,
                cell_font,
                header_font,
                text_color,
                accent,
                width,
                height,
                y,
            )

        image.save(output_path)
        return str(output_path)


def _draw_table(
    draw: ImageDraw.ImageDraw,
    rows: list[list[str]],
    cell_font,
    header_font,
    text_color: tuple[int, int, int],
    accent: tuple[int, int, int],
    width: int,
    height: int,
    top: int,
) -> None:
    left = 70
    right = width - 70
    max_bottom = height - 70
    column_count = max(len(row) for row in rows)
    column_widths = _column_widths(rows, column_count, right - left, cell_font, header_font)
    y = top
    line_color = (210, 216, 224)
    header_bg = _tint(accent, 0.18)
    row_bg = (255, 255, 255)
    alt_bg = (238, 243, 248)

    for row_index, row in enumerate(rows):
        font = header_font if row_index == 0 else cell_font
        wrapped_cells = [
            _wrap_text(str(_cell(row, index)), font, max(40, column_widths[index] - 24))
            for index in range(column_count)
        ]
        row_height = max(
            54,
            max(len(lines) for lines in wrapped_cells) * (font.size + 8) + 24,
        )
        if y + row_height > max_bottom:
            break

        fill = header_bg if row_index == 0 else (alt_bg if row_index % 2 == 0 else row_bg)
        draw.rectangle([left, y, right, y + row_height], fill=fill)

        x = left
        for column_index, lines in enumerate(wrapped_cells):
            next_x = x + column_widths[column_index]
            draw.rectangle([x, y, next_x, y + row_height], outline=line_color, width=1)
            text_y = y + 14
            for line in lines[:3]:
                draw.text((x + 12, text_y), line, font=font, fill=text_color)
                text_y += font.size + 8
            x = next_x
        y += row_height


def _column_widths(
    rows: list[list[str]],
    column_count: int,
    total_width: int,
    cell_font,
    header_font,
) -> list[int]:
    weights = []
    for column in range(column_count):
        font = header_font if column == 0 else cell_font
        widest = max(_text_width(str(_cell(row, column)), font) for row in rows)
        weights.append(max(1, min(widest, 360)))
    total_weight = sum(weights) or 1
    widths = [max(120, int(total_width * weight / total_weight)) for weight in weights]
    overflow = sum(widths) - total_width
    while overflow > 0:
        index = widths.index(max(widths))
        reduction = min(overflow, widths[index] - 120)
        if reduction <= 0:
            break
        widths[index] -= reduction
        overflow -= reduction
    widths[-1] += total_width - sum(widths)
    return widths


def _cell(row: list[str], index: int) -> str:
    return row[index] if index < len(row) else ""


def _tint(color: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    return tuple(int(channel + (255 - channel) * amount) for channel in color)
