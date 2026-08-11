"""Terminal-safe glyph presets and user-defined character set resolution."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass


UNICODE_LINES = "─│╱╲╭╮╰╯┌┐└┘├┤┬┴┼"
ASCII_PRINTABLE = (
    " .,:;~-=+*#%@$&!?/\\|_()[]{}<>"
    "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
)
ASCII_STRUCTURE = " .,:;-_=+*/\\|()[]{}<>!?LJTYXVC"
ASCII_TONE = " .,:;irsXA253hMHGS#9B&@"
UNICODE_TONE = " ░▒▓█▄▀▌▐"


@dataclass(frozen=True)
class GlyphSet:
    """Resolved characters plus their intended structure and fill roles."""

    characters: str
    structure: frozenset[str]
    fill: frozenset[str]
    excluded: tuple[str, ...] = ()


PRESETS = {
    "ascii": (ASCII_PRINTABLE, ASCII_STRUCTURE, ASCII_TONE),
    "line": (
        " " + ASCII_STRUCTURE + UNICODE_LINES,
        " " + ASCII_STRUCTURE + UNICODE_LINES,
        " .,:;-_=+",
    ),
    "portrait": (
        ASCII_PRINTABLE + UNICODE_LINES,
        ASCII_STRUCTURE + UNICODE_LINES,
        ASCII_TONE,
    ),
    "unicode": (
        ASCII_PRINTABLE + UNICODE_LINES + UNICODE_TONE,
        ASCII_STRUCTURE + UNICODE_LINES + "▄▀▌▐",
        ASCII_TONE + UNICODE_TONE,
    ),
}


def _unique(characters: str) -> str:
    return "".join(dict.fromkeys(characters))


def _is_terminal_safe(character: str) -> bool:
    if character == " ":
        return True
    if not character or character in "\n\r\t":
        return False
    category = unicodedata.category(character)
    if category.startswith("C") or unicodedata.combining(character):
        return False
    return unicodedata.east_asian_width(character) not in {"W", "F"}


def _sanitize(characters: str) -> tuple[str, tuple[str, ...]]:
    accepted = []
    excluded = []
    for character in _unique(characters):
        if _is_terminal_safe(character):
            accepted.append(character)
        else:
            excluded.append(character)
    return "".join(accepted), tuple(excluded)


def resolve_glyph_set(
    preset: str = "portrait",
    symbols: str = "",
    fill_symbols: str = "",
) -> GlyphSet:
    """Resolve a preset with optional literal structure and fill overrides."""

    try:
        preset_characters, preset_structure, preset_fill = PRESETS[preset]
    except KeyError as error:
        raise ValueError(f"unsupported character preset: {preset}") from error

    structure_source = symbols if symbols else preset_structure
    fill_source = fill_symbols if fill_symbols else preset_fill
    structure, excluded_structure = _sanitize(structure_source)
    fill, excluded_fill = _sanitize(fill_source)
    if not structure.strip() and not fill.strip():
        raise ValueError("the resolved character set contains no visible glyphs")

    if symbols or fill_symbols:
        characters_source = " " + structure + fill
    else:
        characters_source = preset_characters
    characters, excluded_characters = _sanitize(characters_source)
    characters = _unique(" " + characters)
    if len(characters) > 512:
        raise ValueError("character sets may contain at most 512 unique glyphs")

    excluded = tuple(
        dict.fromkeys(excluded_structure + excluded_fill + excluded_characters)
    )
    return GlyphSet(
        characters=characters,
        structure=frozenset(" " + structure),
        fill=frozenset(" " + fill),
        excluded=excluded,
    )


__all__ = [
    "ASCII_PRINTABLE",
    "ASCII_STRUCTURE",
    "ASCII_TONE",
    "GlyphSet",
    "PRESETS",
    "UNICODE_LINES",
    "UNICODE_TONE",
    "resolve_glyph_set",
]
