import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from edgeglyph.engine import (
    BeadConfig,
    BlockConfig,
    RenderConfig,
    bead_preview_size,
    block_glyphs,
    chamfer_distance,
    flood_background,
    parse_hex_color,
    render,
    render_beads,
    render_blocks,
    render_line_sprite,
    thin,
    write_lua,
)
from edgeglyph.outputs import save_result


def find_test_font():
    candidates = (
        Path.home() / "Library/Fonts/ComicMono.ttf",
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
        Path("/System/Library/Fonts/Menlo.ttc"),
    )
    return next((path for path in candidates if path.exists()), None)


class GeometryTests(unittest.TestCase):
    def test_bead_preview_size_bounds_large_grids(self):
        config = BeadConfig(cols=2048, rows=2048, bead_size=24)
        self.assertEqual(bead_preview_size(config), 2)

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
    def test_bead_render_builds_square_pattern_and_transparent_preview(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.png"
            preview = Path(directory) / "preview.png"
            image = Image.new("RGBA", (64, 64), (255, 255, 255, 0))
            draw = ImageDraw.Draw(image)
            draw.ellipse((6, 5, 58, 59), fill="#f0cf68")
            draw.ellipse((19, 22, 29, 35), fill="#cf5962")
            draw.ellipse((36, 22, 46, 35), fill="#cf5962")
            image.save(source)

            config = BeadConfig(
                cols=16,
                rows=16,
                colors=4,
                oversample=3,
                bead_size=8,
                board_style="transparent",
            )
            result = render_beads(source, config)
            self.assertEqual(len(result.lines), 16)
            self.assertTrue(all(len(line) == 16 for line in result.lines))
            self.assertLessEqual(set("".join(result.lines)), {" ", "●"})
            self.assertGreater(result.metrics["bead_count"], 0)
            self.assertLessEqual(len(result.palette), 4)

            metrics = save_result(result, preview_path=preview, mode="bead")
            self.assertEqual(metrics["mode"], "bead")
            self.assertEqual(len(metrics["palette"]), len(result.palette))
            self.assertEqual(sum(metrics["palette_counts"]), metrics["bead_count"])
            with Image.open(preview) as rendered:
                self.assertEqual(rendered.mode, "RGBA")
                self.assertEqual(rendered.size, (192, 192))
                self.assertEqual(rendered.getpixel((0, 0))[3], 0)
                self.assertGreater(rendered.getchannel("A").getextrema()[1], 0)

    def test_block_render_uses_only_half_block_characters(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.png"
            image = Image.new("RGB", (96, 96), "white")
            draw = ImageDraw.Draw(image)
            draw.ellipse((10, 8, 86, 88), fill="#f2c98b", outline="#401818", width=5)
            draw.ellipse((30, 35, 40, 48), fill="#401818")
            draw.ellipse((56, 35, 66, 48), fill="#401818")
            image.save(source)

            config = BlockConfig(cols=16, rows=8, colors=1, oversample=4)
            result = render_blocks(source, config)
            self.assertEqual(len(result.lines), 8)
            self.assertTrue(all(len(line) == 16 for line in result.lines))
            self.assertLessEqual(set("".join(result.lines)), set(" ▀▄█"))
            self.assertGreater(result.metrics["foreground_ratio"], 0)
            self.assertEqual(len(result.palette), 1)

    def test_block_zoom_reduces_subject_coverage(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.png"
            image = Image.new("RGB", (96, 96), "white")
            ImageDraw.Draw(image).ellipse((4, 4, 92, 92), fill="#e0a060")
            image.save(source)

            full = render_blocks(
                source,
                BlockConfig(cols=24, rows=8, colors=1, oversample=4, zoom=1.0),
            )
            inset = render_blocks(
                source,
                BlockConfig(cols=24, rows=8, colors=1, oversample=4, zoom=0.75),
            )
            self.assertLess(
                inset.metrics["foreground_ratio"], full.metrics["foreground_ratio"]
            )

    def test_block_render_preserves_half_cell_color_boundaries(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.png"
            output = Path(directory) / "output.lua"
            image = Image.new("RGB", (96, 96), "#efc66f")
            ImageDraw.Draw(image).rectangle((0, 36, 95, 95), fill="#d76f82")
            image.save(source)

            config = BlockConfig(cols=8, rows=4, colors=2, oversample=4, fit="contain")
            result = render_blocks(source, config)
            self.assertEqual(len(result.palette), 2)
            self.assertTrue(
                any(
                    index is not None
                    for row in result.background_indices
                    for index in row
                )
            )

            write_lua(
                output,
                result.glyphs,
                result.selected,
                result.palette,
                result.color_indices,
                config.cols,
                config.rows,
                result.background_indices,
            )
            exported = output.read_text(encoding="utf-8")
            self.assertRegex(exported, r'\{ "[▀▄█ ]+", [12], [12] \}')

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
