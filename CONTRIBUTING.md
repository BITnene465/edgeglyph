# Contributing

Contributions are welcome when they preserve EdgeGlyph's three renderer boundaries:

- Block mode is region-first and terminal-native. Its output remains spaces plus Unicode half/full blocks.
- Glyph mode is structure-first and evaluates geometry against the requested terminal font.
- Bead mode is cell-first. One square-grid position represents one physical bead, and preview styling must
  not change the underlying pattern or palette counts.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Checks

```bash
python -m unittest discover -s tests -v
python -m compileall -q src
python -m build
```

Changes to matching, optimization, palette grading, or threshold defaults should include a focused test.
Renderer changes should also include before/after previews using a synthetic or redistributable source image.
Do not commit personal photographs or generated artifacts derived from private inputs.

Public arguments belong in `edgeglyph.schema`. Adding a parameter directly to only the CLI or workbench
creates divergent interfaces and will not be accepted.
