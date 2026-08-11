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


def _layout(
    cols: int,
    rows: int,
    palette_size: int,
    cell_size: int,
    header_style: str,
):
    cell = int(cell_size)
    outer = max(18, cell)
    coordinate = max(18, round(cell * 1.25))
    header = {
        "detailed": max(116, round(cell * 6.2)),
        "compact": max(62, round(cell * 3.2)),
        "none": 0,
    }[header_style]
    legend_gap = max(16, cell)
    legend_item_min_width = max(188, round(cell * 10.2))
    legend_item_max_width = max(280, round(cell * 15))
    legend_item_gap = max(8, round(cell * 0.5))
    legend_columns = min(
        max(1, palette_size),
        min(12, max(4, ceil(palette_size / 6))),
    )
    grid_span = cols * cell + coordinate * 2
    minimum_legend_span = (
        legend_item_min_width * legend_columns
        + legend_item_gap * max(0, legend_columns - 1)
    )
    width = max(grid_span, minimum_legend_span) + outer * 2
    available_legend_width = width - outer * 2
    legend_item_width = min(
        legend_item_max_width,
        (available_legend_width - legend_item_gap * max(0, legend_columns - 1))
        // legend_columns,
    )
    legend_span = legend_item_width * legend_columns + legend_item_gap * max(
        0, legend_columns - 1
    )
    legend_left = (width - legend_span) // 2
    legend_rows = ceil(palette_size / legend_columns) if palette_size else 0
    legend_heading = max(32, round(cell * 1.8))
    legend_row_height = max(48, round(cell * 2.55))
    legend_footer = max(30, round(cell * 1.7))
    legend_height = (
        legend_heading + legend_rows * legend_row_height + legend_footer
        if palette_size
        else 0
    )
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
        "legend_item_gap": legend_item_gap,
        "legend_columns": legend_columns,
        "legend_left": legend_left,
        "legend_heading": legend_heading,
        "legend_row_height": legend_row_height,
        "legend_footer": legend_footer,
        "width": width,
        "height": height,
        "grid_left": grid_left,
        "grid_top": grid_top,
        "grid_bottom": grid_bottom,
    }


def _draw_header(
    draw,
    layout,
    *,
    title: str,
    header_style: str,
    cols: int,
    rows: int,
    color_count: int,
    bead_count: int,
) -> None:
    if header_style == "none":
        return

    outer = layout["outer"]
    right = layout["width"] - outer
    top = outer
    display_title = title or "BEAD ASSEMBLY CHART"
    brand_font = _load_font(9, mono=True, bold=True)
    label_font = _load_font(8, mono=True)
    value_font = _load_font(14, mono=True, bold=True)
    draw.rounded_rectangle(
        (outer, top, outer + 32, top + 32),
        radius=3,
        fill="#1b1e26",
    )
    draw.text(
        (outer + 16, top + 16),
        "EG",
        fill="#e3cf62",
        font=_load_font(11, mono=True, bold=True),
        anchor="mm",
    )
    draw.text(
        (outer + 44, top + 1),
        "EDGEGLYPH / PATTERN SHEET",
        fill="#6f7580",
        font=brand_font,
    )

    if header_style == "compact":
        metadata = f"{cols} x {rows}  /  {color_count} COLORS  /  {bead_count:,} BEADS"
        metadata_width = draw.textlength(metadata, font=label_font)
        title_width = max(120, right - (outer + 44) - metadata_width - 28)
        title_font = _fit_font(
            draw,
            display_title,
            title_width,
            19,
            bold=True,
        )
        draw.text(
            (outer + 44, top + 14),
            display_title,
            fill="#1b1e26",
            font=title_font,
        )
        draw.text(
            (right, top + 20),
            metadata,
            fill="#4e5460",
            font=label_font,
            anchor="ra",
        )
    else:
        title_font = _fit_font(
            draw,
            display_title,
            right - (outer + 44),
            24,
            bold=True,
        )
        draw.text(
            (outer + 44, top + 14),
            display_title,
            fill="#1b1e26",
            font=title_font,
        )

        empty = cols * rows - bead_count
        coverage = bead_count / max(1, cols * rows)
        metrics = (
            ("GRID", f"{cols} x {rows}"),
            ("COLORS", str(color_count)),
            ("BEADS", f"{bead_count:,}"),
            ("EMPTY", f"{empty:,}"),
            ("COVERAGE", f"{coverage:.1%}"),
        )
        metric_top = top + 54
        metric_width = (right - outer) / len(metrics)
        for index, (label, value) in enumerate(metrics):
            x = outer + index * metric_width
            if index:
                draw.line(
                    (x, metric_top, x, metric_top + 35),
                    fill="#d9dce1",
                    width=1,
                )
            draw.text(
                (x + 10, metric_top),
                label,
                fill="#818792",
                font=label_font,
            )
            draw.text(
                (x + 10, metric_top + 13),
                value,
                fill="#242731",
                font=value_font,
            )

    rule_y = outer + layout["header"] - 10
    draw.rectangle((outer, rule_y, outer + 46, rule_y + 3), fill="#e3cf62")
    draw.line((outer + 54, rule_y + 1, right, rule_y + 1), fill="#cfd3d9", width=1)


def _draw_legend(draw, layout, colors, counts, bead_count: int) -> None:
    if not colors:
        return

    top = layout["grid_bottom"] + layout["coordinate"] + layout["legend_gap"]
    left = layout["outer"]
    right = layout["width"] - layout["outer"]
    heading_font = _load_font(12, mono=True, bold=True)
    detail_font = _load_font(8, mono=True)
    code_font = _load_font(11, mono=True, bold=True)
    count_font = _load_font(10, mono=True, bold=True)
    draw.text((left, top), "COLOR KEY", fill="#242731", font=heading_font)
    draw.text(
        (right, top + 1),
        f"{len(colors)} COLORS  /  {bead_count:,} TOTAL BEADS",
        fill="#69707c",
        font=detail_font,
        anchor="ra",
    )
    draw.line(
        (
            left,
            top + layout["legend_heading"] - 9,
            right,
            top + layout["legend_heading"] - 9,
        ),
        fill="#cfd3d9",
        width=1,
    )

    items_top = top + layout["legend_heading"]
    item_width = layout["legend_item_width"]
    item_gap = layout["legend_item_gap"]
    for index, (rgb, count) in enumerate(zip(colors, counts)):
        column = index % layout["legend_columns"]
        row = index // layout["legend_columns"]
        x = layout["legend_left"] + column * (item_width + item_gap)
        y = items_top + row * layout["legend_row_height"]
        item_bottom = y + layout["legend_row_height"] - item_gap
        draw.rounded_rectangle(
            (x, y, x + item_width, item_bottom),
            radius=5,
            fill="#fafaf8",
            outline="#dde0e4",
            width=1,
        )
        swatch = item_bottom - y - 10
        draw.rounded_rectangle(
            (x + 5, y + 5, x + 5 + swatch, item_bottom - 5),
            radius=3,
            fill=rgb,
            outline="#aeb3bc",
            width=1,
        )
        text_x = x + swatch + 13
        draw.text(
            (text_x, y + 6),
            _code(index, len(colors)),
            fill="#20232b",
            font=code_font,
        )
        hex_color = f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"
        draw.text(
            (text_x, y + 23),
            hex_color,
            fill="#727985",
            font=detail_font,
        )
        percentage = count / max(1, bead_count)
        draw.text(
            (x + item_width - 8, y + 7),
            f"x{count:,}",
            fill="#20232b",
            font=count_font,
            anchor="ra",
        )
        draw.text(
            (x + item_width - 8, y + 24),
            f"{percentage:.1%}",
            fill="#727985",
            font=detail_font,
            anchor="ra",
        )

    rows = ceil(len(colors) / layout["legend_columns"])
    footer_y = items_top + rows * layout["legend_row_height"] + 3
    draw.line((left, footer_y, right, footer_y), fill="#d9dce1", width=1)
    draw.text(
        (left, footer_y + 10),
        "CODES ARE LOCAL TO THIS CHART  /  MATCH PHYSICAL BEADS BY HEX COLOR",
        fill="#7b818c",
        font=detail_font,
    )


def draw_bead_chart(
    path: str | Path,
    palette,
    color_indices,
    cols: int,
    rows: int,
    *,
    title: str = "",
    cell_size: int = 18,
    header_style: str = "detailed",
    major_interval: int = 10,
) -> None:
    """Draw a printable color-code grid with coordinates and palette counts."""

    title = title.strip()
    if "\n" in title or "\r" in title or len(title) > 160:
        raise ValueError("chart title must be one line and at most 160 characters")
    if not 12 <= cell_size <= 32:
        raise ValueError("chart cell size must be between 12 and 32")
    if header_style not in {"detailed", "compact", "none"}:
        raise ValueError(f"unsupported chart header style: {header_style}")
    if len(color_indices) != rows or any(len(row) != cols for row in color_indices):
        raise ValueError("bead chart grid does not match its configured dimensions")

    colors = _palette_rgb(palette)
    counts = _palette_counts(color_indices, len(colors))
    bead_count = sum(counts)
    layout = _layout(cols, rows, len(colors), cell_size, header_style)
    cell = layout["cell"]
    grid_left = layout["grid_left"]
    grid_top = layout["grid_top"]
    grid_right = grid_left + cols * cell
    grid_bottom = layout["grid_bottom"]

    canvas = Image.new("RGB", (layout["width"], layout["height"]), "#f5f6f7")
    draw = ImageDraw.Draw(canvas)
    _draw_header(
        draw,
        layout,
        title=title,
        header_style=header_style,
        cols=cols,
        rows=rows,
        color_count=len(colors),
        bead_count=bead_count,
    )

    code_font = _load_font(max(7, round(cell * 0.42)), mono=True)
    coordinate_font = _load_font(max(7, round(cell * 0.32)), mono=True)
    minor_grid = "#d8dce1"
    major_grid = "#d06a6c"
    draw.rectangle((grid_left, grid_top, grid_right, grid_bottom), fill="#ffffff")

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
    draw.rectangle(
        (grid_left, grid_top, grid_right, grid_bottom),
        outline="#3e434d",
        width=2,
    )

    coordinate_fill = "#656b75"
    coordinate_major = "#b34f52"
    coordinate_major_font = _load_font(max(7, round(cell * 0.32)), mono=True, bold=True)
    for col in range(cols):
        x = grid_left + (col + 0.5) * cell
        label = str(col + 1)
        emphasized = (col + 1) % major_interval == 0
        draw.text(
            (x, grid_top - layout["coordinate"] / 2),
            label,
            fill=coordinate_major if emphasized else coordinate_fill,
            font=coordinate_major_font if emphasized else coordinate_font,
            anchor="mm",
        )
        draw.text(
            (x, grid_bottom + layout["coordinate"] / 2),
            label,
            fill=coordinate_major if emphasized else coordinate_fill,
            font=coordinate_major_font if emphasized else coordinate_font,
            anchor="mm",
        )
    for row in range(rows):
        y = grid_top + (row + 0.5) * cell
        label = str(row + 1)
        emphasized = (row + 1) % major_interval == 0
        draw.text(
            (grid_left - layout["coordinate"] / 2, y),
            label,
            fill=coordinate_major if emphasized else coordinate_fill,
            font=coordinate_major_font if emphasized else coordinate_font,
            anchor="mm",
        )
        draw.text(
            (grid_right + layout["coordinate"] / 2, y),
            label,
            fill=coordinate_major if emphasized else coordinate_fill,
            font=coordinate_major_font if emphasized else coordinate_font,
            anchor="mm",
        )

    _draw_legend(draw, layout, colors, counts, bead_count)

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(destination, optimize=True)


__all__ = ["MAX_CHART_PIXELS", "draw_bead_chart"]
