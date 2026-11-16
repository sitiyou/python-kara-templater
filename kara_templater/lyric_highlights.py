"""Named highlight ownership projected into common masks or coverage partitions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from functools import partial
from typing import Literal

from .composition import Glow
from .coverage_animation import Coverage, CoveragePartition, GlowFunction
from .geometry import Vec2, finite
from .lyric_line import LyricLine, LyricTarget
from .model import Box
from .raster_settings import RasterSettings
from .scene import ObjectGroup, RectangleClip, RectangleFunction, SceneObject
from .scene_animation import StatePatch, TimeSpan, VisualState, linear_rate
from .scene_text import PositionedText
from .timeline import Region, union_regions

type LyricGlow = (
    Glow
    | GlowFunction
    | Callable[[LyricLine, LyricTarget], Glow | GlowFunction | None]
    | None
)


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
    """One left-to-right pass, with absolute seconds and measured line-local x.

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
        if self.time.duration == 0:
            return self.region.left if time < self.time.start else self.region.right
        value = (
            0
            if time <= self.time.start
            else 1
            if time >= self.time.end
            else self.rate((time - self.time.start) / self.time.duration)
        )
        finite(value)
        return self.region.left + self.region.width * max(0, min(1, value))

    def arrival(self, x: float) -> float | None:
        """Return an exact crossing clock using a declared monotone inverse.

        Arbitrary forward callbacks cannot be reliably inverted by sampling.
        A nonlinear rate therefore needs inverse_rate for arrival bindings.
        """
        if not self.region.left <= x <= self.region.right or not self.region.width:
            return None
        if self.time.duration == 0:
            return self.time.start
        progress = (x - self.region.left) / self.region.width
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
            Region(span.region.left, span.front(time)) for span in started
        )


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
                (h.paint, h.glow) != (active[0].paint, active[0].glow) for h in active
            ):
                raise ValueError(
                    "union highlights require identical appearance at overlaps"
                )
            chosen = (active[0].id,)
        elif mode == "priority":
            top = max(h.priority for h in active)
            highest = tuple(h for h in active if h.priority == top)
            if any(
                (h.paint, h.glow) != (highest[0].paint, highest[0].glow)
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
        # A single front starting at the body's left edge always owns a prefix;
        # its complement is one suffix, including reset and hidden intervals.
        if len(self.highlights) == 1 and all(
            span.region.left <= self.body.left for span in self.highlights[0].passes
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
        return region.left, -65536, region.right, 65536


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

    def __post_init__(self) -> None:
        if self.mode not in ("union", "priority", "layer") or self.strategy not in (
            "clip",
            "coverage",
        ):
            raise ValueError("invalid highlight mode/strategy")
        if self.mode == "layer" and self.strategy == "coverage":
            raise ValueError(
                "layered highlights need separate visual components, not coverage union"
            )

    def apply(self, line: LyricLine) -> LyricLine:
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
        drawings: list[tuple[LyricTarget, PositionedText, int, Box]] = []
        for target, character in zip(
            line.query("character"), line.layout.body.characters, strict=True
        ):
            unit = next(
                i
                for i, unit in enumerate(line.layout.lyrics.units)
                if unit.start <= character.start and character.end <= unit.end
            )
            source = line.layout.lyrics.units[unit]
            drawings.append(
                (
                    target,
                    character,
                    unit,
                    line.layout.body.range_bounds(source.start, source.end),
                )
            )
        readings = tuple(
            (character, ruby)
            for ruby in line.layout.ruby
            for character in ruby.layout.characters
        )
        for target, (character, ruby) in zip(line.query("ruby"), readings, strict=True):
            drawings.append((target, character, ruby.unit_index, ruby.layout.bounds))

        required = tuple(
            dict.fromkeys(
                TimeSpan(span.time.start + target.delay, span.time.end + target.delay)
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
            chosen = tuple(
                replace(highlight, glow=_resolve_glow(highlight.glow, line, target))
                for highlight in chosen
            )
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
            if not body.width or not box.width:
                return
            scale = character.layout_scale
            assert scale is not None
            base = _Ownership(
                chosen,
                self.mode,
                None,
                node.time_origin,
                target.delay,
                Region(body.left, body.right),
                Region(box.left, box.right),
                character.bounds.left,
                scale.x,
            )
            if any(
                t < -node.time_origin or t > node.lifetime.end - node.time_origin
                for t in base.breakpoints
            ):
                raise ValueError(f"{node.id}: highlight timing lies outside display")
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
                if highlight is not None:
                    piece = replace(
                        piece, state=highlight.paint.interpolate(piece.state, 1)
                    )
                if self.strategy == "clip":
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
                                deform=RectangleFunction(
                                    partial(ownership.rectangle, index),
                                    base.breakpoints,
                                ),
                            ),
                        )
                        for index in range(ownership.clip_regions)
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
                        pieces.append(
                            replace(
                                halo,
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
                        )
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
            siblings = ruby.layout.characters
            drawing = ruby.layout.bounds
        if not drawing.width or not box.width:
            return ()
        index = siblings.index(character)
        left = drawing.left if index == 0 else character.bounds.left
        right = (
            siblings[index + 1].bounds.left
            if index + 1 < len(siblings)
            else drawing.right
        )
        if right < left:
            raise ValueError("non-monotone character positions cannot define arrival")
        region = Region(
            box.left + (left - drawing.left) * box.width / drawing.width,
            box.left + (right - drawing.left) * box.width / drawing.width,
        )
        x = {"enter": region.left, "center": region.center, "complete": region.right}[
            self.threshold
        ]
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
            passes: tuple[HighlightPass, ...], point: float, threshold: str
        ) -> tuple[float, ...]:
            return tuple(
                time
                for span in passes
                if not (threshold == "enter" and point == span.region.right)
                and not (threshold == "complete" and point == span.region.left)
                if (time := span.arrival(point)) is not None
            )

        for highlight in highlights:
            if highlight.unit != unit_index or (
                self.names and highlight.id not in self.names
            ):
                continue
            for round_id in sorted({span.round for span in highlight.passes}):
                passes = tuple(
                    span for span in highlight.passes if span.round == round_id
                )
                times = arrivals(passes, x, self.threshold)
                if not times:
                    continue
                enters = arrivals(passes, region.left, "enter")
                exits = arrivals(passes, region.right, "complete")
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
