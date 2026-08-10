import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from edgeglyph.engine import (
    BlockConfig,
    RenderConfig,
    block_glyphs,
    chamfer_distance,
    flood_background,
    parse_hex_color,
    render,
    render_blocks,
    render_line_sprite,
    thin,
    write_lua,
)


def find_test_font():
    candidates = (
        Path.home() / "Library/Fonts/ComicMono.ttf",
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
        Path("/System/Library/Fonts/Menlo.ttc"),
    )
    return next((path for path in candidates if path.exists()), None)


class GeometryTests(unittest.TestCase):
    def test_chamfer_distance_tracks_pixel_steps(self):
        mask = np.zeros((5, 5), dtype=bool)
        mask[2, 2] = True
        distance = chamfer_distance(mask)
        self.assertEqual(distance[2, 2], 0)
        self.assertAlmostEqual(distance[2, 3], 1)
        self.assertAlmostEqual(distance[3, 3], np.sqrt(2), places=5)

    def test_thinning_reduces_a_thick_stroke(self):
        image = np.zeros((9, 9), dtype=bool)
        image[2:7, 3:6] = True
        skeleton = thin(image)
        self.assertGreater(skeleton.sum(), 0)
        self.assertLess(skeleton.sum(), image.sum())

    def test_background_flood_does_not_remove_enclosed_white(self):
        rgb = np.ones((9, 9, 3), dtype=np.float32)
        rgb[2:7, 2:7] = 0.2
        rgb[4, 4] = 1.0
        background = flood_background(rgb)
        self.assertTrue(background[0, 0])
        self.assertFalse(background[4, 4])

    def test_line_sprites_match_terminal_geometry(self):
        horizontal = render_line_sprite("─", 11, 22)
        vertical = render_line_sprite("│", 11, 22)
        diagonal = render_line_sprite("╲", 11, 22)
        self.assertGreater(horizontal[:, 0].max(), 0.5)
        self.assertGreater(horizontal[:, -1].max(), 0.5)
        self.assertGreater(vertical[0, :].max(), 0.5)
        self.assertGreater(vertical[-1, :].max(), 0.5)
        self.assertGreater(diagonal[0, 0], 0.2)
        self.assertGreater(diagonal[-1, -1], 0.2)

    def test_block_glyphs_cover_half_cells(self):
        glyphs = block_glyphs(8, 12)
        self.assertEqual([glyph["character"] for glyph in glyphs], [" ", "▀", "▄", "█"])
        self.assertEqual(glyphs[1]["mask"].sum(), 48)
        self.assertEqual(glyphs[2]["mask"].sum(), 48)
        self.assertEqual(glyphs[3]["mask"].sum(), 96)
        np.testing.assert_allclose(
            parse_hex_color("#cba6f7"), [203 / 255, 166 / 255, 247 / 255]
        )


class RenderTests(unittest.TestCase):
    def test_block_render_uses_only_half_block_characters(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.png"
            image = Image.new("RGB", (96, 96), "white")
            draw = ImageDraw.Draw(image)
            draw.ellipse((10, 8, 86, 88), fill="#f2c98b", outline="#401818", width=5)
            draw.ellipse((30, 35, 40, 48), fill="#401818")
            draw.ellipse((56, 35, 66, 48), fill="#401818")
            image.save(source)

            config = BlockConfig(cols=16, rows=8, oversample=4)
            result = render_blocks(source, config)
            self.assertEqual(len(result.lines), 8)
            self.assertTrue(all(len(line) == 16 for line in result.lines))
            self.assertLessEqual(set("".join(result.lines)), set(" ▀▄█"))
            self.assertGreater(result.metrics["foreground_ratio"], 0)
            self.assertEqual(len(result.palette), 1)

    @unittest.skipUnless(find_test_font(), "no suitable monospace font found")
    def test_small_synthetic_render(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.png"
            image = Image.new("RGB", (96, 96), "white")
            draw = ImageDraw.Draw(image)
            draw.ellipse((14, 10, 82, 78), outline="#222222", width=4)
            draw.ellipse((30, 35, 40, 48), fill="#dd6677")
            draw.ellipse((56, 35, 66, 48), fill="#dd6677")
            draw.arc((35, 42, 61, 66), 10, 170, fill="#222222", width=3)
            image.save(source)

            result = render(
                source,
                find_test_font(),
                config=RenderConfig(cols=16, rows=8, colors=6, top_k=5),
            )
            self.assertEqual(len(result.lines), 8)
            self.assertTrue(all(len(line) == 16 for line in result.lines))
            self.assertGreater(result.metrics["f1"], 0)
            self.assertFalse(np.isnan(result.metrics["chamfer"]))

    @unittest.skipUnless(find_test_font(), "no suitable monospace font found")
    def test_blank_image_and_lua_export(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "blank.png"
            output = Path(directory) / "blank.lua"
            Image.new("RGBA", (64, 64), (255, 255, 255, 0)).save(source)

            config = RenderConfig(cols=8, rows=4, colors=4, top_k=4)
            result = render(source, find_test_font(), config=config)
            self.assertEqual(result.lines, [" " * 8] * 4)
            self.assertEqual(result.metrics["f1"], 1.0)

            write_lua(
                output,
                result.glyphs,
                result.selected,
                result.palette,
                result.color_indices,
                config.cols,
                config.rows,
            )
            exported = output.read_text(encoding="utf-8")
            self.assertIn("width = 8", exported)
            self.assertIn("height = 4", exported)


if __name__ == "__main__":
    unittest.main()
