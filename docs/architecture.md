# Architecture

EdgeGlyph exposes one rendering contract through three interfaces: Python, CLI, and the local web
workbench. Renderer settings live in `edgeglyph.schema`; both CLI argument construction and web controls
read that schema instead of maintaining separate defaults.

```text
src/edgeglyph/
├── modes/
│   ├── block.py       Public half-block mode API
│   └── glyph.py       Public font-matched mode API
├── schema.py          Parameter names, defaults, ranges, and choices
├── outputs.py         Text, Lua, PNG, debug, palette, and metrics output
├── cli.py             block / glyph / web / schema commands
├── web/
│   ├── server.py      Loopback-only standard-library HTTP server
│   └── static/        Build-free HTML, CSS, and JavaScript workbench
└── engine.py          Numerical rendering implementation and compatibility API
```

## Mode boundary

`block` is region-first. It builds a filled subject, carves local detail, quantizes colors in OKLab, and
encodes two vertical pixels per terminal cell with `▀▄█`.

`glyph` is structure-first. It extracts and thins edges, rasterizes the selected terminal font, scores
candidate glyph geometry, and optimizes continuity across the complete grid.

Mode-specific options do not cross this boundary. Font paths only belong to `glyph`; crop, zoom, and
silhouette controls only belong to `block`.

## Compatibility

`engine.py` remains import-compatible with releases before 0.4. New integrations should import
`edgeglyph.modes.block` or `edgeglyph.modes.glyph`. The old flat CLI form is translated internally, but all
new examples use explicit mode subcommands.

## Web security

The workbench uses `ThreadingHTTPServer` and has no runtime web-framework dependency. It only accepts
`127.0.0.1`, `localhost`, or `::1`, does not persist uploaded images, and removes each render's temporary
directory after the response is built. It is a local renderer, not a deployment-ready multi-user service.
