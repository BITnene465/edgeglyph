# Repository Guidance

- Keep the renderer structure-first; tone-only shortcuts must remain optional modes.
- Test against the actual requested font files because glyph geometry is part of the algorithm.
- Do not commit personal input images or generated artifacts derived from them.
- Preserve or improve the structural benchmark when changing matching or optimization weights.
- Keep the core dependency set small. NumPy and Pillow are sufficient for the current implementation.
