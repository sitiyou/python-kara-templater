"""Lyric streams bind targets, display and layout into the shared Scene model."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass, field, replace
from functools import cached_property
from hashlib import sha256
from pathlib import Path
from urllib.parse import quote, unquote

from .ass import Document, Line, Style
from .coverage_animation import GlowFunction
from .cues import CueContent, CueContext, CueFactory, CuePreset, bind_lyric_cues
from .document_lyrics import DocumentLyrics, parse_document_lyrics
from .document_text import DocumentText
from .geometry import finite
from .import_ass import SOURCE_PREFIX, SourceBinding, source_marker, source_prefix
from .lyric_highlights import LyricHighlights
from .lyric_layout import (
    KaraokeRows,
    Layout,
    LayoutContext,
    LayoutLine,
    Placement,
    validate_placements,
)
from .lyric_line import LyricLine, LyricRule, _LyricBinding
from .model import Box
from .scene import Lifetime, ObjectGroup, Scene, SceneObject
from .scene_animation import TimeSpan
from .scene_lyrics import LyricLayout, layout_lyrics
from .scene_output import SceneBudget, _scene_source_records
from .scene_text import DocumentLayout, _union
from .sources import EventOrigin, SourceRef


@dataclass(frozen=True)
class LyricSource:
    """An immutable source view used by Track predicates and metadata functions.

    id identifies source content independently of its track/view. Original
    singing intervals remain in lyrics; display is the original ASS visibility.
    """

    id: str
    record_index: int | None
    style: str
    actor: str
    effect: str
    display: Lifetime
    text_data: DocumentText
    projection: DocumentLyrics | None = None

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
    ) -> LyricSource:
        """Create a structured source without synthesizing or replacing ASS records.

        The projection retains full-precision singing, appearance runs, ruby and
        cues. Regeneration requires supplying this source again; ASS output does
        not embed Python data or private serialization.
        """
        if not id:
            raise ValueError("structured lyrics need a stable source id")
        return cls(id, None, style, actor, effect, display, lyrics.source, lyrics)

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


type LyricEffect = LyricRule | Callable[[LyricLine], LyricLine]


@dataclass(frozen=True, kw_only=True)
class Track:
    """An independent lyric stream with selection, placement and composable effects.

    With layout omitted, two bottom rows alternate left and right in the region.
    All times use seconds. preview/tail are desired, reducible display padding;
    rule durations and inline cue visibility are mandatory occupancy. The visual
    effects receive the measured, unpositioned line once before allocation.
    LyricRule entries declare timing; callable entries decorate the line in order.
    Rule factories resolve once before decoration and bind to final target aliases.
    Authored visual intervals join occupancy; rule binding follows allocation.
    min_outline_gap is the minimum script-pixel clearance between hard strokes;
    None preserves shaped spacing. reserved_border declares the outer hard radius
    of custom or shared visual layers. Glow and motion do not reserve space.
    ruby_gap sets the visual gap in script pixels between hard outlines of
    the reading group and its body at rest. Negative values allow overlap.
    All animation evaluation and output belong to Scene.
    """

    id: str
    source: Callable[[LyricSource], bool] = _all_sources
    layout: Layout | KaraokeRows | None = None
    region: Box | None = None
    preview: float = 1.8
    tail: float = 1.0
    effects: tuple[LyricEffect, ...] = ()
    cues: Mapping[str, CuePreset] = field(default_factory=dict)
    tags: frozenset[str] | Callable[[LyricSource], frozenset[str]] = frozenset()
    styles: tuple[Style, ...] = ()
    references: tuple[LayoutLine, ...] = ()
    min_outline_gap: float | None = 2
    reserved_border: float = 0
    ruby_gap: float = 6

    def __post_init__(self) -> None:
        finite(self.preview, self.tail, self.reserved_border, self.min_outline_gap or 0, self.ruby_gap)
        if self.reserved_border < 0 or (
            self.min_outline_gap is not None and self.min_outline_gap < 0
        ):
            raise ValueError("outline clearance must be nonnegative")
        if not self.id:
            raise ValueError("Track needs a stable id")
        if self.preview < 0 or self.tail < 0:
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

    def export_compact_ass(self, path: str | Path, *, budget: SceneBudget | None = None) -> None:
        """Save a playback ASS with native karaoke timing, line fades and cues.

        For simple KaraokeEffects lines this approximates motion and materials with
        native sweep and fade tags. Duotone readings use measured ruby layouts and
        their own clocks. Complex timings and internal inline cue reservations
        use ordinary ASS compilation. budget controls compiler resource limits.
        """
        from ._compact_ass import compact_document

        compact_document(self, budget or SceneBudget()).save(path)

    @property
    def lines(self) -> tuple[LyricLine, ...]:
        """The bound lyric lines in track/source order."""
        return tuple(plan.line for plan in self.plans)


def _sources(document: Document, owner: str) -> tuple[LyricSource, ...]:
    prefix = source_prefix(owner)
    result: list[LyricSource] = []
    seen: set[str] = set()
    for index, record in enumerate(document.records):
        if not isinstance(record, Line):
            continue
        marked = record.comment and record.effect.startswith(prefix)
        if record.comment and not marked:
            continue
        if record.effect.startswith("kara:scene:v1:"):
            continue
        if record.effect.startswith(SOURCE_PREFIX) and not marked:
            continue
        # Selection operates on lyric inputs, not untimed template/drawing events.
        text = document.text_at(index)
        if not text.timing:
            continue
        if marked:
            identifier, separator, effect = record.effect[len(prefix) :].partition(":")
            if not separator or not identifier:
                raise ValueError(f"record {index}: damaged lyric source marker")
            identifier, effect = unquote(identifier), unquote(effect)
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
    nodes: dict[str, SceneObject] = {}

    def collect(node: SceneObject, window: TimeSpan | None = None) -> None:
        nodes[node.id] = node
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
    for node in nodes.values():
        if not isinstance(node, ObjectGroup) or node.coverage is None:
            continue
        for name, glow in node.coverage.glows.items():
            if isinstance(glow, GlowFunction) and glow.required_interval is not None:
                owner = nodes[name]
                span = glow.required_interval
                spans.append(
                    TimeSpan(
                        owner.time_origin + span.start, owner.time_origin + span.end
                    )
                )
    return tuple(spans)


def _stamp(node: SceneObject, source: str, track: str) -> SceneObject:
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
            children=tuple(_stamp(child, source, track) for child in node.children),
        )
    return replace(node, origin=origin)


def _cue_presets(presets: Mapping[str, CuePreset]) -> dict[str, CuePreset]:
    """Measure and bind each cue from the same factory result within one line."""
    result: dict[str, CuePreset] = {}
    for name, preset in presets.items():
        cache: dict[CueContext, CueContent] = {}

        def factory(
            context: CueContext,
            *,
            original: CueFactory = preset.factory,
            memo: dict[CueContext, CueContent] = cache,
        ) -> CueContent:
            if context not in memo:
                memo[context] = original(context)
            return memo[context]

        result[name] = replace(preset, factory=factory)
    return result


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


def prepare_tracks(
    document: Document,
    *,
    tracks: tuple[Track, ...],
    owner: str = "karaoke",
    inputs: tuple[LyricSource, ...] = (),
) -> LyricScene:
    """Measure, allocate and bind independent tracks into one ordinary Scene.

    Same-source views are allowed and have distinct visual identities. Original
    records are retained once as owner-marked comments. Re-preparing owned output
    removes only that owner's generated events and regenerates from its sources.
    inputs adds structured LyricSource values alongside parsed ASS sources.
    These have no ASS record ownership and must be supplied again to regenerate
    them. The caller's Document and reusable declarations are not mutated.
    """
    if not owner:
        raise ValueError("lyric scene owner cannot be empty")
    if len({track.id for track in tracks}) != len(tracks):
        raise ValueError("duplicate Track ids")
    source_document = deepcopy(document)
    source_document.records = _scene_source_records(
        source_document.records, "kara:scene:v1:" + quote(owner, safe="") + ":", set()
    )
    if any(source.record_index is not None for source in inputs):
        raise ValueError(
            "explicit inputs must be structured sources without ASS record ownership"
        )
    sources = (*_sources(source_document, owner), *deepcopy(inputs))
    if len({source.id for source in sources}) != len(sources):
        raise ValueError("duplicate lyric source ids")
    scene = LyricScene(source_document, owner=owner)
    plans: list[LinePlan] = []
    for declaration in tracks:
        track = deepcopy(declaration)
        selected = sorted(
            (source for source in sources if track.source(source)),
            key=lambda source: min(
                (
                    segment.singing.start
                    for unit in source.lyrics.units
                    for segment in unit.segments
                ),
                default=source.display.start,
            ),
        )
        view = Document([*source_document.records, *track.styles], source_document.meta)
        allocation_inputs: list[LayoutLine] = []
        prepared: dict[str, LyricLine] = {}
        resolved: dict[str, tuple[_LyricBinding, ...]] = {}
        border = max(
            [track.reserved_border]
            + [
                effect._hard_border
                for effect in track.effects
                if isinstance(effect, LyricHighlights)
            ]
        )
        for source in selected:
            identity = f"track:{quote(track.id, safe='')}/{source.id}"
            spans = tuple(
                segment.singing
                for unit in source.lyrics.units
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
            entrance = exit = 0.0
            display = Lifetime(
                max(
                    0,
                    min(source.display.start, singing.start)
                    - max(track.preview, entrance),
                ),
                max(source.display.end, singing.end) + max(track.tail, exit),
            )
            bare = layout_lyrics(
                view,
                source.lyrics,
                id=identity,
                display=display,
                min_outline_gap=track.min_outline_gap,
                reserved_border=border,
                ruby_gap=track.ruby_gap,
            )
            local_presets = _cue_presets(track.cues)
            cued = bind_lyric_cues(bare, local_presets)
            bindings = LyricLine.from_layout(
                cued.lyrics, tags=tags, inline=cued.inline, independent=cued.independent
            )._resolve(
                tuple(
                    effect for effect in track.effects if isinstance(effect, LyricRule)
                )
            )
            resolved[identity] = bindings
            entrance, exit = _padding(bindings)
            display = Lifetime(
                max(0, min(display.start, singing.start - entrance)),
                max(display.end, singing.end + exit),
            )
            reserved = _reserved_animations(bindings)
            if cued.inline:
                reserved = Lifetime(
                    min(
                        *(cue.lifetime.start for cue in cued.inline),
                        reserved.start if reserved else singing.start,
                    ),
                    max(
                        *(cue.lifetime.end for cue in cued.inline),
                        reserved.end if reserved else singing.end,
                    ),
                )
            if reserved is not None:
                display = Lifetime(
                    min(display.start, reserved.start), max(display.end, reserved.end)
                )
            cued = bind_lyric_cues(_retime(bare, display), local_presets)
            line = LyricLine.from_layout(
                cued.lyrics, tags=tags, inline=cued.inline, independent=cued.independent
            )
            for effect in track.effects:
                if isinstance(effect, LyricRule):
                    continue
                line = effect(line)
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
                    max(display.end, singing.end + exit),
                )
                scheduled = _reserved_animations(line._scheduled)
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
            if line.lifetime.end > display.end:
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
            allocation_inputs.append(
                LayoutLine(
                    id=identity,
                    singing=singing,
                    display=display,
                    bounds=_union((line.layout.bounds, *cue_bounds)),
                    entrance=entrance,
                    exit=exit,
                    sources=(SourceRef(source.id),),
                    tags=tags,
                    cues=source.lyrics.body.cues,
                    lead=bool(source.lyrics.body.cues),
                    reserved=reserved,
                )
            )
        batch = tuple(allocation_inputs)
        region = track.region or Box(
            0, 0, source_document.meta.res_x, source_document.meta.res_y
        )
        layout = KaraokeRows() if track.layout is None else track.layout
        placements = layout.allocate(
            batch, LayoutContext(region, track.references, source_document.meta.res_y)
        )
        validate_placements(batch, placements)
        by_id = {placement.id: placement for placement in placements}
        for source, item in zip(selected, batch, strict=True):
            placement = by_id[item.id]
            line = prepared[item.id].with_display(placement.display)
            line = replace(
                line,
                state=replace(
                    line.state, position=line.state.position + placement.position
                ),
            )
            stamped = _stamp(line, source.id, track.id)
            assert isinstance(stamped, LyricLine)
            independent = tuple(
                _stamp(cue, source.id, track.id) for cue in line.independent
            )
            line = replace(
                stamped,
                independent=tuple(
                    cue for cue in independent if isinstance(cue, ObjectGroup)
                ),
            )
            current = {target.id: target for target in line.targets}
            line = line._bind(
                tuple(
                    replace(binding, target=current[binding.target.id])
                    for binding in resolved[item.id]
                )
            )
            scene.add(*line.objects)
            if source.record_index is not None:
                scene.replace_source(source.record_index)
                record = source_document.records[source.record_index]
                assert isinstance(record, Line)
                source_document.records[source.record_index] = replace(
                    record,
                    effect=source_marker(
                        owner,
                        SourceBinding(source.record_index, source.id, source.effect),
                    ),
                )
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
