import unittest
from dataclasses import replace
from pathlib import Path

from kara_templater import (
    Document,
    Engine,
    Line,
    Style,
    TemplateError,
    apply_templates,
    preprocess,
    split_karaoke,
    text_extents,
)
from kara_templater.ass import EVENT_FORMAT, STYLE_FORMAT, format_time, parse_time

ROOT = Path(__file__).resolve().parents[1]


def document(*lines):
    return Document.parse(
        "[Script Info]\nPlayResX: 640\nPlayResY: 480\n[V4+ Styles]\nFormat: "
        + STYLE_FORMAT
        + "\n"
        + Style(fontname="sans-serif").serialize()
        + "\n[Events]\nFormat: "
        + EVENT_FORMAT
        + "\n"
        + "\n".join(line.serialize() for line in lines)
        + "\n"
    )


def template(text, effect="template syl noblank", **kwargs):
    return Line(text=text, effect=effect, comment=True, **kwargs)


def source(text=r"{\k20}a{\k30}b", **kwargs):
    return Line(text=text, start_time=1000, end_time=2000, **kwargs)


def effects(doc):
    return [line for line in doc.lines if not line.comment and line.effect == "fx"]


class AssTests(unittest.TestCase):
    def test_example_roundtrip(self):
        doc = Document.load(ROOT / "examples/karaoke.ass")
        other = Document.parse(doc.dumps())
        self.assertEqual(other.dumps(), doc.dumps())
        self.assertEqual(doc.lines[-1].text, r"{\k50}你{\k50}好{\k50}世{\k50}界")

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
            fontsize=20.5, scale_x=90.25, scale_y=105.5, spacing=0.75, outline=1.5, shadow=0.25
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
        self.assertEqual(Document.parse("[Script Info]\nPlayResY: 1024").meta.res_x, 1280)


class MetricsTests(unittest.TestCase):
    def setUp(self):
        self.style = Style(fontname="sans-serif", fontsize=32)

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
            text_extents(self.style, "x" * 3000)[0], text_extents(self.style, "x" * 1000)[0] * 2.9
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


class LayoutTests(unittest.TestCase):
    def test_tags_zero_syllable_and_timing(self):
        syls, furi = split_karaoke(r"{\k0\i1}{\K20} a {\ko30}b")
        self.assertEqual(len(syls), 3)
        self.assertEqual([s.i for s in syls], [0, 1, 2])
        self.assertEqual(syls[1].tag, r"\kf")
        self.assertEqual(syls[1].text, r"{\i1} a ")
        self.assertEqual(
            (syls[1].prespace, syls[1].text_spacestripped, syls[1].postspace), (" ", "a", " ")
        )
        self.assertEqual((syls[2].start_time, syls[2].end_time), (200, 500))
        self.assertFalse(furi)

    def test_multi_furigana_and_fx(self):
        syls, furi = split_karaoke(r"{\k20\-spark}漢|かん{\k30}＃{\k50}字｜＜じ")
        self.assertEqual([s.text_stripped for s in syls], ["", "漢", "字"])
        self.assertEqual(syls[1].duration, 500)
        self.assertEqual(len(syls[1].highlights), 2)
        self.assertEqual(syls[2].inline_fx, "spark")
        self.assertEqual([f.text for f in furi], ["かん", "じ"])
        self.assertTrue(furi[1].spillback)

    def test_effective_margins(self):
        doc = document(source(margin_l=-5, margin_r=25, margin_v=-10))
        line = preprocess(doc.lines[0], doc.styles, doc.meta)
        self.assertEqual((line.eff_margin_l, line.eff_margin_r, line.eff_margin_v), (10, 25, 10))

    def test_drawing_not_visible(self):
        syls, _ = split_karaoke(r"{\k20\p1}m 0 0 l 10 10{\p0}a")
        self.assertEqual(syls[-1].text_stripped, "a")
        self.assertIn("m 0 0", syls[-1].text)

    def test_alignment_space_and_furi(self):
        for alignment in range(1, 10):
            doc = document(source(r"{\k20} a {\k30}b"))
            doc.styles["Default"].align = alignment
            line = preprocess(doc.lines[0], doc.styles, doc.meta)
            self.assertGreater(line.kara[1].prespacewidth, 0)
            self.assertGreater(line.kara[2].left, line.kara[1].right)
            self.assertAlmostEqual(line.right - line.left, line.width)
            if alignment in (1, 4, 7):
                self.assertEqual(line.x, 10)
            if alignment in (3, 6, 9):
                self.assertEqual(line.x, 630)
        doc = document(source(r"{\k20}漢|かん{\k30}字|じ"))
        line = preprocess(doc.lines[0], doc.styles, doc.meta)
        self.assertEqual(line.text_stripped, "漢字")
        self.assertEqual(line.furistyle.fontsize, line.styleref.fontsize / 2)
        self.assertGreaterEqual(line.furi[1].left, line.furi[0].right)


class EngineTests(unittest.TestCase):
    def test_example_and_idempotence(self):
        original = Document.load(ROOT / "examples/karaoke.ass")
        original_text = original.dumps()
        result = apply_templates(original)
        self.assertEqual(original.dumps(), original_text)
        fx = effects(result)
        self.assertEqual(len(fx), 4)
        self.assertEqual([f.text[-1] for f in fx], list("你好世界"))
        self.assertEqual(
            [(f.start_time, f.end_time) for f in fx],
            [(1000, 1500), (1500, 2000), (2000, 2500), (2500, 3000)],
        )
        self.assertEqual(apply_templates(result).dumps(), result.dumps())

    def test_all_retime_modes(self):
        expected = {
            "line": (990, 2020),
            "preline": (990, 1020),
            "postline": (1990, 2020),
            "syl": (1190, 1520),
            "presyl": (1190, 1220),
            "postsyl": (1490, 1520),
            "start2syl": (990, 1220),
            "syl2end": (1490, 2020),
            "abs": (-10, 20),
            "set": (-10, 20),
            "sylpct": (1170, 1260),
        }
        for mode, times in expected.items():
            with self.subTest(mode=mode):
                doc = document(template(f'!retime("{mode}", -10, 20)!'), source())
                fx = effects(apply_templates(doc))
                self.assertEqual((fx[1].start_time, fx[1].end_time), times)

    def test_preline_named_combination(self):
        doc = document(
            template(r"{\an5}", "template pre-line joined"),
            template(r"{\k$kdur}", "template line joined"),
            source(),
        )
        fx = effects(apply_templates(doc))
        self.assertEqual(len(fx), 1)
        self.assertEqual(fx[0].text, r"{\an5}{\k20}a{\k30}b")

    def test_named_template_modifiers_persist(self):
        doc = document(
            template("prefix", "template pre-line joined all notext repeat 2"),
            template("$i", "template line joined"),
            source(style="Other"),
        )
        fx = effects(apply_templates(doc))
        self.assertEqual([x.text for x in fx], ["prefix12", "prefix12"])

    def test_preline_without_main_text(self):
        doc = document(template(r"{\an5}", "template pre-line"), source())
        self.assertEqual(effects(apply_templates(doc))[0].text, r"{\an5}ab")

    def test_code_contexts_loops_groups_style_and_helpers(self):
        doc = document(
            template('count = 0; fxgroup["skip"] = False', "code once"),
            template("count += 1", "code line repeat 2"),
            template("count += 10", "code syl noblank"),
            template(
                '!relayer(7)!!remember("v", count)!!recall("v")!:$i:$dur:!j!',
                "template syl noblank repeat 2 notext",
            ),
            template("skip", "template syl fxgroup skip"),
            source(),
            source(style="Other"),
        )
        fx = effects(apply_templates(doc))
        self.assertEqual(len(fx), 4)
        self.assertEqual(fx[0].text, "1212:1:200:1")
        self.assertEqual(fx[-1].text, "2222:2:300:2")
        self.assertTrue(all(f.layer == 7 for f in fx))

    def test_all_styles_and_keeptags(self):
        doc = document(
            template("", "template syl all keeptags noblank notext"),
            source(r"{\k20\i1}a", style="Other"),
        )
        self.assertEqual(effects(apply_templates(doc))[0].text, r"{\i1}a")
        self.assertEqual(effects(apply_templates(doc))[0].style, "Default")

    def test_char_multi_and_fx(self):
        doc = document(
            template("!retime('syl')!", "template syl char multi fx spark noblank"),
            source(r"{\k20\-spark}ab{\k30}#{\k20\-other}c"),
        )
        fx = effects(apply_templates(doc))
        self.assertEqual([x.text for x in fx], ["a", "a", "b", "b"])
        self.assertEqual([(x.start_time, x.end_time) for x in fx], [(1000, 1200), (1200, 1500)] * 2)

    def test_furigana(self):
        doc = document(
            template("!retime('syl')!", "template furi noblank"),
            source(r"{\k20}漢|かん{\k30}字|じ"),
        )
        result = apply_templates(doc)
        self.assertEqual([x.text for x in effects(result)], ["かん", "じ"])
        self.assertTrue(all(x.style == "Default-furigana" for x in effects(result)))
        self.assertIn("Default-furigana", result.styles)
        self.assertEqual(apply_templates(result).dumps(), result.dumps())

    def test_memory_scopes(self):
        doc = document(
            template('!remember_line("linevalue", orgline.i)!', "template syl noblank notext"),
            template('!recall("linevalue", -1)!', "template syl noblank notext"),
            source(),
        )
        fx = effects(apply_templates(doc))
        self.assertEqual([x.text for x in fx], ["3", "3", "3", "3"])
        doc = document(
            template('!remember_syl("value", syl.i)!', "template syl noblank notext"),
            template('!recall("value", -1)!', "template syl noblank notext"),
            source(),
        )
        self.assertEqual([x.text for x in effects(apply_templates(doc))], ["1", "1", "2", "2"])

    def test_restyle_and_memory_decorator(self):
        doc = document(
            template('remember("initial", False)', "code once"),
            template(
                '!restyle("Alternate")!!recall("initial", "wrong")!!remember_if("v", 7, True, lambda name: (orgline.i, name))!!recall("v")!',
                "template syl noblank notext",
            ),
            source(r"{\k10}a"),
        )
        pos = next(i for i, record in enumerate(doc.records) if isinstance(record, Style))
        doc.records.insert(pos, Style(name="Alternate"))
        fx = effects(apply_templates(doc))
        self.assertEqual(fx[0].style, "Alternate")
        self.assertEqual(fx[0].text, "False77")

    def test_expressions_and_loop_controls(self):
        doc = document(
            template('!"yes!" if 1 != 2 else "no"!', "template syl noblank notext"), source()
        )
        self.assertEqual(effects(apply_templates(doc))[0].text, "yes!")
        doc = document(
            template("!maxloops(2)!!j!", "template syl noblank notext"), source(r"{\k10}a")
        )
        self.assertEqual([x.text for x in effects(apply_templates(doc))], ["1", "2"])

    def test_error_context_and_limits(self):
        for t in (
            template("$unknown"),
            template("!unknown()!"),
            template("!1 + !"),
            template("", "template repeat bad"),
            template("", "template unsupported"),
        ):
            with (
                self.subTest(text=t.text, effect=t.effect),
                self.assertRaisesRegex(TemplateError, "Event 1"),
            ):
                apply_templates(document(t, source()))
        with self.assertRaisesRegex(TemplateError, "Iteration limit"):
            Engine(max_iterations=3).apply(document(template("!loopctl(0, 2)!"), source()))
        with self.assertRaisesRegex(TemplateError, "Output line limit"):
            Engine(max_output_lines=1).apply(document(template(""), source()))

    def test_character_video_correction(self):
        doc = document(
            template("$sleft:$sright", "template syl char noblank notext"), source(r"{\k20}ab")
        )
        normal = effects(apply_templates(doc))
        corrected = effects(apply_templates(doc, video_size=(640, 960)))

        def width(line):
            left, right = map(float, line.text.split(":"))
            return right - left

        for a, b in zip(normal, corrected):
            self.assertAlmostEqual(width(b), width(a) * 2, delta=2)

    def test_non_karaoke_untouched_and_video_correction(self):
        doc = document(template("$swidth", "template syl noblank notext"), source(effect="other"))
        self.assertEqual(doc.dumps(), apply_templates(doc).dumps())
        doc = document(template("$swidth", "template syl noblank notext"), source(r"{\k10}a"))
        normal = float(effects(apply_templates(doc))[0].text)
        corrected = float(effects(apply_templates(doc, video_size=(640, 960)))[0].text)
        self.assertAlmostEqual(corrected, 2 * normal, delta=1)


if __name__ == "__main__":
    unittest.main()
