# Repository Guidance

- Keep block rendering region-first and glyph rendering structure-first; tone-only shortcuts remain optional.
- Keep bead rendering cell-first: one square-grid position equals one physical bead, independent of preview styling.
- Block mode must stay terminal-native and use only spaces plus Unicode half/full block elements.
- Test glyph mode against the actual requested font files because glyph geometry is part of the algorithm.
- Do not commit personal input images or generated artifacts derived from them unless the user explicitly
  approves them as documentation examples.
- Preserve or improve the structural benchmark when changing matching or optimization weights.
- Keep the core dependency set small. NumPy and Pillow are sufficient for the current implementation.
