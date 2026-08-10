"""Terminal-native half-block rendering mode."""

from pathlib import Path

from ..engine import BlockConfig, RenderResult, render_blocks
from ..schema import coerce_options

NAME = "block"
Config = BlockConfig


def render(
    source: str | Path,
    config: BlockConfig | None = None,
    **options,
) -> RenderResult:
    if config is not None and options:
        raise ValueError("pass either a BlockConfig or keyword options, not both")
    resolved = config or BlockConfig(**coerce_options(NAME, options))
    return render_blocks(source, resolved)


__all__ = ["Config", "NAME", "BlockConfig", "RenderResult", "render"]
