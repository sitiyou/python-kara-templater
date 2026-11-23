import unittest
from dataclasses import replace
from pathlib import Path

from kara_templater import Document, Scene, Style, text_extents
from kara_templater.ass import STYLE_FORMAT, format_time, parse_time

ROOT = Path(__file__).resolve().parents[1]


class AssTests(unittest.TestCase):
    def test_code_authored_rgb_and_parsed_video_color_metadata(self):
        created = Document.create()
        self.assertEqual(created.meta["ycbcr matrix"], "None")
        self.assertEqual(Document.parse(created.dumps()).dumps(), created.dumps())
        for field in ("", "YCbCr Matrix: TV.601\n", "YCbCr Matrix: TV.709\n"):
            with self.subTest(field=field):
                text = created.dumps().replace("YCbCr Matrix: None\n", field)
                parsed = Document.parse(text)
                # Parsing/compiling an existing script must retain its choice,
                # including absence; only newly authored documents choose RGB.
                self.assertEqual(parsed.dumps(), text)
                self.assertEqual(Scene(parsed).ass.compile().document.dumps(), text)

    def test_example_roundtrip(self):
        doc = Document.load(ROOT / "examples/karaoke.ass")
        other = Document.parse(doc.dumps())
        self.assertEqual(other.dumps(), doc.dumps())
        self.assertEqual(
            doc.lines[-1].text, r"{\k50}Ka|ka{\k50}ra|ra{\k50}o|o{\k50}ke|ke"
        )

    def test_unknown_fields_sections_commas_and_reordered_format(self):
        text = (
            "[Script Info]\nPlayResX: 640\n[V4+ Styles]\nFormat: "
            + STYLE_FORMAT
            + "\n"
            + Style().serialize()
            + "\n[Events]\nFormat: Start, End, Name, Style, Effect, Layer, MarginL, MarginR, MarginV, Custom, Text\nDialogue: 0:00:01.00,0:00:02.00,actor,Default,,3,0,0,0,keep,a,b,c\n[Fonts]\nfontname: keep.ttf\nabc123\n"
        )
        doc = Document.parse(text)
        self.assertEqual(doc.lines[0].text, "a,b,c")
        self.assertEqual(doc.lines[0].actor, "actor")
        self.assertEqual(doc.meta.res_y, 480)
        self.assertIn("keep,a,b,c", doc.dumps())
        self.assertTrue(doc.dumps().endswith("fontname: keep.ttf\nabc123\n"))

    def test_time(self):
        self.assertEqual(parse_time("1:02:03.45"), 3723450)
        self.assertEqual(format_time(3723456), "1:02:03.45")
        self.assertEqual(format_time(-100), "0:00:00.00")
        with self.assertRaises(ValueError):
            parse_time("0:61:00.00")

    def test_fractional_style_values(self):
        style = Style(
            fontsize=20.5,
            scale_x=90.25,
            scale_y=105.5,
            spacing=0.75,
            outline=1.5,
            shadow=0.25,
        )
        text = "[V4+ Styles]\nFormat: " + STYLE_FORMAT + "\n" + style.serialize()
        parsed = Document.parse(text).styles["Default"]
        for attr in ("fontsize", "scale_x", "scale_y", "spacing", "outline", "shadow"):
            self.assertEqual(getattr(parsed, attr), getattr(style, attr))

    def test_large_fractional_values_keep_precision(self):
        style = Style(fontsize=123456.75)
        text = "[V4+ Styles]\nFormat: " + STYLE_FORMAT + "\n" + style.serialize()
        self.assertEqual(Document.parse(text).styles["Default"].fontsize, 123456.75)

    def test_resolution(self):
        self.assertEqual(Document.parse("").meta.res_x, 384)
        self.assertEqual(
            Document.parse("[Script Info]\nPlayResY: 1024").meta.res_x, 1280
        )


class MetricsTests(unittest.TestCase):
    def setUp(self):
        self.style = Style(fontname="sans-serif", fontsize=32, outline=0)

    def test_empty_and_spaces(self):
        self.assertEqual(text_extents(self.style, "")[0], 0)
        space = text_extents(self.style, " ")[0]
        self.assertGreater(space, 0)
        self.assertAlmostEqual(text_extents(self.style, "   ")[0], 3 * space, delta=0.1)
        self.assertAlmostEqual(
            text_extents(self.style, " A ")[0],
            text_extents(self.style, "A")[0] + 2 * space,
            delta=0.1,
        )

    def test_outline_pads_each_ink_bearing_line_once(self):
        outlined = replace(self.style, outline=2.5, spacing=1.5)
        plain = replace(outlined, outline=0)
        for text in ("AV", r" AV\h", r"A\NB", "A\n\nB"):
            rows = 2 if "B" in text else 1
            w, h, d, leading = text_extents(plain, text)
            self.assertEqual(text_extents(outlined, text), (w + 5, h + rows * 5, d + 2.5, leading))
        for text in ("", "  ", r"\N\h", "\u2060"):
            self.assertEqual(text_extents(outlined, text), text_extents(plain, text))

    def test_scale_spacing_and_height(self):
        w, h, d, leading = text_extents(self.style, "AV")
        self.assertGreater(h, 0)
        self.assertGreaterEqual(d, 0)
        self.assertEqual(leading, 0)
        scaled = text_extents(replace(self.style, scale_x=200, scale_y=150), "AV")
        self.assertAlmostEqual(scaled[0], w * 2, delta=0.2)
        self.assertAlmostEqual(scaled[1], h * 1.5, delta=0.2)
        self.assertGreater(text_extents(replace(self.style, spacing=3), "AV")[0], w)

    def test_unicode_fallback_literals_and_long_text(self):
        for text in ("你好", "مرحبا", "e\u0301", "{hello}", "🙂"):
            self.assertGreater(text_extents(self.style, text)[0], 0)
        self.assertGreater(
            text_extents(self.style, "x" * 3000)[0],
            text_extents(self.style, "x" * 1000)[0] * 2.9,
        )

    def test_hard_newline(self):
        w, h, _, _ = text_extents(self.style, r"A\NA")
        single = text_extents(self.style, "A")
        self.assertAlmostEqual(w, single[0], delta=0.1)
        self.assertAlmostEqual(h, single[1] * 2, delta=0.2)

    def test_invalid_and_repeated_calls(self):
        for size in (0, -1, float("nan")):
            with self.assertRaises(ValueError):
                text_extents(replace(self.style, fontsize=size), "a")
        for _ in range(100):
            for text in ("a", "", " ", "{}", "b"):
                self.assertEqual(len(text_extents(self.style, text)), 4)
