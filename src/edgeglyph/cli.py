import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .engine import (
    BlockConfig,
    RenderConfig,
    draw_preview,
    render,
    render_blocks,
    write_debug,
    write_lua,
    write_text,
)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="edgeglyph",
        description="Convert images to terminal block art or structure-aware glyph art.",
    )
    parser.add_argument("source", type=Path)
    parser.add_argument("--style", choices=("block", "glyph"), default="block")
    parser.add_argument(
        "--font", type=Path, help="Primary monospace TTF/OTF font for glyph style"
    )
    parser.add_argument(
        "--fallback-font", type=Path, help="Font used for Unicode line symbols"
    )
    parser.add_argument("--cols", type=int, default=56)
    parser.add_argument("--rows", type=int, default=28)
    parser.add_argument(
        "--foreground", default="#cba6f7", help="Block foreground color as #RRGGBB"
    )
    parser.add_argument("--subject-threshold", type=float, default=0.34)
    parser.add_argument("--ink-threshold", type=float, default=0.46)
    parser.add_argument("--detail", type=float, default=1.0)
    parser.add_argument("--oversample", type=int, default=6)
    parser.add_argument("--fit", choices=("contain", "cover"), default="cover")
    parser.add_argument("--focus-y", type=float, default=0.36)
    parser.add_argument("--colors", type=int, default=16)
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--min-luminance", type=float, default=0.72)
    parser.add_argument(
        "--fill-mode", choices=("none", "salient", "tone"), default="none"
    )
    parser.add_argument("--continuity", type=float, default=0.4)
    parser.add_argument("--diversity", type=float, default=1.5)
    parser.add_argument(
        "--line-renderer",
        choices=("sprite", "font"),
        default="sprite",
        help="Model box-drawing characters as terminal sprites or fallback-font glyphs",
    )
    parser.add_argument("-o", "--output", type=Path, help="Write plain UTF-8 glyph art")
    parser.add_argument(
        "--lua-output", type=Path, help="Write NvDash-compatible Lua data"
    )
    parser.add_argument("--preview", type=Path, help="Write a color PNG preview")
    parser.add_argument(
        "--debug-dir", type=Path, help="Write edge and mask diagnostics"
    )
    parser.add_argument("--metrics", type=Path, help="Write structural metrics as JSON")
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    return parser


def ensure_parent(path):
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.style == "block":
        config = BlockConfig(
            cols=args.cols,
            rows=args.rows,
            foreground=args.foreground,
            subject_threshold=args.subject_threshold,
            ink_threshold=args.ink_threshold,
            detail=args.detail,
            oversample=args.oversample,
            fit=args.fit,
            focus_y=args.focus_y,
        )
        result = render_blocks(args.source, config)
    else:
        if args.font is None:
            parser.error("--font is required with --style glyph")
        config = RenderConfig(
            cols=args.cols,
            rows=args.rows,
            colors=args.colors,
            top_k=args.top_k,
            minimum_luminance=args.min_luminance,
            fill_mode=args.fill_mode,
            continuity=args.continuity,
            diversity=args.diversity,
            line_renderer=args.line_renderer,
        )
        result = render(args.source, args.font, args.fallback_font, config)

    for path in (args.output, args.lua_output, args.preview, args.metrics):
        ensure_parent(path)
    if args.output:
        write_text(args.output, result.lines)
    else:
        print("\n".join(result.lines))
    if args.lua_output:
        write_lua(
            args.lua_output,
            result.glyphs,
            result.selected,
            result.palette,
            result.color_indices,
            config.cols,
            config.rows,
        )
    if args.preview:
        draw_preview(
            args.preview,
            args.font,
            args.fallback_font,
            result.glyphs,
            result.selected,
            result.palette,
            result.color_indices,
            config.cols,
            config.rows,
        )
    if args.debug_dir:
        write_debug(
            args.debug_dir,
            result.source,
            result.glyphs,
            result.selected,
            config.cols,
            config.rows,
            config.cell_width,
            config.cell_height,
        )

    metrics = {
        **result.metrics,
        "style": args.style,
        "cols": config.cols,
        "rows": config.rows,
        "colors": len(result.palette),
        "characters": len(set("".join(result.lines).replace(" ", ""))),
    }
    if args.metrics:
        args.metrics.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metrics, sort_keys=True), file=sys.stderr)
