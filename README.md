<p align="center"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/assets/edgeglyph-logo-dark.svg"><img src="docs/assets/edgeglyph-logo.svg" width="640" alt="EdgeGlyph terminal art renderer"></picture></p>

<p align="center"><strong>English</strong> · <a href="README.zh-CN.md">简体中文</a></p>

<p align="center">
  <a href="https://github.com/BITnene465/edgeglyph/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/BITnene465/edgeglyph/actions/workflows/ci.yml/badge.svg"></a>
  <img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white">
  <a href="LICENSE"><img alt="MIT License" src="https://img.shields.io/badge/License-MIT-e3cf62"></a>
</p>

EdgeGlyph converts images into terminal blocks, font-matched glyph art, and fuse-bead patterns. The CLI,
Python API, NvDash exporter, and local workbench use the same parameter schema.

<p align="center"><img src="docs/assets/showcase.png" width="100%" alt="EdgeGlyph rendering modes using one source image"></p>

| Mode | Representation | Main output |
| --- | --- | --- |
| `block` | spaces and Unicode `▀▄█` | compact terminal color art |
| `glyph` | rasterized glyphs from a selected font | color or monochrome character art |
| `bead` | one square-grid cell per physical bead | pattern, palette counts, pegboard PNG |

## Install

```bash
git clone https://github.com/BITnene465/edgeglyph.git
cd edgeglyph
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Python 3.10 or newer is required. Runtime dependencies are NumPy and Pillow.

Start the loopback-only workbench:

```bash
edgeglyph web
```

Open `http://127.0.0.1:8765` if the browser does not open automatically.

## Glyph mode

<p align="center">
  <img src="docs/example-glyph-render.png" width="47%" alt="Color glyph rendering">
  <img src="docs/example-glyph-mono-render.png" width="47%" alt="Monochrome glyph rendering">
</p>
<p align="center"><sub>Color output · monochrome output</sub></p>

Color output:

```bash
edgeglyph glyph input.png \
  --font /path/to/MapleMono-NF-Regular.ttf \
  --profile hybrid \
  --color-mode color \
  --cols 56 --rows 28 \
  --output output.txt \
  --preview output.png \
  --lua-output output.lua
```

Monochrome output for plain TTYs and terminals without color chunk support:

```bash
edgeglyph glyph input.png \
  --font /path/to/MapleMono-NF-Regular.ttf \
  --profile hybrid \
  --color-mode mono \
  --mono-color '#e8e8e8' \
  --output output.txt \
  --preview output-mono.png
```

`mono` uses one foreground color and no cell backgrounds. TXT output contains only UTF-8 characters and can
use the terminal's current foreground color.

### Glyph controls

| Argument | Values | Default |
| --- | --- | ---: |
| `--profile` | `outline`, `hybrid`, `tone` | `hybrid` |
| `--color-mode` | `color`, `mono` | `color` |
| `--mono-color` | `#RRGGBB` | `#e8e8e8` |
| `--character-preset` | `portrait`, `ascii`, `line`, `unicode` | `portrait` |
| `--fill-mode` | `auto`, `none`, `salient`, `tone` | `auto` |
| `--symbols` / `--fill-symbols` | literal custom characters | preset |
| `--symbols-file` / `--fill-symbols-file` | UTF-8 character files | - |
| `--top-k` | candidates retained per cell | `8` |

Glyph coverage, density, regional ink, direction, and texture are measured from the requested font. Invalid
terminal-width and missing-font glyphs are excluded. Maple Mono NF or another Nerd Font is recommended for
the Unicode preset.

Feature weights are available through `--shape-weight`, `--tone-weight`, `--color-weight`,
`--texture-weight`, and `--global-weight`. Run `edgeglyph glyph --help` for their ranges.

## Block mode

```bash
edgeglyph block input.png \
  --cols 72 --rows 24 \
  --colors 4 \
  --fit cover --focus-y 0.36 --zoom 0.9 \
  --output output.txt \
  --preview output.png
```

Block output uses only spaces and `▀▄█`. Each terminal cell stores independent upper and lower colors.

## Bead mode

```bash
edgeglyph bead input.png \
  --cols 48 --rows 48 \
  --colors 12 \
  --background auto \
  --board-style light --finish glossy \
  --preview bead-pattern.png \
  --metrics bead-counts.json
```

<p align="center">
  <img src="docs/assets/atri1.png" width="47%" alt="Wide source artwork">
  <img src="docs/atri1-bead-render.png" width="47%" alt="Fuse-bead pattern preview">
</p>

Bead grids support up to `2048 × 2048` cells and `128` colors. Large previews reduce the displayed bead size
without changing the logical grid.

## Outputs

| Argument | File |
| --- | --- |
| `-o`, `--output` | plain UTF-8 art |
| `--preview` | rendered PNG |
| `--lua-output` | NvDash palette and text chunks |
| `--metrics` | JSON metrics and bead counts |
| `--debug-dir` | intermediate masks and reconstructions |

Without `--output`, text is written to stdout. Metrics are written to stderr.

Print the full validated interface:

```bash
edgeglyph block --help
edgeglyph glyph --help
edgeglyph bead --help
edgeglyph schema
```

## Python API

```python
from edgeglyph.modes import glyph

result = glyph.render(
    "input.png",
    "/path/to/MapleMono-NF-Regular.ttf",
    profile="hybrid",
    color_mode="mono",
    cols=56,
    rows=28,
)

print("\n".join(result.lines))
```

Public mode modules are `edgeglyph.modes.block`, `edgeglyph.modes.glyph`, and `edgeglyph.modes.bead`.

## Development

```bash
PYTHONPATH=src pytest -q
python -m compileall -q src
python -m build
```

Architecture and renderer boundaries are documented in [docs/architecture.md](docs/architecture.md).
Contribution rules are in [CONTRIBUTING.md](CONTRIBUTING.md).

## References

- [Structure-based ASCII Art, ACM Transactions on Graphics, 2010](https://doi.org/10.1145/1778765.1778789)
- [Chafa](https://github.com/hpjansson/chafa)

## License

[MIT](LICENSE)
