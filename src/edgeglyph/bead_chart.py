"""Numbered assembly-chart exporter for fuse-bead patterns."""

from __future__ import annotations

from math import ceil
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


MAX_CHART_PIXELS = 120_000_000


def _font_candidates(*, mono: bool, bold: bool) -> tuple[str, ...]:
    if mono:
        return (
            "/System/Library/Fonts/SFNSMono.ttf",
            "/System/Library/Fonts/Menlo.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
            "C:/Windows/Fonts/consola.ttf",
            "DejaVuSansMono.ttf",
        )
    if bold:
        return (
            str(Path.home() / "Library/Fonts/LXGWWenKai-Medium.ttf"),
            "/System/Library/Fonts/STHeiti Medium.ttc",
            "/System/Library/Fonts/Supplemental/Songti.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "C:/Windows/Fonts/msyhbd.ttc",
            "DejaVuSans-Bold.ttf",
        )
    return (
        str(Path.home() / "Library/Fonts/LXGWWenKai-Regular.ttf"),
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Supplemental/Songti.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/msyh.ttc",
        "DejaVuSans.ttf",
    )


def _load_font(size: int, *, mono: bool = False, bold: bool = False):
    for candidate in _font_candidates(mono=mono, bold=bold):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def _fit_font(draw, text: str, maximum_width: int, size: int, *, bold=False):
    while size > 12:
        font = _load_font(size, bold=bold)
        if draw.textlength(text, font=font) <= maximum_width:
            return font
        size -= 1
    return _load_font(12, bold=bold)


def _palette_rgb(palette) -> list[tuple[int, int, int]]:
    colors = np.clip(np.rint(np.asarray(palette) * 255), 0, 255).astype(np.uint8)
    return [tuple(int(channel) for channel in color) for color in colors]


def _palette_counts(color_indices, count: int) -> list[int]:
    counts = [0] * count
    for row in color_indices:
        for color_index in row:
            if color_index is not None:
                counts[color_index - 1] += 1
    return counts


def _code(index: int, palette_size: int) -> str:
    width = max(2, len(str(palette_size)))
    return f"C{index + 1:0{width}d}"


def _text_color(rgb: tuple[int, int, int]) -> tuple[int, int, int]:
    luminance = (299 * rgb[0] + 587 * rgb[1] + 114 * rgb[2]) / 1000
    return (28, 30, 36) if luminance >= 154 else (250, 250, 248)


def _layout(cols: int, rows: int, palette_size: int, cell_size: int, title: str):
    cell = int(cell_size)
    outer = max(14, cell)
    coordinate = max(18, round(cell * 1.25))
    header = max(54, round(cell * 2.8)) if title else 0
    legend_gap = max(16, cell)
    legend_item_width = max(132, cell * 7)
    legend_columns = min(max(1, palette_size), 6)
    grid_span = cols * cell + coordinate * 2
    legend_span = legend_item_width * legend_columns
    width = max(grid_span, legend_span) + outer * 2
    legend_columns = max(1, (width - outer * 2) // legend_item_width)
    legend_rows = ceil(palette_size / legend_columns) if palette_size else 0
    legend_row_height = max(28, cell + 8)
    legend_height = legend_rows * legend_row_height + (outer if palette_size else 0)
    grid_left = (width - cols * cell) // 2
    grid_top = outer + header + coordinate
    grid_bottom = grid_top + rows * cell
    height = grid_bottom + coordinate + legend_gap + legend_height + outer
    if width * height > MAX_CHART_PIXELS:
        raise ValueError(
            "bead chart is too large; reduce the grid or --chart-cell-size"
        )
    return {
        "cell": cell,
        "outer": outer,
        "coordinate": coordinate,
        "header": header,
        "legend_gap": legend_gap,
        "legend_item_width": legend_item_width,
        "legend_columns": legend_columns,
        "legend_row_height": legend_row_height,
        "width": width,
        "height": height,
        "grid_left": grid_left,
        "grid_top": grid_top,
        "grid_bottom": grid_bottom,
    }


def draw_bead_chart(
    path: str | Path,
    palette,
    color_indices,
    cols: int,
    rows: int,
    *,
    title: str = "",
    cell_size: int = 18,
    major_interval: int = 10,
) -> None:
    """Draw a printable color-code grid with coordinates and palette counts."""

    title = title.strip()
    if "\n" in title or "\r" in title or len(title) > 160:
        raise ValueError("chart title must be one line and at most 160 characters")
    if not 12 <= cell_size <= 32:
        raise ValueError("chart cell size must be between 12 and 32")
    if len(color_indices) != rows or any(len(row) != cols for row in color_indices):
        raise ValueError("bead chart grid does not match its configured dimensions")

    colors = _palette_rgb(palette)
    counts = _palette_counts(color_indices, len(colors))
    layout = _layout(cols, rows, len(colors), cell_size, title)
    cell = layout["cell"]
    grid_left = layout["grid_left"]
    grid_top = layout["grid_top"]
    grid_right = grid_left + cols * cell
    grid_bottom = layout["grid_bottom"]

    canvas = Image.new("RGB", (layout["width"], layout["height"]), "#ffffff")
    draw = ImageDraw.Draw(canvas)

    if title:
        title_font = _fit_font(
            draw,
            title,
            canvas.width - layout["outer"] * 2,
            max(22, round(cell * 1.55)),
            bold=True,
        )
        draw.text(
            (layout["outer"], layout["outer"]),
            title,
            fill="#17191f",
            font=title_font,
        )

    code_font = _load_font(max(7, round(cell * 0.34)), mono=True)
    coordinate_font = _load_font(max(7, round(cell * 0.32)), mono=True)
    minor_grid = "#d8dce1"
    major_grid = "#d35f61"

    for row in range(rows):
        for col in range(cols):
            color_index = color_indices[row][col]
            if color_index is None:
                continue
            if not 1 <= color_index <= len(colors):
                raise ValueError("bead chart contains an invalid palette index")
            x0 = grid_left + col * cell
            y0 = grid_top + row * cell
            rgb = colors[color_index - 1]
            draw.rectangle((x0, y0, x0 + cell, y0 + cell), fill=rgb)
            draw.text(
                (x0 + cell / 2, y0 + cell / 2),
                _code(color_index - 1, len(colors)),
                fill=_text_color(rgb),
                font=code_font,
                anchor="mm",
            )

    for col in range(cols + 1):
        x = grid_left + col * cell
        major = col % major_interval == 0
        draw.line(
            (x, grid_top, x, grid_bottom),
            fill=major_grid if major else minor_grid,
            width=2 if major else 1,
        )
    for row in range(rows + 1):
        y = grid_top + row * cell
        major = row % major_interval == 0
        draw.line(
            (grid_left, y, grid_right, y),
            fill=major_grid if major else minor_grid,
            width=2 if major else 1,
        )

    coordinate_fill = "#656b75"
    for col in range(cols):
        x = grid_left + (col + 0.5) * cell
        label = str(col + 1)
        draw.text(
            (x, grid_top - layout["coordinate"] / 2),
            label,
            fill=coordinate_fill,
            font=coordinate_font,
            anchor="mm",
        )
        draw.text(
            (x, grid_bottom + layout["coordinate"] / 2),
            label,
            fill=coordinate_fill,
            font=coordinate_font,
            anchor="mm",
        )
    for row in range(rows):
        y = grid_top + (row + 0.5) * cell
        label = str(row + 1)
        draw.text(
            (grid_left - layout["coordinate"] / 2, y),
            label,
            fill=coordinate_fill,
            font=coordinate_font,
            anchor="mm",
        )
        draw.text(
            (grid_right + layout["coordinate"] / 2, y),
            label,
            fill=coordinate_fill,
            font=coordinate_font,
            anchor="mm",
        )

    legend_top = grid_bottom + layout["coordinate"] + layout["legend_gap"]
    legend_font = _load_font(max(9, round(cell * 0.48)), mono=True)
    for index, (rgb, count) in enumerate(zip(colors, counts)):
        column = index % layout["legend_columns"]
        row = index // layout["legend_columns"]
        x = layout["outer"] + column * layout["legend_item_width"]
        y = legend_top + row * layout["legend_row_height"]
        swatch = max(18, cell)
        draw.rounded_rectangle(
            (x, y, x + swatch, y + swatch),
            radius=3,
            fill=rgb,
            outline="#adb2bb",
            width=1,
        )
        hex_color = f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"
        label = f"{_code(index, len(colors))}  {hex_color}  x{count}"
        draw.text(
            (x + swatch + 7, y + swatch / 2),
            label,
            fill="#252830",
            font=legend_font,
            anchor="lm",
        )

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(destination, optimize=True)


__all__ = ["MAX_CHART_PIXELS", "draw_bead_chart"]
