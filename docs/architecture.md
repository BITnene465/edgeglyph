# Architecture

EdgeGlyph exposes one rendering contract through three interfaces: Python, CLI, and the local web
workbench. Renderer settings live in `edgeglyph.schema`; both CLI argument construction and web controls
read that schema instead of maintaining separate defaults.

```text
src/edgeglyph/
├── modes/
│   ├── bead.py        Public square-grid fuse-bead mode API
│   ├── block.py       Public half-block mode API
│   └── glyph.py       Public font-matched mode API
├── schema.py          Parameter names, defaults, ranges, and choices
├── glyphsets.py       Terminal-safe presets and custom glyph resolution
├── bead_chart.py      Printable coordinates, color codes, and palette legend
├── outputs.py         Text, Lua, PNG, debug, palette, and metrics output
├── cli.py             bead / block / glyph / web / schema commands
├── web/
│   ├── server.py      Loopback-only standard-library HTTP server
│   └── static/        Build-free HTML, CSS, and JavaScript workbench
└── engine.py          Numerical rendering implementation and compatibility API
```

## Mode boundary

`block` is region-first. It builds a filled subject, carves local detail, quantizes colors in OKLab, and
encodes two vertical pixels per terminal cell with `▀▄█`.

`glyph` is font-first and profile-driven. `outline` retains the structure-first edge, skeleton, and Chamfer
pipeline. `hybrid` combines those signals with regional tone, foreground/background color fitting, local
texture, and multi-scale density consistency. `tone` reduces structural influence for dense character art.
All profiles rasterize the actual requested font and derive glyph coverage, spatial ink, gradient, centroid,
texture, and boundary descriptors before matching.

`color` output fits source colors and may use foreground/background pairs. `mono` removes color from glyph
selection, emits one configurable foreground color, and never emits cell backgrounds. Plain text remains
free of color metadata in both cases.

Structure and fill character sets remain independent. Presets are resolved in `glyphsets.py`; literal CLI/Web
overrides and UTF-8 character files pass through terminal-width and font-coverage validation. The optimizer
keeps per-cell top-k candidates, applies boundary continuity and diversity terms, and evaluates density over
three neighborhood scales so a locally plausible glyph cannot silently damage the global silhouette.

`bead` is cell-first. It samples one physical color per square-grid position, quantizes those colors in
OKLab, removes empty background cells, and draws a dedicated pegboard preview with circular bead geometry.
The separate chart exporter keeps the same palette indices but renders square cells, stable `C01` codes,
four-edge coordinates, 10-cell guide lines, and an exact count legend for manual assembly.

Mode-specific options do not cross this boundary. Font paths only belong to `glyph`; terminal silhouette
carving only belongs to `block`; board, finish, and bead-size controls only belong to `bead`.

## Glyph references

The symbol registry, separate structure/fill sets, font-derived coverage, and foreground/background fitting
take engineering cues from [Chafa](https://github.com/hpjansson/chafa). The `outline` profile follows the
shape-matching direction described in [Structure-based ASCII Art](https://ttwong12.github.io/papers/asciiart/asciiart.pdf),
while keeping its raster-vectorization limitations isolated from the default hybrid profile. Tone ramps and
dithering remain explicit profile choices rather than universal assumptions.

## Compatibility

`engine.py` remains import-compatible with releases before 0.4. New integrations should import
`edgeglyph.modes.bead`, `edgeglyph.modes.block`, or `edgeglyph.modes.glyph`. The old flat CLI form is
translated internally, but all new examples use explicit mode subcommands.

## Web security

The workbench uses `ThreadingHTTPServer` and has no runtime web-framework dependency. It only accepts
`127.0.0.1`, `localhost`, or `::1`, does not persist uploaded images, and removes each render's temporary
directory after the response is built. It is a local renderer, not a deployment-ready multi-user service.
