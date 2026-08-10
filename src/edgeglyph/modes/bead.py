"""Square-grid fuse-bead pattern and physical preview mode."""

from pathlib import Path

from ..engine import BeadConfig, RenderResult, render_beads
from ..schema import coerce_options

NAME = "bead"
Config = BeadConfig


def render(
    source: str | Path,
    config: BeadConfig | None = None,
    **options,
) -> RenderResult:
    if config is not None and options:
        raise ValueError("pass either a BeadConfig or keyword options, not both")
    resolved = config or BeadConfig(**coerce_options(NAME, options))
    return render_beads(source, resolved)


__all__ = ["Config", "NAME", "BeadConfig", "RenderResult", "render"]
