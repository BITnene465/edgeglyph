"""Terminal block art and structure-aware glyph art generation."""

from .engine import BlockConfig, RenderConfig, RenderResult, render, render_blocks
from .modes import block, glyph

__all__ = [
    "BlockConfig",
    "RenderConfig",
    "RenderResult",
    "block",
    "glyph",
    "render",
    "render_blocks",
]
__version__ = "0.4.0"
