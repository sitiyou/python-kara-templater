"""Lyric streams bind targets, display and layout into the shared Scene model."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from copy import deepcopy
from dataclasses import dataclass, field, replace
from functools import cache, cached_property
from hashlib import sha256
from urllib.parse import quote

from ._karaoke_motion import RowSlide
from ._source_records import (
    GENERATED_PREFIX,
    SOURCE_PREFIX,
    generated_prefix,
    read_source_marker,
    source_prefix,
    strip_generated_records,
    write_source_marker,
)
from .appearance import _EMPTY_THEME, KaraokeTheme, PaintPair
from .ass import Document, Line, Style
from .composition import Glow
from .cues import (
    CueContent,
    CueContext,
    CueFactory,
    CuePreset,
    _validate_bpm,
    bind_lyric_cues,
)
from .document_lyrics import DocumentLyrics, parse_document_lyrics
from .document_text import DocumentText, _read_document_text, _soft_break
from .geometry import Vec2, finite
from .karaoke_effects import KaraokeEffects
from .lyric_highlights import LyricGradient, LyricHighlights, _style_material
from .lyric_layout import (
    KaraokeRows,
    Layout,
    LayoutContext,
    LayoutLine,
    Placement,
    _RowMetrics,
    validate_placements,
)
from .lyric_line import LyricLine, LyricRule, _LyricBinding
from .lyric_particles import LyricParticles
from .model import Box
from .paint_fields import Extrusion
from .scene import Lifetime, ObjectGroup, Scene, SceneObject
from .scene_animation import (
    ShaderMotion,
    StateAnimation,
    StateFunction,
    TimeSpan,
    Transform,
)
from .scene_lyrics import (
    LyricLayout,
    StudioSpacing,
    VectorGuide,
    layout_lyrics,
)
from .scene_text import DocumentLayout, _union
from .sources import EventOrigin, SourceRef


@dataclass(frozen=True)
class LyricSource:
    """An immutable source view used by Track predicates and metadata functions.

    id identifies source content independently of its track/view. Original
    singing intervals remain in lyrics; display is the original ASS visibility.
    An optional chapter groups consecutive sources. The first selected line of a
    chapter starts a fresh row rotation by default, even without a visible cue.
    """

    id: str
    record_index: int | None
    style: str
    actor: str
    effect: str
    display: Lifetime
    text_data: DocumentText
    projection: DocumentLyrics | None = None
    chapter: str | None = None

    @classmethod
    def from_lyrics(
        cls,
        id: str,
        lyrics: DocumentLyrics,
        *,
        display: Lifetime,
        style: str = "Default",
        actor: str = "",
        effect: str = "",
        chapter: str | None = None,
    ) -> LyricSource:
        """Create a structured source without synthesizing or replacing ASS records.

        The projection retains full-precision singing, appearance runs, ruby and
        cues. Regeneration requires supplying this source again; ASS output does
        not embed Python data or private serialization.
        """
        if not id:
            raise ValueError("structured lyrics need a stable source id")
        return cls(id, None, style, actor, effect, display, lyrics.source, lyrics, chapter)

    @cached_property
    def lyrics(self) -> DocumentLyrics:
        """Project selected lyrics lazily; unselected raw events need no support."""
        return (
            self.projection
            if self.projection is not None
            else parse_document_lyrics(self.text_data, start=self.display.start)
        )

    @property
    def text(self) -> str:
        """Decoded body text, excluding ruby and custom markup."""
        return self.lyrics.body.text


def _all_sources(source: LyricSource) -> bool:
    return True


@dataclass(frozen=True)
class _SourceById:
    """An exact selection the preset can resolve by index."""

    id: str

    def __call__(self, source: LyricSource) -> bool:
        return source.id == self.id


type LyricEffect = LyricRule | Callable[[LyricLine], LyricLine]


@dataclass(frozen=True, kw_only=True)
class Track:
    """An independent lyric stream with selection, placement and composable effects.

    With layout omitted, two bottom rows alternate left and right in the region.
    All times use seconds. preview/tail are desired, reducible display padding;
    automatic tail (None) targets one second after singing, including the exit,
    and prefers at least 0.2 seconds of hold. On a shared row, trim excess preview,
    then hold, then scale display-anchored transitions to fit. An explicit tail
    retains rigid animation durations. Singing and authored cue times stay fixed. The visual
    effects receive the measured, unpositioned line once before allocation.
    extrusion gives body and ruby a common solid side in local script pixels.
    LyricRule entries declare timing; callable entries decorate the line in order.
    Rule factories resolve once before decoration and bind to final target aliases.
    Authored visual intervals join occupancy; rule binding follows allocation.
    min_outline_gap is the minimum script-pixel clearance between hard strokes;
    zero allows touching outlines (the default) and None disables clearance. studio_spacing selects Studio ink-based cells
    for both body and readings. By default KaraokeRows uses Studio cells and
    Layout uses native advances. Horizontal palt selects the font’s proportional
    alternate widths for body and ruby and uses native advances by default. reserved_border declares the outer hard radius
    of custom or shared visual layers. Glow and motion do not reserve space.
    ruby_gap sets the visual gap in script pixels between hard outlines of
    the reading group and its body at rest. Negative values allow overlap.
    vertical stacks cells downward with right-side readings. With no layout override,
    two columns rotate from right to left. Explicit layout allocators place the prepared blocks.
    right_to_left places shaped lyric cells from right to left, including readings.
    reverse_timing assigns the first authored window to the last timed lyric unit
    and reverses the built-in wipe. A predicate selects individual source lines.
    All animation evaluation and output belong to Scene.
    """

    id: str
    source: Callable[[LyricSource], bool] = _all_sources
    layout: Layout | KaraokeRows | None = None
    region: Box | None = None
    preview: float = 5.0
    tail: float | None = None
    effects: tuple[LyricEffect, ...] = ()
    theme: KaraokeTheme = field(default_factory=KaraokeTheme)
    cues: Mapping[str, CuePreset] = field(default_factory=dict)
    guide_symbols: Mapping[str, VectorGuide] = field(default_factory=dict)
    tags: frozenset[str] | Callable[[LyricSource], frozenset[str]] = frozenset()
    styles: tuple[Style, ...] = ()
    references: tuple[LayoutLine, ...] = ()
    min_outline_gap: float | None = 0
    reserved_border: float = 0
    ruby_gap: float = 6
    studio_spacing: bool | StudioSpacing | None = None
    vertical: bool = False
    right_to_left: bool = False
    reverse_timing: bool | Callable[[LyricSource], bool] = False
    palt: bool = False
    extrusion: Extrusion | None = None

    def __post_init__(self) -> None:
        finite(self.preview, self.tail or 0, self.reserved_border, self.min_outline_gap or 0, self.ruby_gap)
        if self.reserved_border < 0 or (
            self.min_outline_gap is not None and self.min_outline_gap < 0
        ):
            raise ValueError("outline clearance must be nonnegative")
        if not self.id:
            raise ValueError("Track needs a stable id")
        if self.preview < 0 or (self.tail is not None and self.tail < 0):
            raise ValueError("preview/tail must be nonnegative seconds")


@dataclass(frozen=True)
class LinePlan:
    """Inspectable source/view association and final layout/animation binding."""

    track_id: str
    source: LyricSource
    input: LayoutLine
    placement: Placement
    line: LyricLine


@dataclass
class LyricScene(Scene):
    """A normal Scene with immutable lyric arrangement snapshots for inspection."""

    plans: tuple[LinePlan, ...] = ()

    @property
    def lines(self) -> tuple[LyricLine, ...]:
        """The bound lyric lines in track/source order."""
        return tuple(plan.line for plan in self.plans)


def _sources(document: Document, owner: str) -> tuple[LyricSource, ...]:
    prefix = source_prefix(owner)
    result: list[LyricSource] = []
    seen: set[str] = set()
    styles = document.styles
    soft_break = _soft_break(document)
    for index, record in enumerate(document.records):
        if not isinstance(record, Line):
            continue
        marked = record.comment and record.effect.startswith(prefix)
        if record.comment and not marked:
            continue
        if record.effect.startswith(GENERATED_PREFIX):
            continue
        if record.effect.startswith(SOURCE_PREFIX) and not marked:
            continue
        # Selection operates on lyric inputs, not untimed template/drawing events.
        text = _read_document_text(document, index, styles, soft_break)
        if not text.timing:
            continue
        if marked:
            identifier, effect = read_source_marker(record.effect, prefix, index)
        else:
            digest = sha256(record.serialize().encode()).hexdigest()[:20]
            identifier, occurrence = f"ass:{digest}", 1
            while identifier in seen:
                identifier = f"ass:{digest}:{occurrence}"
                occurrence += 1
            effect = record.effect
        if identifier in seen:
            raise ValueError(f"record {index}: duplicate lyric source id {identifier}")
        seen.add(identifier)
        result.append(
            LyricSource(
                identifier,
                index,
                record.style,
                record.actor,
                effect,
                Lifetime(record.start_time / 1000, record.end_time / 1000),
                text,
            )
        )
    return tuple(result)


def _retime(layout: LyricLayout, display: Lifetime) -> LyricLayout:
    """Adjust undecorated measured nodes before any animation binding."""

    def text(value: DocumentLayout) -> DocumentLayout:
        return replace(
            value,
            lifetime=display,
            characters=tuple(
                replace(item, object=replace(item.object, lifetime=display))
                for item in value.characters
            ),
        )

    return replace(
        layout,
        body=text(layout.body),
        ruby=tuple(replace(ruby, layout=text(ruby.layout)) for ruby in layout.ruby),
    )


def _visual_spans(line: LyricLine) -> tuple[TimeSpan, ...]:
    """Read authored intervals without invoking frame callbacks."""
    spans = list(line.required_display)

    def collect(node: SceneObject, window: TimeSpan | None = None) -> None:
        if node.id in line._optional_objects:
            return
        # Shared lyric windows are adjusted after allocation. Explicit child
        # windows remain fixed, including restrictions from intermediate groups.
        if node is not line and node.lifetime != line.lifetime:
            start = max(node.lifetime.start, window.start if window else 0)
            end = min(node.lifetime.end, window.end if window else node.lifetime.end)
            window = TimeSpan(start, max(start, end))
        if (
            not isinstance(node, ObjectGroup)
            and window is not None
            and window.duration > 0
        ):
            spans.append(window)
        spans.extend(
            TimeSpan(node.time_origin + clip.start, node.time_origin + clip.end)
            for clip in node.animations
        )
        if isinstance(node, ObjectGroup):
            for child in node.children:
                collect(child, window)

    collect(line)
    return tuple(spans)


def _stamp(
    node: SceneObject, source: str, track: str,
    extrusion: Extrusion | None = None, glyphs: frozenset[str] = frozenset(),
) -> SceneObject:
    previous = node.origin
    origin = EventOrigin(
        (SourceRef(source),)
        if previous is None
        else tuple(replace(ref, item_id=source) for ref in previous.sources),
        "lyric orchestration" if previous is None else previous.effect,
        (track,),
    )
    if isinstance(node, ObjectGroup):
        return replace(
            node,
            origin=origin,
            children=tuple(_stamp(child, source, track, extrusion, glyphs) for child in node.children),
        )
    if extrusion is not None and node.id in glyphs:
        return replace(node, origin=origin, extrusion=extrusion)
    return replace(node, origin=origin)


def _cue_presets(
    presets: Mapping[str, CuePreset], recipe: KaraokeEffects | None, role_style: str | None,
    theme: KaraokeTheme, bpm: float | None,
) -> dict[str, CuePreset]:
    """Measure and bind each cue from the same factory result within one line."""
    result: dict[str, CuePreset] = {}
    for name, preset in presets.items():
        @cache
        def factory(
            context: CueContext,
            *,
            original: CueFactory = preset.factory,
            inherit: bool = preset.colors is None,
        ) -> CueContent:
            if inherit and recipe is not None:
                assert recipe.sung is not None and recipe.unsung is not None
                before, after = context.colors.before, context.colors.after
                colors = PaintPair(
                    replace(before, fill=recipe.unsung, outline=recipe.unsung_outline or before.outline,
                                secondary_outline=recipe.secondary_outline,
                                glow=recipe.base_glow if isinstance(recipe.base_glow, Glow) else None),
                    replace(after, fill=recipe.sung, outline=recipe.sung_outline or after.outline,
                                secondary_outline=recipe.sung_secondary_outline or recipe.secondary_outline,
                                glow=recipe.glow if isinstance(recipe.glow, Glow) else None),
                )
                material = _style_material(recipe.material, role_style)
                gradient = material if isinstance(material, LyricGradient) else None
                base = _style_material(recipe.base_material, role_style)
                context = replace(context, colors=colors, gradient=gradient,
                                  base_gradient=base if isinstance(base, LyricGradient) else None)
            elif inherit:
                before, after = context.colors.before, context.colors.after
                context = replace(context, colors=PaintPair(
                    replace(before, fill=theme.unsung or before.fill, outline=theme.unsung_outline or before.outline),
                    replace(after, fill=theme.sung or after.fill, outline=theme.sung_outline or after.outline),
                ))
            if recipe is not None and recipe.singing.startswith("zoom_pulse"):
                context = replace(context, zoom_pulse_curve_level=recipe.zoom_pulse_curve_level)
            return original(context)

        lead, duration = preset.resolve_timing(bpm=bpm)
        result[name] = replace(preset, factory=factory, lead=lead, duration=duration)
    return result


def _animation_prefix(animation: StateAnimation, fraction: float) -> StateAnimation:
    from ._karaoke_motion import ZoomScale

    if isinstance(animation, Transform) and isinstance(animation.scale, ZoomScale):
        return replace(animation, scale=replace(animation.scale, duration=animation.scale.duration * fraction))
    if isinstance(animation, ShaderMotion):
        return replace(animation, progress_scale=animation.progress_scale * fraction)
    return StateFunction(lambda base, t: animation.sample(base, t * fraction), animation.channels)


def _padding(bindings: tuple[_LyricBinding, ...]) -> tuple[float, float]:
    entrance = exit = 0.0
    for binding in bindings:
        if binding.target.role == "cue":
            continue
        if binding.at == "enter":
            if binding.offset < 0:
                raise ValueError("enter animation offset cannot precede display start")
            entrance = max(entrance, binding.offset + binding.duration)
        elif binding.at == "exit":
            if binding.offset > 0:
                raise ValueError("exit animation offset cannot follow display end")
            exit = max(exit, binding.duration - binding.offset)
    return entrance, exit


def _reserved_animations(bindings: tuple[_LyricBinding, ...]) -> Lifetime | None:
    intervals = tuple(
        (binding.at + binding.offset, binding.at + binding.offset + binding.duration)
        for binding in bindings
        if isinstance(binding.at, (int, float))
    )
    if not intervals:
        return None
    return Lifetime(
        min(start for start, _ in intervals), max(end for _, end in intervals)
    )


def _row_metrics(layout: LyricLayout, bounds: Box, border: float, secondary_width: float) -> _RowMetrics | None:
    body = layout.body
    if not body.characters:
        return None
    glyph = body.characters[0]
    baseline = glyph.bounds.top + (glyph.baseline or 0) * glyph.object.state.scale.y
    pad = max(border, *(c.object.state.border + secondary_width for c in body.characters))
    body_top = body.bounds.top - pad
    top = min(body_top, bounds.top)
    for ruby in layout.ruby:
        for reading in ruby.layout.characters:
            top = min(top, reading.bounds.top - max(border, reading.object.state.border + secondary_width))
    bottom = max(body.bounds.top + body.bounds.height + pad, bounds.top + bounds.height)
    return _RowMetrics(baseline, baseline - body_top, bottom - baseline, body_top - top)


def _preview_slice(
    sources: list[LyricSource], track: Track, layout: Layout | KaraokeRows, window: Lifetime,
) -> slice:
    """Keep strict row rotation, co-visible row heights and adjacent handoffs."""
    if (type(layout) is not Layout or layout.policy != "strict" or layout.reset_after is not None
            or track.tail is not None or track.cues or track.guide_symbols or track.vertical
            or track.reverse_timing or not isinstance(track.tags, frozenset) or len(track.effects) > 1):
        return slice(0, None)
    entry = exit = release = 0.0
    for effect in track.effects:
        padding = effect._preview_padding() if type(effect) is KaraokeEffects else None
        if padding is None:
            return slice(0, None)
        entry, exit, release = padding
    lanes: dict[int, list[int]] = {}
    windows: list[tuple[float, float]] = []
    singing: list[tuple[float, float]] = []
    styles: set[str] = set()
    row = 0
    for i, source in enumerate(sources):
        body = source.lyrics.body
        if source.record_index is not None or body.cues or not body.text.strip():
            return slice(0, None)
        styles.update(run.appearance.style for run in body.runs)
        # With automatic row gaps the global maximum body font size affects
        # even windows that contain just one line. Keep the full batch if it varies.
        if layout.gap is None and len(styles) > 1:
            return slice(0, None)
        spans = [seg.singing for unit in source.lyrics.units for seg in unit.segments]
        if not spans:
            return slice(0, None)
        lo, hi = min(s.start for s in spans), max(s.end for s in spans)
        singing.append((lo, hi))
        windows.append((min(source.display.start - track.preview, lo - max(track.preview, entry)),
                        max(source.display.end, hi + 1) + exit + release + entry))
        if layout.reset_on_lead and source.chapter is not None and (i == 0 or source.chapter != sources[i - 1].chapter):
            row = 0
        lanes.setdefault(row, []).append(i)
        row = (row + 1) % layout.rows
    # Same-row neighbors must retain their singing intervals. This tightens
    # the visibility bounds even before shaping or exact adaptive handoff.
    for indices in lanes.values():
        for prev, nxt in zip(indices, indices[1:], strict=False):
            windows[prev] = (windows[prev][0], min(windows[prev][1], singing[nxt][0]))
            windows[nxt] = (max(windows[nxt][0], singing[prev][1]), windows[nxt][1])
    needed = {i for i, (a, b) in enumerate(windows) if a < window.end and window.start < b}
    if not needed:
        return slice(0, 0)
    if layout.gap is None:
        # A row's vertical offset depends only on overlapping lower-numbered
        # rows. Walk those dependencies in descending row order.
        for row in sorted(lanes, reverse=True):
            peers = [windows[i] for i in lanes[row] if i in needed]
            for lower, indices in lanes.items():
                if lower < row:
                    needed.update(i for i in indices if any(
                        windows[i][0] < b and a < windows[i][1] for a, b in peers
                    ))
    neighbors = set(needed)
    for indices in lanes.values():
        for j, i in enumerate(indices):
            if i in needed:
                neighbors.update(indices[max(0, j - 1):j + 2])
    earliest = min(neighbors)
    first = max(i for i in lanes[0] if i <= earliest)
    return slice(first, max(neighbors) + 1)


def prepare_tracks(
    document: Document,
    *,
    tracks: tuple[Track, ...],
    owner: str = "karaoke",
    inputs: tuple[LyricSource, ...] = (),
    theme: KaraokeTheme = _EMPTY_THEME,
    bpm: float | None = None,
    preview_interval: tuple[float, float] | None = None,
) -> LyricScene:
    """Measure, allocate and bind independent tracks into one ordinary Scene.

    Same-source views are allowed and have distinct visual identities. Original
    records are retained once as owner-marked comments. Re-preparing owned output
    removes only that owner's generated events and regenerates from its sources.
    theme supplies shared catalog and cue colors. Track roles override only their
    declared channels, and explicit effect colors take precedence.
    bpm supplies a fixed song tempo for automatic cue timing.
    inputs adds structured LyricSource values alongside parsed ASS sources.
    These have no ASS record ownership and must be supplied again to regenerate
    them. The caller's Document and reusable declarations are not mutated.
    preview_interval limits the returned plans and objects to lines or independent
    cues visible in this half-open interval of absolute seconds. Strict rows with bounded catalog effects retain neighboring handoffs
    and overlapping rows. Other allocators use the full batch. Omit it when later template code needs off-window objects
    or references them from visible objects.
    """
    return _prepare_tracks(
        document, build_tracks=lambda _document, _sources: tracks,
        owner=owner, inputs=inputs, theme=theme,
        bpm=bpm, preview_interval=preview_interval,
    )


def _prepare_tracks(
    document: Document,
    *,
    build_tracks: Callable[[Document, tuple[LyricSource, ...]], tuple[Track, ...]],
    owner: str,
    inputs: tuple[LyricSource, ...] = (),
    theme: KaraokeTheme = _EMPTY_THEME,
    bpm: float | None = None,
    preview_interval: tuple[float, float] | None = None,
) -> LyricScene:
    window = Lifetime(*preview_interval) if preview_interval is not None else None
    _validate_bpm(bpm)
    if not owner:
        raise ValueError("lyric scene owner cannot be empty")
    source_document = deepcopy(document)
    source_document.records = strip_generated_records(
        source_document.records, generated_prefix(owner), set()
    )
    if any(source.record_index is not None for source in inputs):
        raise ValueError(
            "explicit inputs must be structured sources without ASS record ownership"
        )
    sources = (*_sources(source_document, owner), *deepcopy(inputs))
    tracks = build_tracks(source_document, sources)
    if len({track.id for track in tracks}) != len(tracks):
        raise ValueError("duplicate Track ids")
    source_by_id = {source.id: source for source in sources}
    if len(source_by_id) != len(sources):
        raise ValueError("duplicate lyric source ids")
    scene = LyricScene(source_document, owner=owner)
    plans: list[LinePlan] = []
    source_styles = tuple(source_document.styles.values())
    for declaration in tracks:
        track = deepcopy(declaration)
        palette = theme.overlay(track.theme)
        track = replace(track, effects=tuple(
            effect.with_theme(palette) if isinstance(effect, KaraokeEffects) else effect
            for effect in track.effects
        ))
        layout = KaraokeRows() if track.layout is None else track.layout
        horizontal_rtl = track.right_to_left and not track.vertical
        studio_spacing = (isinstance(layout, KaraokeRows) and not track.palt if track.studio_spacing is None
                          else track.studio_spacing)
        candidates: Iterable[LyricSource]
        if isinstance(track.source, _SourceById):
            source = source_by_id.get(track.source.id)
            candidates = () if source is None else (source,)
        else:
            candidates = (source for source in sources if track.source(source))
        selected = sorted(
            candidates,
            key=lambda source: min(
                (
                    segment.singing.start
                    for unit in source.lyrics.units
                    for segment in unit.segments
                ),
                default=source.display.start,
            ),
        )
        selection = _preview_slice(selected, track, layout, window) if window else slice(0, None)
        original = selected
        selected = selected[selection]
        view = Document([*source_styles, *track.styles], source_document.meta)
        allocation_inputs: list[LayoutLine] = []
        prepared: dict[str, LyricLine] = {}
        row_cues: dict[str, Vec2] = {}
        resolved: dict[str, tuple[_LyricBinding, ...]] = {}
        border = max(
            [track.reserved_border]
            + [
                effect._hard_border
                for effect in track.effects
                if isinstance(effect, (LyricHighlights, KaraokeEffects))
            ]
        )
        secondary_width = max((e._secondary_width for e in track.effects
                               if isinstance(e, (LyricHighlights, KaraokeEffects))), default=0)
        recipe = next((e for e in track.effects if isinstance(e, KaraokeEffects)), None)
        for track_index, source in enumerate(selected, start=selection.start):
            identity = f"track:{quote(track.id, safe='')}/{source.id}"
            reverse = track.reverse_timing(source) if callable(track.reverse_timing) else track.reverse_timing
            lyrics = source.lyrics._reverse_timing() if reverse else source.lyrics
            spans = tuple(
                segment.singing
                for unit in lyrics.units
                for segment in unit.segments
            )
            if not spans:
                raise ValueError(f"{source.id}: lyric source has no singing intervals")
            start, end = (
                min(span.start for span in spans),
                max(span.end for span in spans),
            )
            singing = TimeSpan(start, end)
            tags = (
                track.tags if isinstance(track.tags, frozenset) else track.tags(source)
            )
            minimum_hold = 0.2 if track.tail is None else 0.0
            display = Lifetime(
                max(
                    0,
                    min(source.display.start, singing.start)
                    - track.preview,
                ),
                max(source.display.end, singing.end + 1.0) if track.tail is None
                else max(source.display.end, singing.end) + track.tail,
            )
            bare = layout_lyrics(
                view,
                lyrics,
                id=identity,
                display=display,
                min_outline_gap=track.min_outline_gap,
                reserved_border=border, secondary_width=secondary_width,
                ruby_gap=track.ruby_gap,
                studio_spacing=studio_spacing,
                palt=track.palt,
                guide_symbols=track.guide_symbols,
                right_to_left=horizontal_rtl, vertical=track.vertical,
            )
            role_style = next((g.source_style for g in bare.body.characters if g.object.text.strip()), None)
            local_presets = _cue_presets(track.cues, recipe, role_style, palette, bpm)
            cued = bind_lyric_cues(bare, local_presets, bpm=bpm)
            line = LyricLine.from_layout(
                cued.lyrics, tags=tags, inline=cued.inline, independent=cued.independent,
                track_index=track_index,
            )
            bindings = line._resolve(
                tuple(
                    effect for effect in track.effects if isinstance(effect, LyricRule)
                )
            )
            resolved[identity] = bindings
            entrance, exit = _padding(bindings)
            display = Lifetime(
                max(0, min(display.start, singing.start - entrance)),
                max(display.end, singing.end + (minimum_hold + exit)),
            )
            reserved = _reserved_animations(bindings)
            timed_cues = [cue for cue in cued.cues if cue.marker.placement == "inline" or cue.preset.line_edge]
            if timed_cues:
                reserved = Lifetime(
                    min(
                        *(cue.lifetime.start for cue in timed_cues),
                        reserved.start if reserved else singing.start,
                    ),
                    max(
                        *(cue.lifetime.end for cue in timed_cues),
                        reserved.end if reserved else singing.end,
                    ),
                )
            if reserved is not None:
                display = Lifetime(
                    min(display.start, reserved.start), max(display.end, reserved.end)
                )
            if display != bare.body.lifetime:
                cued = bind_lyric_cues(_retime(bare, display), local_presets, bpm=bpm)
                line = LyricLine.from_layout(
                    cued.lyrics, tags=tags, inline=cued.inline, independent=cued.independent,
                    track_index=track_index,
                )
            line = replace(line, _at_placement=(), _fit_display=track.tail is None)
            for effect in track.effects:
                if isinstance(effect, LyricRule):
                    continue
                if isinstance(effect, KaraokeEffects) and (reverse or horizontal_rtl):
                    effect = replace(effect, reverse_wipe=horizontal_rtl != (reverse or effect.reverse_wipe))
                if isinstance(effect, LyricParticles) and effect.color is None:
                    effect = replace(effect, color=recipe.sung if recipe else palette.sung)
                # Catalog colors were bound once for the Track and its cues.
                # Subclasses and custom callables keep their own entry point.
                apply = effect._decorate if type(effect) is KaraokeEffects else effect
                line = apply(line)
                if not isinstance(line, LyricLine) or line.id != identity:
                    raise ValueError(
                        f"{identity}: visual factory must preserve lyric identity"
                    )
            if line._scheduled:
                bindings = (*bindings, *line._scheduled)
                resolved[identity] = bindings
                entrance, exit = _padding(bindings)
                display = Lifetime(
                    max(0, min(display.start, singing.start - entrance)),
                    max(display.end, singing.end + (minimum_hold + exit)),
                )
                scheduled = _reserved_animations(tuple(b for b in line._scheduled if not b.flexible))
                requested = _reserved_animations(line._scheduled)
                if requested is not None:
                    display = Lifetime(min(display.start, requested.start), max(display.end, requested.end))
                if scheduled is not None:
                    reserved = (
                        scheduled
                        if reserved is None
                        else Lifetime(
                            min(reserved.start, scheduled.start),
                            max(reserved.end, scheduled.end),
                        )
                    )
                    display = Lifetime(
                        min(display.start, reserved.start),
                        max(display.end, reserved.end),
                    )
                line = replace(line, _scheduled=())
            visual = _visual_spans(line)
            if line._optional_display:
                display = Lifetime(
                    min(display.start, *(span.start for span in line._optional_display)),
                    max(display.end, *(span.end for span in line._optional_display)),
                )
            if line.lifetime.end > max(display.end, line._flexible_end):
                visual = (*visual, TimeSpan(display.end, line.lifetime.end))
            if visual:
                required = Lifetime(
                    min(span.start for span in visual), max(span.end for span in visual)
                )
                reserved = (
                    required
                    if reserved is None
                    else Lifetime(
                        min(reserved.start, required.start),
                        max(reserved.end, required.end),
                    )
                )
                display = Lifetime(
                    min(display.start, reserved.start), max(display.end, reserved.end)
                )
            display = Lifetime(
                min(display.start, line.lifetime.start),
                max(display.end, line.lifetime.end),
            )
            if line.lifetime != display:
                line = line.with_display(display)
            prepared[identity] = line
            cue_bounds = tuple(
                Box(
                    cue.position.x,
                    cue.position.y,
                    cue.content.width,
                    cue.content.height,
                )
                for cue in cued.cues
                if cue.marker.placement == "inline"
            )
            bounds = _union((line.layout.bounds, *cue_bounds))
            obstacles = [*cue_bounds, *(c.bounds for c in line.layout.body.characters),
                         *(c.bounds for r in line.layout.ruby for c in r.layout.characters)]
            for marker, group in zip(
                (cue for cue in cued.cues if cue.marker.placement == "independent"), cued.independent, strict=True
            ):
                edge = marker.preset.line_edge
                if edge is None:
                    continue
                width, height = marker.content.width, marker.content.height
                row = line.layout.bounds
                x = (max(row.right - width, row.center - width / 2) if horizontal_rtl
                     else min(row.left, row.center - width / 2))
                under = [box for box in obstacles if box.left < x + width and x < box.right]
                if edge == "above":
                    y = min((box.top for box in under), default=row.top) - marker.gap - height
                else:
                    y = max((box.top + box.height for box in under), default=row.top + row.height) + marker.gap
                row_cues[group.id] = Vec2(x, y)
                occupied = Box(x, y, width, height)
                obstacles.append(occupied)
                bounds = _union((bounds, occupied))
            allocation_inputs.append(
                LayoutLine(
                    id=identity,
                    singing=singing,
                    display=display,
                    bounds=bounds,
                    body_bounds=line.layout.body.bounds,
                    body_font_size=max((g.object.font_size for g in bare.body.characters), default=None),
                    em_size=line.query("line")[0].em_size,
                    _vertical=track.vertical,
                    _lyric_width=bare.bounds.width if cue_bounds else None,
                    _row_metrics=None if track.vertical else _row_metrics(line.layout, bounds, border, secondary_width),
                    _adaptive_handoff=track.tail is None,
                    entrance=entrance,
                    exit=exit,
                    sources=(SourceRef(source.id),),
                    tags=tags,
                    cues=source.lyrics.body.cues,
                    lead=bool(source.lyrics.body.cues) or (
                        source.chapter is not None and (
                            track_index == 0 or source.chapter != original[track_index - 1].chapter
                        )
                    ),
                    reserved=reserved,
                )
            )
        batch = tuple(allocation_inputs)
        region = track.region or Box(
            0, 0, source_document.meta.res_x, source_document.meta.res_y
        )
        placements = layout.allocate(
            batch, LayoutContext(region, track.references, source_document.meta.res_y)
        )
        validate_placements(batch, placements)
        by_id = {placement.id: placement for placement in placements}
        for source, item in zip(selected, batch, strict=True):
            placement = by_id[item.id]
            line = prepared[item.id]
            if source.record_index is not None:
                scene.replace_source(source.record_index)
                record = source_document.records[source.record_index]
                assert isinstance(record, Line)
                source_document.records[source.record_index] = replace(
                    record,
                    effect=write_source_marker(owner, source.id, source.effect),
                )
            if window is not None and not any(
                lifetime.start < window.end and window.start < lifetime.end
                for lifetime in (placement.display, *(cue.lifetime for cue in line.independent))
            ):
                continue
            if line.lifetime != placement.display:
                line = line.with_display(placement.display)
            entry_scale = exit_scale = 1.0
            if item._adaptive_handoff:
                if item.entrance:
                    entry_scale = min(1.0, max(0.0, item.singing.start - placement.display.start) / item.entrance)
                if item.exit:
                    exit_scale = min(1.0, max(0.0, placement.display.end - item.singing.end) / item.exit)
            for decorate in line._at_placement or ():
                line = decorate(line, entry_scale, exit_scale)
            line = replace(
                line, _at_placement=None, _fit_display=False, _flexible_end=0,
                _optional_display=(), _optional_objects=frozenset(),
            )
            line = replace(
                line,
                state=replace(
                    line.state, position=line.state.position + placement.position
                ),
            )
            glyphs = (frozenset(t.node_id for t in line.query("character", "ruby"))
                      if track.extrusion else frozenset())
            stamped = _stamp(line, source.id, track.id, track.extrusion, glyphs)
            assert isinstance(stamped, LyricLine)
            independent = tuple(
                _stamp(
                    replace(cue, state=replace(cue.state, position=row_cues[cue.id] + line.state.position))
                    if cue.id in row_cues else cue, source.id, track.id,
                )
                for cue in line.independent
            )
            line = replace(
                stamped,
                independent=tuple(
                    cue for cue in independent if isinstance(cue, ObjectGroup)
                ),
            )
            current = {target.id: target for target in line.targets}
            fitted = []
            for binding in resolved[item.id]:
                scale = 1.0
                if binding.target.role != "cue":
                    if binding.at == "enter":
                        scale = entry_scale
                    elif binding.at == "exit":
                        scale = exit_scale
                motion = binding.animation
                hold = binding.hold
                duration = binding.duration * scale
                if item._adaptive_handoff and binding.fit_end == "before_exit" and isinstance(binding.at, (int, float)):
                    release_end = placement.display.end - item.exit * exit_scale
                    room = max(item.singing.end, release_end) - binding.at - binding.offset
                    if room < duration:
                        motion = _animation_prefix(motion, max(0.0, room) / duration)
                        duration, hold = room, False
                if binding.fit_end == "display" and isinstance(binding.at, (int, float)) and item._adaptive_handoff:
                    duration = min(duration, placement.display.end - binding.at - binding.offset)
                if duration <= 0:
                    continue
                if isinstance(motion, RowSlide):
                    motion = motion.for_row(placement.row)
                fitted.append(replace(binding, target=current[binding.target.id], animation=motion,
                                      duration=duration, offset=binding.offset * scale, hold=hold))
            line = line._bind(tuple(fitted))
            scene.add(*line.objects)
            plans.append(LinePlan(track.id, source, item, placement, line))
    for source in sources:
        index = source.record_index
        if index is not None and index not in scene.replace_records:
            record = source_document.records[index]
            assert isinstance(record, Line)
            source_document.records[index] = replace(
                record, comment=False, effect=source.effect
            )
    scene.plans = tuple(plans)
    return scene
