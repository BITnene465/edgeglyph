"""Mode-independent result formatting and file exporters."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .engine import draw_bead_preview, draw_preview, write_debug, write_lua, write_text


def palette_hex(palette: np.ndarray) -> list[str]:
    colors = np.clip(np.rint(palette * 255), 0, 255).astype(np.uint8)
    return [f"#{red:02x}{green:02x}{blue:02x}" for red, green, blue in colors]


def result_text(result) -> str:
    content = "\n".join(line.rstrip() for line in result.lines).rstrip()
    return content + "\n"


def result_metrics(mode: str, result) -> dict:
    metrics = {
        **result.metrics,
        "mode": mode,
        "cols": result.config.cols,
        "rows": result.config.rows,
        "colors": len(result.palette),
    }
    if mode != "bead":
        metrics["characters"] = len(set("".join(result.lines).replace(" ", "")))
    else:
        counts = [0] * len(result.palette)
        for row in result.color_indices:
            for color_index in row:
                if color_index is not None:
                    counts[color_index - 1] += 1
        metrics["palette"] = palette_hex(result.palette)
        metrics["palette_counts"] = counts
    return metrics


def save_result(
    result,
    *,
    text_path: Path | None = None,
    lua_path: Path | None = None,
    preview_path: Path | None = None,
    metrics_path: Path | None = None,
    debug_dir: Path | None = None,
    mode: str,
    font: Path | None = None,
    fallback_font: Path | None = None,
) -> dict:
    for path in (text_path, lua_path, preview_path, metrics_path):
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
    if text_path:
        write_text(text_path, result.lines)
    if lua_path:
        write_lua(
            lua_path,
            result.glyphs,
            result.selected,
            result.palette,
            result.color_indices,
            result.config.cols,
            result.config.rows,
            result.background_indices,
        )
    if preview_path:
        if mode == "bead":
            draw_bead_preview(
                preview_path,
                result.palette,
                result.color_indices,
                result.config.cols,
                result.config.rows,
                result.config,
            )
        else:
            draw_preview(
                preview_path,
                font,
                fallback_font,
                result.glyphs,
                result.selected,
                result.palette,
                result.color_indices,
                result.config.cols,
                result.config.rows,
                background_indices=result.background_indices,
            )
    if debug_dir:
        write_debug(
            debug_dir,
            result.source,
            result.glyphs,
            result.selected,
            result.config.cols,
            result.config.rows,
            result.config.cell_width,
            result.config.cell_height,
        )

    metrics = result_metrics(mode, result)
    if metrics_path:
        metrics_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    return metrics


__all__ = [
    "draw_preview",
    "draw_bead_preview",
    "palette_hex",
    "result_metrics",
    "result_text",
    "save_result",
    "write_debug",
    "write_lua",
    "write_text",
]
