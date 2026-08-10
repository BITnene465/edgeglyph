"""Single source of truth for renderer modes and their public parameters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Parameter:
    key: str
    flag: str
    label: str
    kind: str
    default: Any
    help: str
    minimum: float | int | None = None
    maximum: float | int | None = None
    step: float | int | None = None
    choices: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "flag": self.flag,
            "label": self.label,
            "kind": self.kind,
            "default": self.default,
            "help": self.help,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "step": self.step,
            "choices": list(self.choices),
        }


COMMON_PARAMETERS = (
    Parameter(
        "cols",
        "--cols",
        "Columns",
        "integer",
        56,
        "Terminal cell columns.",
        8,
        120,
        1,
    ),
    Parameter(
        "rows",
        "--rows",
        "Rows",
        "integer",
        28,
        "Terminal cell rows.",
        4,
        60,
        1,
    ),
)

BLOCK_PARAMETERS = COMMON_PARAMETERS + (
    Parameter(
        "colors",
        "--colors",
        "Palette size",
        "integer",
        4,
        "Maximum adaptive palette size.",
        1,
        8,
        1,
    ),
    Parameter(
        "foreground",
        "--foreground",
        "Single color",
        "color",
        "#cba6f7",
        "Fixed foreground when palette size is one.",
    ),
    Parameter(
        "subject_threshold",
        "--subject-threshold",
        "Subject threshold",
        "number",
        0.34,
        "Minimum pooled coverage retained as subject.",
        0.0,
        1.0,
        0.01,
    ),
    Parameter(
        "ink_threshold",
        "--ink-threshold",
        "Ink threshold",
        "number",
        0.46,
        "Strength required to carve interior detail.",
        0.0,
        1.0,
        0.01,
    ),
    Parameter(
        "detail",
        "--detail",
        "Detail gain",
        "number",
        1.0,
        "Local contrast contribution to carved detail.",
        0.2,
        2.5,
        0.05,
    ),
    Parameter(
        "oversample",
        "--oversample",
        "Oversampling",
        "integer",
        6,
        "Pixels sampled along each terminal-pixel axis.",
        2,
        12,
        1,
    ),
    Parameter(
        "fit",
        "--fit",
        "Frame fit",
        "choice",
        "cover",
        "Crop to fill or contain the complete source.",
        choices=("cover", "contain"),
    ),
    Parameter(
        "focus_y",
        "--focus-y",
        "Vertical focus",
        "number",
        0.36,
        "Vertical crop anchor from top to bottom.",
        0.0,
        1.0,
        0.01,
    ),
    Parameter(
        "zoom",
        "--zoom",
        "Subject scale",
        "number",
        1.0,
        "Scale applied inside the terminal frame.",
        0.4,
        2.0,
        0.02,
    ),
)

GLYPH_PARAMETERS = COMMON_PARAMETERS + (
    Parameter(
        "colors",
        "--colors",
        "Palette size",
        "integer",
        16,
        "Maximum adaptive palette size.",
        1,
        32,
        1,
    ),
    Parameter(
        "top_k",
        "--top-k",
        "Candidate glyphs",
        "integer",
        8,
        "Local glyph candidates retained before grid optimization.",
        2,
        20,
        1,
    ),
    Parameter(
        "minimum_luminance",
        "--min-luminance",
        "Minimum luminance",
        "number",
        0.72,
        "Minimum graded palette luminance.",
        0.2,
        1.0,
        0.01,
    ),
    Parameter(
        "fill_mode",
        "--fill-mode",
        "Fill strategy",
        "choice",
        "none",
        "Structure-only, salient fill, or full tone fill.",
        choices=("none", "salient", "tone"),
    ),
    Parameter(
        "continuity",
        "--continuity",
        "Line continuity",
        "number",
        0.4,
        "Adjacent-cell stroke continuity weight.",
        0.0,
        2.0,
        0.05,
    ),
    Parameter(
        "diversity",
        "--diversity",
        "Glyph diversity",
        "number",
        1.5,
        "Penalty for repeated similar glyphs.",
        0.0,
        4.0,
        0.1,
    ),
    Parameter(
        "line_renderer",
        "--line-renderer",
        "Line renderer",
        "choice",
        "sprite",
        "Terminal sprites or fallback-font box drawing.",
        choices=("sprite", "font"),
    ),
)

MODE_PARAMETERS = {
    "block": BLOCK_PARAMETERS,
    "glyph": GLYPH_PARAMETERS,
}


def mode_schema() -> dict[str, list[dict[str, Any]]]:
    return {
        mode: [parameter.to_dict() for parameter in parameters]
        for mode, parameters in MODE_PARAMETERS.items()
    }


def defaults_for(mode: str) -> dict[str, Any]:
    try:
        parameters = MODE_PARAMETERS[mode]
    except KeyError as error:
        raise ValueError(f"unsupported mode: {mode}") from error
    return {parameter.key: parameter.default for parameter in parameters}


def coerce_options(mode: str, values: dict[str, Any] | None = None) -> dict[str, Any]:
    """Validate untrusted CLI/UI values and return config constructor arguments."""

    try:
        parameters = MODE_PARAMETERS[mode]
    except KeyError as error:
        raise ValueError(f"unsupported mode: {mode}") from error
    incoming = values or {}
    unknown = set(incoming) - {parameter.key for parameter in parameters}
    if unknown:
        raise ValueError(f"unknown {mode} options: {', '.join(sorted(unknown))}")

    result = {}
    for parameter in parameters:
        raw = incoming.get(parameter.key, parameter.default)
        try:
            if parameter.kind == "integer":
                value = int(raw)
            elif parameter.kind == "number":
                value = float(raw)
            else:
                value = str(raw)
        except (TypeError, ValueError) as error:
            raise ValueError(f"{parameter.label} has an invalid value") from error

        if parameter.choices and value not in parameter.choices:
            choices = ", ".join(parameter.choices)
            raise ValueError(f"{parameter.label} must be one of: {choices}")
        if parameter.minimum is not None and value < parameter.minimum:
            raise ValueError(f"{parameter.label} must be at least {parameter.minimum}")
        if parameter.maximum is not None and value > parameter.maximum:
            raise ValueError(f"{parameter.label} must be at most {parameter.maximum}")
        result[parameter.key] = value
    return result
