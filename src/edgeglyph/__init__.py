"""Terminal art, structure-aware glyphs, and fuse-bead pattern generation."""

from .engine import (
    BeadConfig,
    BlockConfig,
    RenderConfig,
    RenderResult,
    render,
    render_beads,
    render_blocks,
)
from .modes import bead, block, glyph

__all__ = [
    "BeadConfig",
    "BlockConfig",
    "RenderConfig",
    "RenderResult",
    "bead",
    "block",
    "glyph",
    "render",
    "render_beads",
    "render_blocks",
]
__version__ = "0.5.0"
