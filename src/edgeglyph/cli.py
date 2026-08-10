"""Command-line interface organized around explicit renderer modes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .modes import bead, block, glyph
from .outputs import result_text, save_result
from .schema import MODE_PARAMETERS, mode_schema


def _add_schema_arguments(parser: argparse.ArgumentParser, mode: str) -> None:
    frame = parser.add_argument_group("frame")
    controls = parser.add_argument_group(f"{mode} controls")
    for index, parameter in enumerate(MODE_PARAMETERS[mode]):
        group = frame if index < 2 else controls
        kwargs = {
            "dest": parameter.key,
            "default": parameter.default,
            "help": f"{parameter.help} (default: %(default)s)",
        }
        if parameter.kind == "integer":
            kwargs["type"] = int
        elif parameter.kind == "number":
            kwargs["type"] = float
        if parameter.choices:
            kwargs["choices"] = parameter.choices
        group.add_argument(parameter.flag, **kwargs)


def _add_output_arguments(parser: argparse.ArgumentParser) -> None:
    output = parser.add_argument_group("output")
    output.add_argument("-o", "--output", type=Path, help="Plain UTF-8 art file")
    output.add_argument("--lua-output", type=Path, help="NvDash-compatible Lua data")
    output.add_argument("--preview", type=Path, help="Color PNG preview")
    output.add_argument("--debug-dir", type=Path, help="Intermediate diagnostic images")
    output.add_argument("--metrics", type=Path, help="Renderer metrics as JSON")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="edgeglyph",
        description="Convert images into terminal art, glyph art, or fuse-bead patterns.",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    block_parser = commands.add_parser(
        "block",
        help="Render solid Unicode half-block artwork",
        description="Render solid, palette-quantized terminal art with spaces and ▀▄█.",
    )
    block_parser.add_argument("source", type=Path, help="Source image")
    _add_schema_arguments(block_parser, "block")
    _add_output_arguments(block_parser)

    bead_parser = commands.add_parser(
        "bead",
        help="Render a square-grid fuse-bead pattern",
        description="Quantize an image into one color per bead with a physical PNG preview.",
    )
    bead_parser.add_argument("source", type=Path, help="Source image")
    _add_schema_arguments(bead_parser, "bead")
    _add_output_arguments(bead_parser)

    glyph_parser = commands.add_parser(
        "glyph",
        help="Render structure-aware font-matched artwork",
        description="Match source structure against glyphs from a real terminal font.",
    )
    glyph_parser.add_argument("source", type=Path, help="Source image")
    fonts = glyph_parser.add_argument_group("fonts")
    fonts.add_argument(
        "--font", type=Path, required=True, help="Primary monospace TTF/OTF font"
    )
    fonts.add_argument(
        "--fallback-font", type=Path, help="Font used for Unicode line symbols"
    )
    _add_schema_arguments(glyph_parser, "glyph")
    _add_output_arguments(glyph_parser)

    web_parser = commands.add_parser(
        "web",
        help="Start the local visual workbench",
        description="Run the EdgeGlyph workbench on a loopback-only HTTP server.",
    )
    web_parser.add_argument(
        "--host",
        choices=("127.0.0.1", "localhost", "::1"),
        default="127.0.0.1",
        help="Loopback address (default: %(default)s)",
    )
    web_parser.add_argument(
        "--port", type=int, default=8765, help="HTTP port (default: %(default)s)"
    )
    web_parser.add_argument(
        "--open",
        action=argparse.BooleanOptionalAction,
        default=True,
        dest="open_browser",
        help="Open the workbench in the default browser",
    )

    commands.add_parser("schema", help="Print the machine-readable mode schema")
    return parser


def _normalize_legacy_argv(argv: list[str]) -> list[str]:
    """Translate the pre-0.4 flat invocation into an explicit mode command."""

    if not argv or argv[0] in {"bead", "block", "glyph", "web", "schema"}:
        return argv
    if argv[0].startswith("-"):
        return argv

    mode = "block"
    remaining = list(argv)
    for flag in ("--style", "--mode"):
        if flag in remaining:
            index = remaining.index(flag)
            if index + 1 >= len(remaining):
                return argv
            mode = remaining[index + 1]
            del remaining[index : index + 2]
            break
    return [mode, *remaining]


def _config_options(args: argparse.Namespace) -> dict:
    return {
        parameter.key: getattr(args, parameter.key)
        for parameter in MODE_PARAMETERS[args.command]
    }


def _run_renderer(args: argparse.Namespace) -> int:
    options = _config_options(args)
    if args.command == "block":
        result = block.render(args.source, **options)
        font = fallback_font = None
    elif args.command == "bead":
        result = bead.render(args.source, **options)
        font = fallback_font = None
    else:
        result = glyph.render(
            args.source,
            args.font,
            args.fallback_font,
            **options,
        )
        font = args.font
        fallback_font = args.fallback_font

    if not args.output:
        print(result_text(result), end="")
    metrics = save_result(
        result,
        text_path=args.output,
        lua_path=args.lua_output,
        preview_path=args.preview,
        metrics_path=args.metrics,
        debug_dir=args.debug_dir,
        mode=args.command,
        font=font,
        fallback_font=fallback_font,
    )
    print(json.dumps(metrics, sort_keys=True), file=sys.stderr)
    return 0


def main(argv=None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(_normalize_legacy_argv(raw_argv))

    if args.command in {"bead", "block", "glyph"}:
        try:
            return _run_renderer(args)
        except (OSError, ValueError) as error:
            parser.error(str(error))
    if args.command == "schema":
        print(json.dumps(mode_schema(), indent=2))
        return 0
    if args.command == "web":
        from .web.server import serve

        serve(args.host, args.port, args.open_browser)
        return 0
    parser.error(f"unsupported command: {args.command}")
    return 2
