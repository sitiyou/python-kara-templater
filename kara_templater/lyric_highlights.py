"""Named highlight ownership projected into common masks or coverage partitions."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from functools import partial
from math import ceil
from statistics import NormalDist
from typing import Literal

from .composition import _ASS_BLUR_TO_SIGMA, Color, Glow
from .coverage_animation import Coverage, CoveragePartition, GlowFunction
from .document_lyrics import LyricUnit
from .geometry import Vec2, finite
from .lyric_line import LyricLine, LyricTarget, _line_x
from .model import Box
from .paint_fields import ColorRamp, ColorStop, LinearGradient, PaintField, _mix
from .raster_settings import RasterSettings
from .scene import (
    ObjectGroup,
    RectangleClip,
    RectangleFunction,
    RectangleKeyframes,
    SceneObject,
    _CellWipeClip,
)
from .scene_animation import StatePatch, TimeSpan, VisualState, linear_rate
from .scene_lyrics import LyricLayout, _after_onset
from .scene_text import PositionedText
from .text_geometry import _VectorGuideText
from .timeline import Region, union_regions

type LyricGlow = (
    Glow
    | GlowFunction
    | Callable[[LyricLine, LyricTarget], Glow | GlowFunction | None]
    | None
)

type _ResolvedStyleMaterial = PaintField | Callable[[LyricLine, LyricTarget], PaintField | None] | None
type LyricMaterial = _ResolvedStyleMaterial | Mapping[str, LyricGradient]


def _style_material(source: LyricMaterial, style: str | None) -> _ResolvedStyleMaterial:
    if isinstance(source, Mapping):
        gradient = source.get(style) if style is not None else None
        if gradient is not None and not isinstance(gradient, LyricGradient):
            raise TypeError("style material must be a LyricGradient")
        return gradient
    return source


def _resolve_material(
    source: LyricMaterial, line: LyricLine, target: LyricTarget,
    character: PositionedText | None = None,
) -> PaintField | None:
    source = _style_material(source, target.source_style)
    value = source(line, target) if callable(source) else source
    if (character is not None and isinstance(source, LyricGradient)
            and source.axis == "x" and isinstance(value, LinearGradient)):
        # A body-wide brush only needs its stops under this glyph's fill.
        # Include overhangs and an antialiasing pixel on either edge.
        assert value.fill is not None and character.layout_scale is not None
        ink = character.ink_bounds or character.bounds
        left, right = _line_x(character, ink.left, ink.right)
        left -= 1
        right += 1
        value = replace(value, fill=ColorRamp((
            ColorStop(left, value.fill.at(left)),
            *(s for s in value.fill.stops if left < s.position < right),
            ColorStop(right, value.fill.at(right)),
        )))
    if value is not None and not isinstance(value, PaintField):
        raise TypeError("lyric material factory must return a PaintField or None")
    return value


@dataclass(frozen=True)
class LyricGradient:
    """Evenly spaced colors on measured lyrics. Vertical colors span each glyph.
    Horizontal colors span all body glyphs sharing an ASS style and their readings.

    Pass as material to LyricHighlights.from_singing. Coordinates are derived
    from undecorated glyph bounds, independent of glow/outline;
    step is color-band width in local script pixels. This factory produces an
    ordinary LinearGradient and inherits its renderer restrictions.
    """

    colors: tuple[Color, ...]
    step: int = 1
    axis: Literal["x", "y"] = "y"

    def __post_init__(self) -> None:
        if self.axis not in ("x", "y"):
            raise ValueError("lyric gradient axis must be x or y")
        if len(self.colors) < 2 or not all(isinstance(c, Color) for c in self.colors):
            raise ValueError("lyric gradient needs at least two Color values")
        if type(self.step) is not int or self.step < 1:
            raise ValueError("lyric gradient step must be a positive integer")

    def __call__(self, line: LyricLine, target: LyricTarget) -> LinearGradient:
        """Resolve a local fill gradient once during lyric preparation."""
        left, right = 0.0, 2 * target.center.y
        if self.axis == "x":
            if target._line_x is None:
                raise ValueError("horizontal lyric gradient needs a measured lyric target")
            left, right = target._line_x
        return self._between(left, right)

    def _between(self, left: float, right: float) -> LinearGradient:
        extent = right - left
        if extent <= 0:
            raise ValueError("lyric gradient needs a positive measured glyph extent")
        return LinearGradient(
            fill=ColorRamp(tuple(
                ColorStop(left + extent * index / (len(self.colors) - 1), color)
                for index, color in enumerate(self.colors)
            )),
            axis=self.axis, step=self.step, space="local",
        )


def _hard_glow_border(glow: LyricGlow) -> float:
    return glow.border if isinstance(glow, Glow) and not glow.blur and glow.opacity else 0


def _resolve_glow(
    glow: LyricGlow, line: LyricLine, target: LyricTarget
) -> Glow | GlowFunction | None:
    if glow is None or isinstance(glow, (Glow, GlowFunction)):
        return glow
    value = glow(line, target)
    if value is not None and not isinstance(value, (Glow, GlowFunction)):
        raise TypeError("lyric glow factory must return Glow, GlowFunction or None")
    return value


@dataclass(frozen=True)
class HighlightPass:
    """One horizontal pass, with absolute seconds and measured line-local x.

    reverse starts the front at the right edge and grows ownership to the left.

    round identifies repeat groups; reset discards previous rounds. rate receives
    normalized progress. Declared breakpoints are seconds from the pass start.
    A zero-duration pass reveals its entire region at its start, as ASS k0 does.
    """

    time: TimeSpan
    region: Region
    round: int = 0
    rate: Callable[[float], float] = linear_rate
    breakpoints: tuple[float, ...] = ()
    inverse_rate: Callable[[float], float] | None = None
    reverse: bool = False

    def _edges(self, region: Region) -> tuple[float, float]:
        return (region.right, region.left) if self.reverse else (region.left, region.right)

    def __post_init__(self) -> None:
        finite(*self.breakpoints)
        if self.time.start < 0:
            raise ValueError("highlight pass needs a nonnegative start")
        if type(self.round) is not int or self.round < 0:
            raise ValueError("highlight round must be a nonnegative integer")
        if any(t < 0 or t > self.time.duration for t in self.breakpoints):
            raise ValueError("highlight breakpoint lies outside pass duration")

    def front(self, time: float) -> float:
        """Return the line-local front coordinate at absolute Scene seconds."""
        start, end = self._edges(self.region)
        if self.time.duration == 0:
            return start if time < self.time.start else end
        if time <= self.time.start:
            return start
        if time >= self.time.end:
            return end
        value = self.rate((time - self.time.start) / self.time.duration)
        finite(value)
        return start + (end - start) * max(0, min(1, value))

    def arrival(self, x: float) -> float | None:
        """Return an exact crossing clock using a declared monotone inverse.

        Arbitrary forward callbacks cannot be reliably inverted by sampling.
        A nonlinear rate therefore needs inverse_rate for arrival bindings.
        """
        if not self.region.left <= x <= self.region.right or not self.region.width:
            return None
        if self.time.duration == 0:
            return self.time.start
        start, end = self._edges(self.region)
        progress = (x - start) / (end - start)
        if self.inverse_rate is not None:
            fraction = self.inverse_rate(progress)
        elif self.rate is linear_rate:
            fraction = progress
        else:
            raise ValueError("nonlinear highlight arrival requires inverse_rate")
        finite(fraction)
        if not 0 <= fraction <= 1:
            raise ValueError("inverse_rate must return a time fraction in 0..1")
        return self.time.start + fraction * self.time.duration


@dataclass(frozen=True)
class Highlight:
    """A named paint contribution for one lyric unit, independent of Track streams."""

    id: str
    unit: int
    passes: tuple[HighlightPass, ...]
    paint: StatePatch
    priority: int = 0
    repeat: Literal["hold", "reset"] = "hold"
    end: Literal["hold", "hide"] = "hold"
    glow: LyricGlow = None
    material: LyricMaterial = None

    def __post_init__(self) -> None:
        if (
            not self.id
            or type(self.unit) is not int
            or self.unit < 0
            or not self.passes
        ):
            raise ValueError("highlight needs identity, unit and passes")
        if self.repeat not in ("hold", "reset") or self.end not in ("hold", "hide"):
            raise ValueError("invalid highlight lifecycle")
        if not self.paint.channels <= frozenset(
            ("fill", "outline", "border", "blur", "shadow", "opacity")
        ):
            raise ValueError("highlight paint cannot change layout geometry")
        self.paint.interpolate(VisualState(), 1)
        for before, after in zip(self.passes, self.passes[1:], strict=False):
            if before.time.end > after.time.start or before.round > after.round:
                raise ValueError("highlight passes must be ordered and nonoverlapping")

    def regions(self, time: float) -> tuple[Region, ...]:
        """Resolve owned regions at absolute seconds, applying repeat/end policy."""
        if self.end == "hide" and time >= self.passes[-1].time.end:
            return ()
        started = tuple(span for span in self.passes if span.time.start <= time)
        if self.repeat == "reset" and started:
            started = tuple(span for span in started if span.round == started[-1].round)
        return union_regions(
            (Region(span.front(time), span.region.right) if span.reverse
             else Region(span.region.left, span.front(time)))
            for span in started
        )


@dataclass(frozen=True)
class _SingingHighlights:
    paint: StatePatch
    glow: LyricGlow
    material: LyricMaterial = None
    wipe: bool = True
    reverse: bool = False
    ruby_reading_units: bool = False

    def interval(self, start: float, end: float) -> TimeSpan:
        return TimeSpan(start if self.wipe else end, end)

    def _passes(self, layout: LyricLayout, unit: LyricUnit, region: Region) -> tuple[HighlightPass, ...]:
        if self.wipe:
            passes = []
            repeated = len(unit._body_singing()) > 1
            parts = layout._body_wipe(unit, reading_units=self.ruby_reading_units, reverse=self.reverse)
            for i, (span, a, b) in enumerate(parts):
                start, end = (1 - b, 1 - a) if self.reverse else (a, b)
                bounds = Region(region.left + region.width * start,
                                region.right if end == 1 else region.left + region.width * end)
                passes.append(HighlightPass(self.interval(span.start, span.end), bounds,
                                            round=i if repeated else 0, reverse=self.reverse))
            return tuple(passes)
        return tuple(HighlightPass(self.interval(span.start, span.end), region, round=i)
                     for i, span in enumerate(unit._body_singing()))

    def for_target(self, highlight: Highlight, target: LyricTarget, glyph: PositionedText) -> Highlight:
        if self.wipe and isinstance(glyph.object, _VectorGuideText) and all(
            p.time.duration == 0 for p in highlight.passes
        ):
            def after_start(p: HighlightPass) -> HighlightPass:
                start = _after_onset(p.time.start, glyph.object.lifetime.end)
                return replace(p, time=TimeSpan(start, start))
            return replace(highlight, passes=tuple(after_start(p) for p in highlight.passes))
        if target.role != "ruby" or (not self.wipe and len(highlight.passes) == 1):
            return highlight
        clock = target._reading_span if self.wipe and target._reading_span else target.singing[0]
        interval = self.interval(clock.start, clock.end)
        region = Region(min(p.region.left for p in highlight.passes),
                        max(p.region.right for p in highlight.passes))
        return replace(highlight, passes=(HighlightPass(interval, region, reverse=self.reverse),))

    def __call__(self, line: LyricLine) -> tuple[Highlight, ...]:
        return tuple(
            Highlight(
                f"singing:{index}",
                index,
                self._passes(line.layout, unit, _sweep_axis(box, line.layout._vertical)),
                self.paint,
                glow=self.glow,
                material=self.material,
                repeat="reset",
            )
            for index, unit in enumerate(line.layout.lyrics.units)
            if unit.segments
            and line.layout.lyrics.body.text[unit.start : unit.end].strip()
            for box in (line.layout.body.range_bounds(unit.start, unit.end),)
            if box.width > 0
        )


def _sweep_axis(box: Box, vertical: bool) -> Region:
    return Region(box.top, box.top + box.height) if vertical else Region(box.left, box.right)


_EDGE_SECONDS = 0.02


def _owners(
    highlights: tuple[Highlight, ...], time: float, mode: str
) -> tuple[tuple[Region, tuple[str, ...]], ...]:
    coverage = tuple(
        (region, highlight)
        for highlight in highlights
        for region in highlight.regions(time)
    )
    cuts = sorted({x for region, _ in coverage for x in (region.left, region.right)})
    result = []
    for left, right in zip(cuts, cuts[1:], strict=False):
        active = tuple(
            highlight
            for region, highlight in coverage
            if region.left <= left and region.right >= right
        )
        if not active:
            continue
        if mode == "union":
            if any(
                (h.paint, h.glow, h.material)
                != (active[0].paint, active[0].glow, active[0].material) for h in active
            ):
                raise ValueError(
                    "union highlights require identical appearance at overlaps"
                )
            chosen = (active[0].id,)
        elif mode == "priority":
            top = max(h.priority for h in active)
            highest = tuple(h for h in active if h.priority == top)
            if any(
                (h.paint, h.glow, h.material)
                != (highest[0].paint, highest[0].glow, highest[0].material)
                for h in highest
            ):
                raise ValueError("conflicting equal-priority highlights")
            chosen = (highest[0].id,)
        else:
            if len({h.priority for h in active}) != len(active):
                raise ValueError(
                    "layered highlights require distinct priorities at overlaps"
                )
            chosen = tuple(h.id for h in sorted(active, key=lambda h: h.priority))
        result.append((Region(left, right), chosen))
    return tuple(result)


@dataclass(frozen=True, kw_only=True)
class _FeatheredSingingClip(RectangleClip):
    """Mix incoming ink into the sung layer behind its moving right edge."""
    width: float
    unsung_fill: Color
    unsung_outline: Color
    unsung_gradient: LinearGradient | None = None
    front_color: Color | None = None


@dataclass(frozen=True)
class _Ownership:
    highlights: tuple[Highlight, ...]
    mode: str
    owner: str | None
    birth: float
    shift: float
    # Map line-space body regions onto this glyph's local coordinates.
    body: Region
    drawing: Region
    glyph_left: float
    scale: float
    local_y: bool = False

    def strip(self, left: float, right: float) -> tuple[float, float, float, float]:
        if self.local_y:
            return -65536, left, 65536, right
        return left, -65536, right, 65536

    @property
    def breakpoints(self) -> tuple[float, ...]:
        return tuple(
            sorted(
                {
                    t + self.shift - self.birth
                    for h in self.highlights
                    for span in h.passes
                    for t in (
                        span.time.start,
                        span.time.end,
                        *(span.time.start + t for t in span.breakpoints),
                    )
                }
            )
        )

    @property
    def max_regions(self) -> int:
        return max(1, 2 * sum(len(h.passes) for h in self.highlights))

    @property
    def clip_regions(self) -> int:
        # Unions of prefixes (or suffixes) and their complements stay contiguous.
        if len(self.highlights) == 1:
            passes = self.highlights[0].passes
            if all(not p.reverse and p.region.left <= self.body.left for p in passes) or all(
                p.reverse and p.region.right >= self.body.right for p in passes
            ):
                return 1
        return self.max_regions + (self.owner is None)

    def local_regions(self, time: float) -> tuple[Region, ...]:
        result = []
        for region, owners in _owners(
            self.highlights, self.birth + time - self.shift, self.mode
        ):
            if self.owner is not None and self.owner not in owners:
                continue
            left, right = (
                max(region.left, self.body.left),
                min(region.right, self.body.right),
            )
            if left >= right:
                continue
            factor = self.drawing.width / self.body.width
            result.append(
                Region(
                    -65536
                    if left == self.body.left
                    else (
                        self.drawing.left
                        + (left - self.body.left) * factor
                        - self.glyph_left
                    )
                    / self.scale,
                    65536
                    if right == self.body.right
                    else (
                        self.drawing.left
                        + (right - self.body.left) * factor
                        - self.glyph_left
                    )
                    / self.scale,
                )
            )
        return union_regions(result)

    def singing_keyframes(self, padding: float, feather: float = 0) -> RectangleKeyframes:
        """Piecewise-linear singing motion with separate decoration shoulders."""
        passes = self.highlights[0].passes
        span = passes[0]
        start = span.time.start + self.shift - self.birth
        end = passes[-1].time.end + self.shift - self.birth
        left = (self.drawing.left - self.glyph_left) / self.scale
        right = (self.drawing.right - self.glyph_left) / self.scale

        origin, finish = (right, left) if span.reverse else (left, right)
        sign = -1 if span.reverse else 1
        def bounds(edge: float) -> tuple[float, float, float, float]:
            return (
                self.strip(edge, 65536)
                if (self.owner is None) != span.reverse
                else self.strip(-65536, edge)
            )

        if start == end:
            return RectangleKeyframes(
                ((start, bounds(origin - sign * padding)), (end, bounds(finish + sign * padding)))
            )
        keys = [(start, bounds(origin + sign * feather / 2))]
        for part in passes:
            _, destination = part._edges(part.region)
            edge = left + (right - left) * (destination - self.body.left) / self.body.width
            t = part.time.end + self.shift - self.birth
            key = (t, bounds(edge + sign * feather / 2))
            # Consecutive zero-length checkpoints collapse into one visible jump.
            if len(keys) >= 2 and keys[-2][0] == t:
                keys[-1] = key
            else:
                keys.append(key)
        approach = max(-self.birth, start - _EDGE_SECONDS)
        approach_keys = ((approach, bounds(origin - sign * padding)),) if approach < start else ()
        return RectangleKeyframes((*approach_keys, *keys,
                                   (end + _EDGE_SECONDS, bounds(finish + sign * padding))))

    def world_regions(self, state: VisualState, time: float) -> tuple[Region, ...]:
        if state.rotation % 360 or state.skew.x or state.scale.x <= 0:
            raise ValueError(
                "coverage highlights require positive horizontal axis-aligned geometry"
            )
        return tuple(
            Region(
                state.position.x + region.left * state.scale.x,
                state.position.x + region.right * state.scale.x,
            )
            for region in self.local_regions(time)
        )

    def rectangle(
        self, index: int, time: float
    ) -> tuple[float, float, float, float] | None:
        regions = self.local_regions(time)
        if self.owner is None:
            # The base paint owns the complement of all highlighted strips.
            edges = (
                -65536,
                *(x for region in regions for x in (region.left, region.right)),
                65536,
            )
            regions = tuple(
                Region(left, right)
                for left, right in zip(edges[::2], edges[1::2], strict=True)
                if left < right
            )
        if index >= len(regions):
            return None
        region = regions[index]
        return self.strip(region.left, region.right)


def _split_glow(
    halo: SceneObject, opposite: Color, opposite_opacity: float, ownership: _Ownership, padding: float,
) -> tuple[SceneObject, ...]:
    """Approximate a blurred color step by its Gaussian integral across the moving front."""
    # The step response of a Gaussian is its cumulative distribution. Scale
    # the radius to the same local coordinates as the existing singing clip.
    sigma = halo.state.blur * _ASS_BLUR_TO_SIGMA / ownership.scale
    reach = 2 * sigma
    keys = ownership.singing_keyframes(padding + reach)
    suffix = (ownership.owner is None) != ownership.highlights[0].passes[0].reverse
    edge = int(ownership.local_y) + (0 if suffix else 2)

    def strip(start: float, end: float | None) -> RectangleClip:
        def bounds(x: float) -> tuple[float, float, float, float]:
            if suffix:
                return ownership.strip(x + start, 65536 if end is None else x + end)
            return ownership.strip(-65536 if end is None else x - end, x - start)

        return RectangleClip(0, 0, 1, 1, space="local", deform=RectangleKeyframes(
            tuple((t, bounds(rect[edge])) for t, rect in keys.keyframes)
        ))

    pieces = [replace(halo, clip=strip(reach, None))]
    count = min(4, max(1, ceil(reach * ownership.scale)))
    gaussian = NormalDist()
    # Equal color increments place narrower strips where the transition is steep.
    step = (gaussian.cdf(2) - 0.5) / count
    a = 0.0
    for i in range(count):
        weight = 0.5 + (i + 0.5) * step
        b = reach if i + 1 == count else sigma * gaussian.inv_cdf(0.5 + (i + 1) * step)
        # Studio blurs premultiplied RGBA. Weight RGB by each side's visible ink.
        own_alpha = weight * halo.state.opacity
        opacity = own_alpha + (1 - weight) * opposite_opacity
        ink = _mix(opposite, halo.state.fill, own_alpha / opacity if opacity else 0)
        pieces.append(replace(halo, id=f"{halo.id}/band:{i}", clip=strip(a, b),
                              state=replace(halo.state, fill=ink, outline=ink, opacity=opacity)))
        a = b
    return tuple(pieces)


@dataclass(frozen=True, kw_only=True)
class LyricHighlights:
    """Build named union/priority/layer highlights with common visual objects.

    Clip mode clips completed drawing layers (including separate static glow).
    Its glow uses ordinary per-layer alpha and is cut after blur. Coverage mode
    assigns fractional material ownership before blur and closes component alpha;
    it rejects intentional layered overlap, which has different compositing.
    Existing masks/materials must be composed explicitly instead of overwritten.
    Ownership reaching a unit's outer edges includes its overhang, outline and
    glow, so a completed full-unit highlight owns the complete drawing. Interior
    region edges remain exact cuts. Clip uses disjoint rectangular strips so
    axis-aligned world-space edges share ASS integer pixel boundaries, avoiding
    antialiased vector-mask seams between translucent layers. Rotated/sheared
    masks still use vector clipping. Clip masks use local ±65536 outer bounds;
    use explicit custom masks for drawings outside that range.
    Glow factories receive the line and target once during construction, allowing
    distinct body/ruby geometry without invoking author selection on each frame.
    """

    highlights: tuple[Highlight, ...] | Callable[[LyricLine], tuple[Highlight, ...]]
    mode: Literal["union", "priority", "layer"] = "union"
    strategy: Literal["clip", "coverage"] = "clip"
    glow: LyricGlow = None
    settings: RasterSettings = RasterSettings()
    base_paint: StatePatch = StatePatch()
    base_material: LyricMaterial = None
    hook_feather: float = 0
    front_color: Color | None = None

    @property
    def _hard_border(self) -> float:
        borders = [_hard_glow_border(self.glow)]
        if not self.base_paint.blur:
            borders.append(self.base_paint.border or 0)
        highlights = self.highlights
        known = (highlights,) if isinstance(highlights, _SingingHighlights) else highlights
        if isinstance(known, tuple):
            for h in known:
                if not h.paint.blur:
                    borders.append(h.paint.border or 0)
                borders.append(_hard_glow_border(h.glow))
        return max(borders)

    @classmethod
    def from_singing(
        cls,
        paint: StatePatch,
        *,
        wipe: bool = True,
        reverse: bool = False,
        ruby_reading_units: bool = False,
        glow: LyricGlow = None,
        base_glow: LyricGlow = None,
        base_paint: StatePatch | None = None,
        base_material: LyricMaterial = None,
        material: LyricMaterial = None,
        strategy: Literal["clip", "coverage"] = "clip",
        hook_feather: float = 0,
        front_color: Color | None = None,
        settings: RasterSettings | None = None,
    ) -> LyricHighlights:
        """Sweep source singing across body/ruby without authoring clip geometry.

        With reverse=True, each timed unit fills from its right edge.
        With wipe=False, each timed unit switches paint at completion.
        Singing progress uses undecorated measured text bounds. For a single
        linear interval in clip mode, outline/glow margins are traversed in
        separate 20 ms shoulders before/after singing, reserved automatically.
        Contiguous timed readings divide their host wipe equally at reading
        checkpoints. With ruby_reading_units=True, visible reading characters instead
        receive equal distances and empty readings hold position. Each reading retains its individual singing interval.
        Known rectangle keyframes allow continuous native ASS lowering. Repeated
        intervals retain the general ownership evaluator; coverage keeps its
        color-before-blur semantics. Source singing clocks never change.
        base_material paints the unsung drawing. material paints the sung drawing, leaving the separate glow
        color intact. It accepts a PaintField or a (line, target) factory called
        once during preparation; use LyricGradient for measured vertical colors.
        Materials require clip strategy. Local gradients currently require a
        positive single singing interval and axis-aligned scale/translation.
        base_paint changes only the unsung drawing; sung layers retain the
        original appearance before applying paint. Use base_paint with opacity=0
        to reveal text instead of recoloring an already visible baseline.
        """
        return cls(
            highlights=_SingingHighlights(paint, glow, material, wipe, reverse, ruby_reading_units),
            glow=base_glow,
            base_material=base_material,
            hook_feather=hook_feather,
            front_color=front_color,
            strategy=strategy,
            settings=RasterSettings() if settings is None else settings,
            base_paint=StatePatch() if base_paint is None else base_paint,
        )

    def __post_init__(self) -> None:
        finite(self.hook_feather)
        if self.hook_feather < 0:
            raise ValueError("hook feather must be nonnegative")
        if self.base_paint.channels - {"fill", "outline", "opacity", "border", "blur", "shadow"}:
            raise ValueError("highlight base paint cannot change geometry")
        if self.mode not in ("union", "priority", "layer") or self.strategy not in (
            "clip",
            "coverage",
        ):
            raise ValueError("invalid highlight mode/strategy")
        if self.mode == "layer" and self.strategy == "coverage":
            raise ValueError(
                "layered highlights need separate visual components, not coverage union"
            )

    def __call__(self, line: LyricLine) -> LyricLine:
        """Return decorated visuals, reserving each target's shifted pass intervals.

        Pass times use original source seconds. A copied target's delay shifts
        both rendering and required_display; source singing spans stay unchanged.
        """
        highlights = (
            self.highlights
            if isinstance(self.highlights, tuple)
            else self.highlights(line)
        )
        if len({h.id for h in highlights}) != len(highlights):
            raise ValueError("duplicate highlight identities")
        if any(h.unit >= len(line.layout.lyrics.units) for h in highlights):
            raise ValueError("highlight unit is outside lyrics")
        automatic = isinstance(self.highlights, _SingingHighlights)
        drawings = tuple(line._glyph_regions(automatic=automatic))

        def shoulder(highlight: Highlight) -> float:
            return (
                _EDGE_SECONDS
                if automatic
                and self.strategy == "clip"
                and len(highlight.passes) == 1
                and highlight.passes[0].time.duration > 0
                else 0
            )

        required = tuple(
            dict.fromkeys(
                TimeSpan(
                    max(0, span.time.start + target.delay - shoulder(highlight)),
                    span.time.end + target.delay + shoulder(highlight),
                )
                for target, _, unit, _ in drawings
                for highlight in highlights
                if highlight.unit == unit
                for span in highlight.passes
                if span.time.duration > 0
            )
        )
        if required:
            # Match the same target clock used by the rendering ownership below.
            # Copies shift visuals while retaining original source pass times.
            start = min(line.lifetime.start, *(span.start for span in required))
            end = max(line.lifetime.end, *(span.end for span in required))
            line = line.with_display(replace(line.lifetime, start=start, end=end))
            line = replace(line, required_display=(*line.required_display, *required))
        if self.strategy == "clip" and any(
            isinstance(glow, GlowFunction)
            for glow in (self.glow, *(h.glow for h in highlights))
        ):
            raise ValueError("dynamic glow requires coverage strategy")
        if line.coverage is not None:
            raise ValueError("compose existing coverage settings explicitly")
        replacements: dict[str, tuple[SceneObject, ...]] = {}
        aliases: dict[str, tuple[str, ...]] = {}
        partitions: dict[str, CoveragePartition] = {}
        glows: dict[str, Glow | GlowFunction] = {}
        components: list[str] = []
        nodes: dict[str, SceneObject] = {}

        def collect(node: SceneObject) -> None:
            nodes[node.id] = node
            if isinstance(node, ObjectGroup):
                for child in node.children:
                    collect(child)

        collect(line)

        def bind(
            target: LyricTarget, character: PositionedText, unit: int, box: Box
        ) -> None:
            chosen = tuple(h for h in highlights if h.unit == unit)
            if not chosen:
                return
            if isinstance(self.highlights, _SingingHighlights):
                chosen = tuple(self.highlights.for_target(h, target, character) for h in chosen)
            chosen = tuple(
                replace(
                    highlight,
                    glow=_resolve_glow(highlight.glow, line, target),
                    material=_resolve_material(highlight.material, line, target, character),
                )
                for highlight in chosen
            )
            before_material = _resolve_material(self.base_material, line, target, character)
            if self.strategy == "coverage" and (before_material is not None or any(h.material is not None for h in chosen)):
                raise ValueError("highlight materials require clip strategy")
            base_glow = _resolve_glow(self.glow, line, target)
            if self.strategy == "clip" and any(
                isinstance(glow, GlowFunction)
                for glow in (base_glow, *(h.glow for h in chosen))
            ):
                raise ValueError("dynamic glow requires coverage strategy")
            node = nodes[target.node_id]
            if node.clip is not None or node.material is not None or target.aliases:
                raise ValueError(
                    f"{node.id}: compose existing masks/materials explicitly"
                )
            source = line.layout.lyrics.units[unit]
            body = line.layout.body.range_bounds(source.start, source.end)
            vertical = automatic and line.layout._vertical
            body_axis, draw_axis = _sweep_axis(body, vertical), _sweep_axis(box, vertical)
            if not body_axis.width or not draw_axis.width:
                return
            scale = character.layout_scale
            assert scale is not None
            if vertical and self.strategy == "coverage":
                raise ValueError("vertical singing requires clip strategy")
            local_y = vertical and character.object.state.rotation == 0
            pen = character.object.state.position
            base = _Ownership(
                chosen,
                self.mode,
                None,
                node.time_origin,
                target.delay,
                body_axis, draw_axis,
                pen.y if vertical else pen.x,
                scale.y if local_y else scale.x,
                local_y,
            )
            if any(
                t < -node.time_origin or t > node.lifetime.end - node.time_origin
                for t in base.breakpoints
            ):
                raise ValueError(f"{node.id}: highlight timing lies outside display")
            native_singing = (
                automatic
                and len(chosen) == 1
                and chosen[0].passes[-1].round == 0
                and chosen[0].passes[-1].time.end > chosen[0].passes[0].time.start
            )
            # One shared spatial margin keeps body/glow ownership disjoint.
            states = (self.base_paint.interpolate(node.state, 1), *(h.paint.interpolate(node.state, 1) for h in chosen))
            sung_glow = chosen[0].glow
            before_alpha = states[0].opacity * base_glow.opacity if isinstance(base_glow, Glow) else 0
            after_alpha = states[1].opacity * sung_glow.opacity if isinstance(sung_glow, Glow) else 0
            soften_glow = (
                native_singing and isinstance(base_glow, Glow) and isinstance(sung_glow, Glow)
                and base_glow.blur == sung_glow.blur > 0 and base_glow.border == sung_glow.border
                and (before_alpha != after_alpha or (before_alpha > 0 and base_glow.color != sung_glow.color))
            )
            padding = (
                max(
                    *(
                        state.border + 4 * state.blur + abs(state.shadow.x) + 4
                        for state in states
                    ),
                    *(
                        glow.border + 4 * glow.blur + 4
                        for glow in (base_glow, *(h.glow for h in chosen))
                        if isinstance(glow, Glow)
                    ),
                )
                / scale.x
            )
            pieces: list[SceneObject] = []
            for highlight in (None, *sorted(chosen, key=lambda h: h.priority)):
                identity = (
                    node.id
                    if highlight is None
                    else f"{node.id}/highlight:{highlight.id}"
                )
                ownership = replace(
                    base, owner=None if highlight is None else highlight.id
                )
                piece = node.copy(id=identity)
                if highlight is None:
                    piece = replace(
                        piece, state=self.base_paint.interpolate(piece.state, 1), material=before_material,
                    )
                else:
                    material = highlight.material
                    assert not callable(material) and not isinstance(material, Mapping)
                    piece = replace(
                        piece,
                        state=highlight.paint.interpolate(piece.state, 1),
                        material=material,
                    )
                if self.strategy == "clip":
                    feather = (
                        self.hook_feather / scale.x
                        if native_singing and not vertical
                        else 0
                    )
                    drawings = tuple(
                        replace(
                            piece.copy(
                                id=identity
                                if index == 0
                                else f"{identity}/region:{index}"
                            ),
                            clip=RectangleClip(
                                0,
                                0,
                                1,
                                1,
                                space="local",
                                deform=(
                                    ownership.singing_keyframes(padding + feather, feather)
                                    if native_singing
                                    else RectangleFunction(
                                        partial(ownership.rectangle, index),
                                        base.breakpoints,
                                    )
                                ),
                            ),
                        )
                        for index in range(1 if native_singing else ownership.clip_regions)
                    )
                else:
                    partitions[identity] = CoveragePartition(
                        ownership.world_regions,
                        max_regions=base.max_regions,
                        inside=highlight is not None,
                        breakpoints=base.breakpoints,
                    )
                    glow = base_glow if highlight is None else highlight.glow
                    if glow is not None:
                        assert isinstance(glow, (Glow, GlowFunction))
                        glows[identity] = glow
                    drawings = (piece,)
                for piece in drawings:
                    plain_clip = piece.clip
                    if (vertical and target.role == "character" and native_singing
                            and len(chosen[0].passes) == 1 and not chosen[0].passes[0].reverse
                            and isinstance(plain_clip, RectangleClip)):
                        time = chosen[0].passes[0].time
                        plain_clip = _CellWipeClip(
                            **vars(plain_clip), start=time.start + target.delay - node.time_origin,
                            end=time.end + target.delay - node.time_origin,
                        )
                        piece = replace(piece, clip=plain_clip)
                    if (
                        self.strategy == "clip"
                        and native_singing
                        and highlight is not None
                        and self.hook_feather
                        and not vertical
                        and isinstance(plain_clip, RectangleClip)
                    ):
                        unsung = self.base_paint.interpolate(node.state, 1)
                        piece = replace(
                            piece,
                            clip=_FeatheredSingingClip(
                                plain_clip.left,
                                plain_clip.top,
                                plain_clip.right,
                                plain_clip.bottom,
                                space=plain_clip.space,
                                deform=plain_clip.deform,
                                width=self.hook_feather / scale.x,
                                unsung_fill=unsung.fill,
                                unsung_outline=unsung.outline,
                                unsung_gradient=before_material if isinstance(before_material, LinearGradient) else None,
                                front_color=self.front_color,
                            ),
                        )
                    pieces.append(piece)
                    glow = base_glow if highlight is None else highlight.glow
                    if self.strategy == "clip" and isinstance(glow, Glow):
                        if any(
                            clip.animation.channels
                            & frozenset(("fill", "outline", "border", "blur", "shadow"))
                            for clip in piece.animations
                        ):
                            raise ValueError(
                                "compose existing paint animations with glow explicitly"
                            )
                        halo = piece.copy(id=f"{piece.id}/glow")
                        halo = replace(
                            halo,
                            clip=replace(
                                piece.clip,
                                unsung_fill=base_glow.color,
                                unsung_outline=base_glow.color,
                                unsung_gradient=None,
                                front_color=None,
                            )
                            if isinstance(piece.clip, _FeatheredSingingClip)
                            and isinstance(base_glow, Glow)
                            else plain_clip,
                            material=None,
                            layer=piece.layer - 1,
                            state=replace(
                                piece.state,
                                fill=glow.color,
                                outline=glow.color,
                                border=glow.border,
                                blur=glow.blur,
                                opacity=piece.state.opacity * glow.opacity,
                                shadow=Vec2(),
                            ),
                        )
                        if soften_glow:
                            other = sung_glow if highlight is None else base_glow
                            assert isinstance(other, Glow)
                            other_alpha = after_alpha if highlight is None else before_alpha
                            pieces.extend(_split_glow(halo, other.color, other_alpha, ownership, padding))
                        else:
                            pieces.append(halo)
            aliases[node.id] = tuple(piece.id for piece in pieces[1:])
            if self.strategy == "coverage":
                component = ObjectGroup(
                    id=f"{node.id}/material",
                    lifetime=node.lifetime,
                    children=tuple(pieces),
                    origin=node.origin,
                )
                components.append(component.id)
                replacements[node.id] = (component,)
            else:
                replacements[node.id] = tuple(pieces)

        for drawing in drawings:
            bind(*drawing)

        def apply(node: SceneObject) -> SceneObject:
            if isinstance(node, ObjectGroup):
                return replace(
                    node,
                    children=tuple(
                        piece
                        for child in node.children
                        for piece in replacements.get(child.id, (apply(child),))
                    ),
                )
            return node

        result = apply(line)
        assert isinstance(result, LyricLine)
        return replace(
            result,
            targets=tuple(
                replace(target, aliases=aliases.get(target.node_id, target.aliases))
                for target in line.targets
            ),
            coverage=Coverage(
                components=tuple(components),
                partitions=partitions,
                glows=glows,
                settings=self.settings,
            )
            if self.strategy == "coverage"
            else None,
        )


@dataclass(frozen=True, kw_only=True)
class HighlightArrival:
    """Bind common animations to measured character crossings before allocation.

    Use as LyricRule.anchor. first selects the earliest highlight per repeat round;
    each keeps every highlight, and names restricts either selection explicitly.
    Thresholds use original measured geometry, independent of animation and paint
    priority. The interval length is full character traversal. A partial traversal
    requires duration here; LyricRule.duration may further override that length.
    Nonlinear passes require a declared inverse_rate. No runtime state is retained.
    """

    highlights: tuple[Highlight, ...] | Callable[[LyricLine], tuple[Highlight, ...]]
    threshold: Literal["enter", "center", "complete"] = "enter"
    selection: Literal["first", "each"] = "first"
    names: frozenset[str] = frozenset()
    retrigger: bool = True
    duration: float | None = None

    def __post_init__(self) -> None:
        if self.threshold not in ("enter", "center", "complete"):
            raise ValueError("invalid arrival threshold")
        if self.selection not in ("first", "each"):
            raise ValueError("invalid arrival selection")
        if self.duration is not None:
            finite(self.duration)
            if self.duration <= 0:
                raise ValueError("arrival duration must be positive")

    def __call__(self, line: LyricLine, target: LyricTarget) -> tuple[TimeSpan, ...]:
        """Resolve this target's selected crossings and durations in absolute seconds."""
        if target.role not in ("character", "ruby"):
            raise ValueError("highlight arrival requires a character or ruby target")
        # Semantic targets and measured glyphs retain their order across visual copies.
        if target.role == "character":
            pairs = tuple(
                zip(line.query("character"), line.layout.body.characters, strict=True)
            )
            character = next(c for t, c in pairs if t.id == target.id)
            unit_index = next(
                i
                for i, unit in enumerate(line.layout.lyrics.units)
                if unit.start <= character.start and character.end <= unit.end
            )
            unit = line.layout.lyrics.units[unit_index]
            box = line.layout.body.range_bounds(unit.start, unit.end)
            siblings = tuple(
                c
                for c in line.layout.body.characters
                if unit.start <= c.start and c.end <= unit.end
            )
            parent = line.layout.body
            drawing = box
        else:
            readings = tuple(
                (c, ruby) for ruby in line.layout.ruby for c in ruby.layout.characters
            )
            character, ruby = next(
                pair
                for t, pair in zip(line.query("ruby"), readings, strict=True)
                if t.id == target.id
            )
            unit_index = ruby.unit_index
            unit = line.layout.lyrics.units[unit_index]
            box = line.layout.body.range_bounds(unit.start, unit.end)
            siblings = (character,) if isinstance(self.highlights, _SingingHighlights) else ruby.layout.characters
            parent = ruby.layout
            drawing = ruby.layout.bounds
        if not drawing.width or not box.width:
            return ()
        start_offset, end_offset = siblings[0].start, siblings[-1].end
        if parent._right_to_left:
            siblings = tuple(reversed(siblings))
        index = siblings.index(character)
        left = drawing.left if index == 0 else character.bounds.left
        right = (
            siblings[index + 1].bounds.left
            if index + 1 < len(siblings)
            else drawing.right
        )
        if isinstance(self.highlights, _SingingHighlights):
            drawing = parent._sweep_bounds(
                start_offset, end_offset, character
            )
            right = (
                siblings[index + 1].bounds.left
                - siblings[index + 1]._gap_shift
                + character._gap_shift
                if index + 1 < len(siblings)
                else drawing.right
            )
            if not drawing.width:
                return ()
            left = min(drawing.right, max(drawing.left, left))
            right = min(drawing.right, max(drawing.left, right))
        if right < left:
            raise ValueError("non-monotone character positions cannot define arrival")
        region = Region(
            box.left + (left - drawing.left) * box.width / drawing.width,
            box.left + (right - drawing.left) * box.width / drawing.width,
        )
        highlights = (
            self.highlights
            if isinstance(self.highlights, tuple)
            else self.highlights(line)
        )
        if len({h.id for h in highlights}) != len(highlights):
            raise ValueError("duplicate highlight identities")
        missing = self.names - {h.id for h in highlights}
        if missing:
            raise ValueError(f"unknown arrival highlights: {sorted(missing)}")
        candidates: list[tuple[float, str, int, float]] = []

        def arrivals(
            passes: tuple[HighlightPass, ...], threshold: str
        ) -> tuple[float, ...]:
            times = []
            for span in passes:
                entry, exit = span._edges(region)
                start, end = span._edges(span.region)
                point = {"enter": entry, "center": region.center, "complete": exit}[threshold]
                if (threshold == "enter" and point == end) or (threshold == "complete" and point == start):
                    continue
                time = span.arrival(point)
                if time is not None:
                    times.append(time)
            return tuple(times)

        for highlight in highlights:
            if highlight.unit != unit_index or (
                self.names and highlight.id not in self.names
            ):
                continue
            if isinstance(self.highlights, _SingingHighlights):
                highlight = self.highlights.for_target(highlight, target, character)
            for round_id in sorted({span.round for span in highlight.passes}):
                passes = tuple(
                    span for span in highlight.passes if span.round == round_id
                )
                times = arrivals(passes, self.threshold)
                if not times:
                    continue
                enters = arrivals(passes, "enter")
                exits = arrivals(passes, "complete")
                duration = self.duration
                if duration is None:
                    if not enters or not exits:
                        raise ValueError(
                            "incomplete character traversal; specify arrival duration"
                        )
                    duration = min(exits) - min(enters)
                candidates.append((min(times), highlight.id, round_id, duration))
        seen: set[tuple[int | None, str | None]] = set()
        result: list[TimeSpan] = []
        for start, identity, round_id, duration in sorted(candidates):
            key = (
                round_id if self.retrigger else None,
                identity if self.selection == "each" else None,
            )
            if key in seen:
                continue
            seen.add(key)
            if duration > 0:
                result.append(
                    TimeSpan(start + target.delay, start + target.delay + duration)
                )
        return tuple(result)
