"""Structure-aware, font-matched glyph rendering mode."""

from pathlib import Path

from ..engine import RenderConfig, RenderResult, render as render_glyphs
from ..schema import coerce_options

NAME = "glyph"
Config = RenderConfig


def render(
    source: str | Path,
    font: str | Path,
    fallback_font: str | Path | None = None,
    config: RenderConfig | None = None,
    **options,
) -> RenderResult:
    if config is not None and options:
        raise ValueError("pass either a RenderConfig or keyword options, not both")
    resolved = config or RenderConfig(**coerce_options(NAME, options))
    return render_glyphs(source, font, fallback_font, resolved)


__all__ = ["Config", "NAME", "RenderConfig", "RenderResult", "render"]
