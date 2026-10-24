import unittest

from kara_templater import KaraokeLine, Segment, Style, TextUnit, layout_line


class StructuredLayoutTests(unittest.TestCase):
    def test_independent_overlapping_units(self):
        source = KaraokeLine((TextUnit("A", (Segment(0, 2000),)), TextUnit("B", (Segment(1000, 3000),))))
        result = layout_line(source, style=Style())
        self.assertEqual(tuple(u.source for u in result.units), source.units)
        self.assertGreater(result.units[1].box.left, result.units[0].box.left)

    def test_shared_base_segments_must_not_overlap(self):
        with self.assertRaisesRegex(ValueError, "字"):
            TextUnit("字", (Segment(0, 2000, "あ"), Segment(1000, 3000, "い")))

    def test_ruby_parts_partition_one_base(self):
        source = KaraokeLine((TextUnit("今日", (Segment(0, 1000, "きょ"), Segment(1500, 2000, "う"))),))
        unit = layout_line(source, style=Style()).units[0]
        first, last = unit.segments
        self.assertEqual(first.left, unit.box.left)
        self.assertEqual(first.right, last.left)
        self.assertAlmostEqual(last.right, unit.box.right)
        self.assertLess(first.ruby.top, unit.box.top)
        self.assertLess(first.ruby.left, last.ruby.left)

    def test_static_and_zero_duration_units(self):
        result = layout_line(KaraokeLine((TextUnit(" "), TextUnit("A", (Segment(0, 0),)))), style=Style())
        self.assertEqual(result.units[0].segments, ())
        self.assertEqual(result.units[1].segments[0].source.end_ms, 0)

    def test_display_order_is_not_time_order(self):
        source = KaraokeLine((TextUnit("A", (Segment(2000, 3000),)), TextUnit("B", (Segment(0, 1000),))))
        layout = layout_line(source, style=Style())
        self.assertLess(layout.units[0].box.left, layout.units[1].box.left)
        self.assertEqual(layout.units[0].segments[0].source.start_ms, 2000)
        self.assertEqual(layout.units[1].segments[0].source.start_ms, 0)

    def test_ruby_style_and_right_alignment(self):
        source = KaraokeLine((TextUnit("A", (Segment(0, 1000, "a"),)),))
        style = Style(align=3, margin_r=50, margin_v=25)
        ruby_style = Style(fontsize=12)
        layout = layout_line(source, style=style, ruby_style=ruby_style, resolution=(640, 480))
        self.assertAlmostEqual(layout.box.right, 590)
        self.assertAlmostEqual(layout.box.top + layout.box.height, 455)
        larger = layout_line(source, style=style, ruby_style=Style(fontsize=24), resolution=(640, 480))
        self.assertLess(layout.units[0].segments[0].ruby.height, larger.units[0].segments[0].ruby.height)
        self.assertEqual(source.units[0].segments[0], Segment(0, 1000, "a"))

    def test_invalid_layout_parameters(self):
        for resolution in ((0, 480), (640, -1)):
            with self.assertRaises(ValueError):
                layout_line(KaraokeLine(()), style=Style(), resolution=resolution)
        with self.assertRaises(ValueError):
            layout_line(KaraokeLine(()), style=Style(align=0))

    def test_invalid_times(self):
        for start, end in ((-1, 0), (2, 1), (0.5, 1)):
            with self.assertRaises(ValueError):
                Segment(start, end)
