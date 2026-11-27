"""Transfer a timed body sweep onto measured replacement text."""

from dataclasses import dataclass, replace
from math import radians, tan

from ..composition import Color
from ..geometry import Region, Vec2
from ..lyric_line import LyricLine
from ..paint_fields import MaterialClip, PaintInput, _PaintTrack
from ..parameters import LengthExpr, _width
from ..scene import TextObject
from ..scene_animation import TimeSpan
from ..text.layout import PositionedText
from .highlights import (
    _ITALIC_SWEEP_ANGLE,
    LyricHighlights,
    _arrival_region,
    _TimingHighlights,
)
from .materials import _ScanlineTint, _WipeTint


def _sweep_points(
    highlighter: LyricHighlights, line: LyricLine, start: int, end: int,
) -> tuple[tuple[tuple[float, float], ...], bool]:
    if line.layout._vertical:
        raise ValueError("a replacement sweep requires horizontal lyrics")
    if not 0 <= start < end <= len(line.layout.lyrics.body.text):
        raise ValueError("invalid replacement sweep text range")
    selected = tuple(
        (target, glyph)
        for target, glyph in zip(line.query("character"), line.layout.body.characters, strict=True)
        if glyph.start < end and start < glyph.end
    )
    if not selected or min(g.start for _, g in selected) != start or max(g.end for _, g in selected) != end:
        raise ValueError("replacement sweep range must align to shaped clusters")

    regions = []
    unit = None
    delay = selected[0][0].delay
    for target, _ in selected:
        geometry = _arrival_region(line, target, automatic=True)
        if geometry is None or target.delay != delay:
            raise ValueError("replacement sweep range must share one measured clock")
        index, _, region = geometry
        if unit is not None and unit != index:
            raise ValueError("replacement sweep range must belong to one lyric unit")
        unit = index
        regions.append(region)
    fragment = Region(min(r.left for r in regions), max(r.right for r in regions))
    source = highlighter.highlights
    assert isinstance(source, _TimingHighlights)
    chosen = tuple(h for h in source(line) if h.unit == unit)
    if len(chosen) != 1 or not chosen[0].passes or not fragment.width:
        raise ValueError("replacement sweep range needs one timed highlight")

    passes = chosen[0].passes
    reverse = passes[0].reverse
    points: list[tuple[float, float]] = []
    current_round = passes[0].round

    def add(time: float, progress: float) -> None:
        key = (time + delay, progress)
        if points and points[-1] == key:
            return
        if len(points) > 1 and points[-2][0] == key[0]:
            points[-1] = key
        else:
            points.append(key)

    for sweep in passes:
        if sweep.round != current_round:
            # A repeated sweep resets the face at the start of its note.
            if points:
                add(sweep.time.start, points[-1][1])
                add(sweep.time.start, 0)
            current_round = sweep.round
        left, right = max(fragment.left, sweep.region.left), min(fragment.right, sweep.region.right)
        if left >= right:
            continue
        for x in sweep._edges(Region(left, right)):
            time = sweep.arrival(x)
            assert time is not None
            distance = fragment.right - x if reverse else x - fragment.left
            add(time, distance / fragment.width)
    if not points:
        raise ValueError("replacement sweep range has no timed coverage")
    return tuple(points), reverse


@dataclass(frozen=True, kw_only=True)
class LyricSweep:
    """A measured lyric sweep that can paint either version of a glyph run.

    Get it from `KaraokeEffects.sweep()`. Its absolute clock includes note
    checkpoints and rests. Apply it independently to the old and new layouts,
    then animate those drawings under ordinary scene groups.
    """

    _points: tuple[tuple[float, float], ...]
    _reverse: bool
    _angle: float | None
    _script_height: int
    _before: Color
    _after: Color
    _feather: float | LengthExpr
    _scanline_color: Color | PaintInput | None
    _scanline_width: float | LengthExpr | PaintInput
    _scanline_softness: float | LengthExpr | PaintInput
    _scanline_strength: float | PaintInput

    @property
    def interval(self) -> TimeSpan:
        """The first entrance and last completion in absolute scene seconds."""
        return TimeSpan(self._points[0][0], self._points[-1][0])

    def paint(self, glyphs: tuple[PositionedText, ...]) -> tuple[TextObject, ...]:
        """Return the measured drawings with the shared sweep on their fill.

        Supply clusters from one measured horizontal run in their original
        coordinate space. The ink bounds define the new sweep extent and the
        run's first glyph size resolves relative brush widths. After binding,
        drawings can use different lifetimes and parent transforms. Their
        explicit clock origins preserve the sweep on a late-appearing drawing.
        The material is supported by browser and Hook output.
        """
        ink = tuple(g.ink_bounds for g in glyphs if g.ink_bounds and g.ink_bounds.width)
        if not ink:
            raise ValueError("replacement sweep needs measured text ink")
        size = glyphs[0].object.font_size
        feather = _width(self._feather, size, self._script_height, "hook_feather")
        padding = feather / 2 + 1
        scanline = None
        if self._scanline_color is not None:
            def brush_width(value: float | LengthExpr | PaintInput, role: str) -> float | PaintInput:
                return value if isinstance(value, PaintInput) else _width(value, size, self._script_height, role)

            width = brush_width(self._scanline_width, "scanline_width")
            softness = brush_width(self._scanline_softness, "scanline_softness")
            if isinstance(width, PaintInput):
                assert width.control is not None and width.control.bounds is not None
                band_width = width.control.bounds[1]
            else:
                band_width = width
            if not band_width:
                raise ValueError("scanline_width must be positive")
            padding = max(padding, band_width / 2 + 1)
            scanline = self._scanline_color, width, softness

        angle = self._angle
        if angle is None:
            angle = _ITALIC_SWEEP_ANGLE if any(g._italic for g in glyphs) else 0
        slope = tan(radians(angle))
        left = min(b.left + min(slope * b.top, slope * (b.top + b.height)) for b in ink)
        right = max(b.right + max(slope * b.top, slope * (b.top + b.height)) for b in ink)
        sign = -1 if self._reverse else 1
        extent = Region(-right - padding, -left + padding) if self._reverse else Region(left - padding, right + padding)

        result = []
        for glyph in glyphs:
            node = glyph.object
            transform = node.state.transform
            axis = Vec2(sign * (transform.a + slope * transform.b), sign * (transform.c + slope * transform.d))
            offset = sign * (transform.tx + slope * transform.ty)
            clock = node.time_origin
            front = _PaintTrack(tuple((time - clock, extent.at(progress) - offset) for time, progress in self._points))
            state = replace(node.state, fill=self._after)
            materials = (*node.material_effects, MaterialClip(
                effect=_WipeTint(front, axis, self._before, feather), start=-clock,
            ))
            if scanline is not None:
                color, width, softness = scanline
                materials += (MaterialClip(
                    effect=_ScanlineTint(
                        front, _PaintTrack(((0, 1),)), axis, 0, color,
                        width, softness, Vec2(-65536, 65536), self._scanline_strength, 0,
                    ),
                    start=-clock,
                ),)
            result.append(replace(node, state=state, clock_start=clock, material_effects=materials))
        return tuple(result)
