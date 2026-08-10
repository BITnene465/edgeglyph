"""Terminal block art and structure-aware glyph art generation."""

from .engine import BlockConfig, RenderConfig, RenderResult, render, render_blocks

__all__ = ["BlockConfig", "RenderConfig", "RenderResult", "render", "render_blocks"]
__version__ = "0.3.0"
