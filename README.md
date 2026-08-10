# EdgeGlyph

EdgeGlyph converts an image into structure-aware glyph art. It targets line structure first, then samples
color, instead of mapping each cell from brightness to a character independently.

![Synthetic portrait rendered by EdgeGlyph](docs/example-render.png)

The renderer is designed for terminal dashboards, README artwork, and other low-resolution text surfaces.
It uses the actual terminal fonts during matching, so the optimized glyph shapes are the shapes users see.

## Why

Most image-to-ASCII tools are tone renderers. They can reproduce photographs at high text resolutions,
but they tend to become noisy when a detailed subject must fit inside a small dashboard header. EdgeGlyph
uses a structure-first pipeline:

1. Preserve aspect ratio and isolate connected background.
2. Extract multi-channel Scharr edges and apply non-maximum suppression.
3. Thin glyphs rendered from the requested primary and fallback fonts.
4. Match source and glyph structures with bidirectional, orientation-aware Chamfer distance.
5. Optimize neighboring cells for continuity and regularize excessive glyph repetition.
6. Quantize colors only after structural glyph selection.

The approach is inspired by structure-based ASCII art research, while remaining lightweight: the runtime
depends only on NumPy and Pillow.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Usage

```bash
edgeglyph input.png \
  --font /path/to/PrimaryMono.ttf \
  --fallback-font /path/to/NerdFont.ttf \
  --cols 56 --rows 28 \
  --output output.txt \
  --preview output.png
```

For an NvChad/NvDash header:

```bash
edgeglyph input.png \
  --font /path/to/PrimaryMono.ttf \
  --fallback-font /path/to/NerdFont.ttf \
  --lua-output dashboard_art.lua \
  --preview dashboard_art.png
```

Useful modes:

- `--fill-mode none`: structure-only output; best for compact portraits and dashboard headers.
- `--fill-mode salient`: adds sparse tone glyphs to dark, saturated regions.
- `--fill-mode tone`: combines structural edges with general halftone filling.
- `--continuity`: strength of adjacent-cell line continuity.
- `--diversity`: discourages a few similar glyphs from dominating the image.
- `--line-renderer sprite`: models geometric box-drawing sprites used by terminals such as Ghostty.
- `--line-renderer font`: rasterizes box-drawing characters from the requested fallback font instead.
- `--debug-dir`: writes source edges, subject mask, importance map, and reconstructed glyph edges.

## Metrics

EdgeGlyph reports bidirectional edge precision, recall, F1, and Chamfer distance. These metrics do not
replace visual inspection, but they make regressions in structural fidelity measurable.

On the portrait used during initial development, with the actual terminal font and a `56x28` grid:

| Renderer | Edge F1 | Chamfer distance |
| --- | ---: | ---: |
| Tone-oriented terminal renderer | 0.252 | 7.99 |
| EdgeGlyph structure preset | 0.707 | 1.77 |

Lower Chamfer distance is better. The development portrait is not included in this repository.

## Development

```bash
python -m unittest discover -s tests -v
python -m compileall -q src
```

## References

- [X. Xu, L. Zhang, and T.-T. Wong, "Structure-based ASCII Art," ACM Transactions on Graphics, 2010](https://doi.org/10.1145/1778765.1778789).
- [M. Chung and T. Kwon, "Fast Text Placement Scheme for ASCII Art Synthesis," IEEE Access, 2022](https://doi.org/10.1109/ACCESS.2022.3167567).

## License

MIT
