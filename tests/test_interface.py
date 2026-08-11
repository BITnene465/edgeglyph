import base64
import io
import unittest
from importlib import resources

from PIL import Image, ImageDraw

from edgeglyph.cli import _normalize_legacy_argv, build_parser
from edgeglyph.schema import coerce_options, defaults_for, mode_schema
from edgeglyph.web.server import application_schema, render_payload


def encoded_test_image():
    image = Image.new("RGB", (64, 64), "white")
    draw = ImageDraw.Draw(image)
    draw.ellipse((8, 6, 56, 58), fill="#e3cf62", outline="#3b2730", width=4)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode()


class SchemaTests(unittest.TestCase):
    def test_modes_have_independent_defaults(self):
        schema = mode_schema()
        self.assertEqual(set(schema), {"bead", "block", "glyph"})
        self.assertEqual(defaults_for("bead")["cols"], 48)
        self.assertEqual(defaults_for("bead")["colors"], 12)
        self.assertEqual(defaults_for("bead")["chart_title"], "")
        self.assertEqual(defaults_for("bead")["chart_cell_size"], 18)
        self.assertEqual(defaults_for("block")["colors"], 4)
        self.assertEqual(defaults_for("glyph")["colors"], 16)
        self.assertEqual(defaults_for("glyph")["fill_mode"], "auto")
        self.assertEqual(defaults_for("glyph")["color_mode"], "color")

    def test_options_are_coerced_and_bounded(self):
        options = coerce_options("block", {"cols": "72", "zoom": "0.9"})
        self.assertEqual(options["cols"], 72)
        self.assertEqual(options["zoom"], 0.9)
        with self.assertRaisesRegex(ValueError, "Columns must be at most"):
            coerce_options("block", {"cols": 500})
        with self.assertRaisesRegex(ValueError, "unknown block options"):
            coerce_options("block", {"font": "irrelevant.ttf"})

    def test_glyph_options_accept_profiles_weights_and_literal_characters(self):
        options = coerce_options(
            "glyph",
            {
                "profile": "hybrid",
                "symbols": "/\\|_",
                "fill_symbols": ".:#@",
                "global_weight": "0.8",
            },
        )
        self.assertEqual(options["symbols"], "/\\|_")
        self.assertEqual(options["fill_symbols"], ".:#@")
        self.assertEqual(options["global_weight"], 0.8)

    def test_bead_grid_accepts_high_resolution_boundary(self):
        options = coerce_options("bead", {"cols": 2048, "rows": 2048, "colors": 128})
        self.assertEqual(options["cols"], 2048)
        self.assertEqual(options["rows"], 2048)
        self.assertEqual(options["colors"], 128)
        with self.assertRaisesRegex(ValueError, "Grid columns must be at most 2048"):
            coerce_options("bead", {"cols": 2049})
        with self.assertRaisesRegex(ValueError, "Palette size must be at most 128"):
            coerce_options("bead", {"colors": 129})


class CliTests(unittest.TestCase):
    def test_bead_mode_parser(self):
        args = build_parser().parse_args(
            [
                "bead",
                "portrait.png",
                "--colors",
                "10",
                "--finish",
                "matte",
                "--chart-title",
                "Pattern A",
                "--chart-cell-size",
                "20",
                "--chart",
                "pattern.png",
            ]
        )
        self.assertEqual(args.command, "bead")
        self.assertEqual(args.colors, 10)
        self.assertEqual(args.finish, "matte")
        self.assertEqual(args.chart_title, "Pattern A")
        self.assertEqual(args.chart_cell_size, 20)
        self.assertEqual(str(args.chart), "pattern.png")
        self.assertFalse(hasattr(args, "font"))

    def test_explicit_mode_parser(self):
        args = build_parser().parse_args(["block", "portrait.png", "--colors", "3"])
        self.assertEqual(args.command, "block")
        self.assertEqual(args.colors, 3)
        self.assertFalse(hasattr(args, "font"))

    def test_glyph_parser_exposes_custom_character_controls(self):
        args = build_parser().parse_args(
            [
                "glyph",
                "portrait.png",
                "--font",
                "mono.ttf",
                "--profile",
                "tone",
                "--color-mode",
                "mono",
                "--symbols",
                "/\\|_",
            ]
        )
        self.assertEqual(args.profile, "tone")
        self.assertEqual(args.color_mode, "mono")
        self.assertEqual(args.symbols, "/\\|_")

    def test_legacy_style_is_translated(self):
        self.assertEqual(
            _normalize_legacy_argv(
                ["portrait.png", "--style", "glyph", "--font", "mono.ttf"]
            ),
            ["glyph", "portrait.png", "--font", "mono.ttf"],
        )


class WebTests(unittest.TestCase):
    def test_workbench_exposes_bilingual_interface(self):
        static = resources.files("edgeglyph.web").joinpath("static")
        html = static.joinpath("index.html").read_text(encoding="utf-8")
        script = static.joinpath("app.js").read_text(encoding="utf-8")
        self.assertIn('id="language-toggle"', html)
        self.assertIn('data-i18n="section.parameters"', html)
        self.assertIn('"parameters.cols.label": "列数"', script)
        self.assertIn('localStorage.setItem("edgeglyph-locale-v1"', script)
        self.assertIn("createTextControl", script)
        self.assertIn('"choices.mono": "黑白（mono）"', script)
        self.assertIn('data-export="chart"', html)
        self.assertIn('"parameters.chart_title.label": "图纸标题"', script)

    def test_application_schema_exposes_fonts_separately(self):
        schema = application_schema()
        self.assertIn("modes", schema)
        self.assertIn("fonts", schema)
        self.assertIn("font", schema["defaults"])

    def test_block_request_returns_all_download_formats(self):
        result = render_payload(
            {
                "mode": "block",
                "source": encoded_test_image(),
                "options": {"cols": 12, "rows": 6, "colors": 3, "oversample": 3},
            }
        )
        self.assertTrue(result["preview"].startswith("data:image/png;base64,"))
        self.assertIsNone(result["chart"])
        self.assertIn("Generated by EdgeGlyph", result["lua"])
        self.assertEqual(result["metrics"]["mode"], "block")
        self.assertEqual(result["metrics"]["cols"], 12)
        self.assertLessEqual(len(result["palette"]), 3)

    def test_bead_request_returns_physical_preview_and_counts(self):
        result = render_payload(
            {
                "mode": "bead",
                "source": encoded_test_image(),
                "options": {
                    "cols": 12,
                    "rows": 12,
                    "colors": 4,
                    "oversample": 3,
                    "bead_size": 8,
                },
            }
        )
        self.assertTrue(result["preview"].startswith("data:image/png;base64,"))
        self.assertTrue(result["chart"].startswith("data:image/png;base64,"))
        self.assertEqual(result["metrics"]["mode"], "bead")
        self.assertGreater(result["metrics"]["bead_count"], 0)
        self.assertEqual(
            sum(result["metrics"]["palette_counts"]),
            result["metrics"]["bead_count"],
        )
        self.assertNotIn("characters", result["metrics"])


if __name__ == "__main__":
    unittest.main()
