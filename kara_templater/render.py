"""Render structured karaoke items into a copied ASS document."""

from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass, replace
from typing import Protocol, runtime_checkable
from urllib.parse import quote

from ._track_compiler import PreparedTrack
from ._track_scene import track_objects
from .ass import Document, Line, Style
from .ass_output import OutputCapabilityError, OutputSettings, compile_layers, quantize
from .effect import Effect
from .import_ass import ImportSettings, import_karaoke, source_marker
from .layout import layout_line
from .raster_settings import RasterEstimate, RasterPlan
from .recipe import EffectContext, EffectPlan, KaraokeItem
from .sampling import SamplingEstimate, prepare_sampling
from .scene import NativeEvent, ObjectGroup, Scene, SceneObject
from .scene_output import _insert_events, _scene_source_records
from .sources import EventOrigin, SourceRef, _source_context
from .track import BoundTrack, Track, TrackGroup, bind_tracks


@runtime_checkable
class EffectBuilder(Protocol):
    def build(self, item: KaraokeItem, context: EffectContext) -> EffectPlan: ...


type EffectFactory = (
    type[Effect] | EffectBuilder | Callable[[KaraokeItem, EffectContext], EffectPlan]
)
type EffectInput = EffectFactory | Mapping[str, EffectFactory]


@dataclass(frozen=True)
class RenderEstimate:
    """Document cost before property callbacks; sampling counts precede merging.

    Native curve subdivision can increase the final count. This is neither an
    exact total nor an upper bound; the compiler enforces the final event limit.
    """

    static_events: int
    raw_events: int
    sampling: tuple[SamplingEstimate, ...]
    event_limit: int
    raster: tuple[RasterEstimate, ...] = ()

    @property
    def estimated_events(self) -> int:
        return (
            self.static_events
            + self.raw_events
            + sum(s.estimated_events for s in self.sampling)
            + sum(r.frames * r.frame_event_limit for r in self.raster)
        )

    @property
    def target_samples(self) -> int:
        return sum(s.target_samples for s in self.sampling) + sum(
            r.target_samples for r in self.raster
        )


@dataclass(frozen=True)
class RenderResult:
    document: Document
    diagnostics: tuple[str, ...]
    event_count: int
    layer_count: int
    # Entries refer to the actual generated Line objects in document order.
    event_origins: tuple[tuple[Line, EventOrigin], ...] = ()


@dataclass(frozen=True)
class PreparedKaraoke:
    """Prepared karaoke scene plus frontend diagnostics and layer count.

    prepare_karaoke supplies already-lowered NativeEvents; prepare_track_scene
    supplies editable objects whose property callbacks run at Scene compilation.
    """

    scene: Scene
    diagnostics: tuple[str, ...]
    layer_count: int


def prepare_karaoke(
    document: Document,
    items: tuple[KaraokeItem, ...] | None = None,
    *,
    effect: EffectInput | None = None,
    tracks: tuple[Track | TrackGroup, ...] | None = None,
    owner: str = "default",
    settings: OutputSettings | None = None,
    import_settings: ImportSettings | None = None,
    on_estimate: Callable[[RenderEstimate], None] | None = None,
) -> PreparedKaraoke:
    """Prepare existing Track/recipe output as source-mapped NativeEvents.

    Property/raster callbacks run during preparation; Scene compilation does
    not rerun them. Use prepare_track_scene for editable Track objects instead.
    """
    return _prepare_karaoke(
        document,
        items,
        effect=effect,
        tracks=tracks,
        owner=owner,
        settings=settings,
        import_settings=import_settings,
        on_estimate=on_estimate,
    )


def prepare_track_scene(
    document: Document,
    items: tuple[KaraokeItem, ...] | None = None,
    *,
    tracks: tuple[Track | TrackGroup, ...],
    owner: str = "default",
    import_settings: ImportSettings | None = None,
    max_objects: int = 25_000,
) -> PreparedKaraoke:
    """Bind Tracks to editable ObjectGroups without sampling property callbacks.

    Input and ownership rules match prepare_karaoke. SceneBudget controls output
    sampling and cost; Track.sampling belongs to the legacy output path. Native
    per-layer opacity and hard-clipped sweep decorations remain explicit limits.
    max_objects bounds generated text nodes as well as per-item mask partitions.
    """
    if type(max_objects) is not int or max_objects < 1:
        raise ValueError("max_objects must be a positive integer")
    settings = OutputSettings(
        resolution=(int(document.meta.res_x), int(document.meta.res_y)),
        max_events=max_objects,
    )
    return _prepare_karaoke(
        document,
        items,
        tracks=tracks,
        owner=owner,
        settings=settings,
        import_settings=import_settings,
        editable_tracks=True,
    )


def _object_layers(node: SceneObject) -> tuple[int, int]:
    if not isinstance(node, ObjectGroup):
        return 1, node.layer
    children = tuple(_object_layers(child) for child in node.children)
    return sum(count for count, _ in children), node.layer + max(
        (layer for _, layer in children), default=0
    )


def _prepare_karaoke(
    document: Document,
    items: tuple[KaraokeItem, ...] | None = None,
    *,
    effect: EffectInput | None = None,
    tracks: tuple[Track | TrackGroup, ...] | None = None,
    owner: str = "default",
    settings: OutputSettings | None = None,
    import_settings: ImportSettings | None = None,
    on_estimate: Callable[[RenderEstimate], None] | None = None,
    editable_tracks: bool = False,
    track_builder: Callable[[str, PreparedTrack, list[str]], ObjectGroup] | None = None,
) -> PreparedKaraoke:
    """Prepare only this owner's events; preserve sources and other owners.

    effect is a recipe with build(item, context), a callable, or a mapping from
    ASS style names to either. With items omitted, import timed ASS dialogue and
    retain it as owned source comments. Explicit structured items leave dialogue
    unchanged. Both paths preserve the input document.
    on_estimate runs once after preflight and before dynamic property functions.
    It may raise to cancel rendering. Recipe builders have already run by then.
    """
    if not isinstance(owner, str) or not owner:
        raise ValueError("render owner must be a nonempty string")
    if (effect is None) == (tracks is None):
        raise ValueError("provide exactly one of effect or tracks")
    if on_estimate is not None and not callable(on_estimate):
        raise TypeError("on_estimate must be callable")
    scene_owner = "karaoke:" + owner
    document = deepcopy(document)
    document.records = _scene_source_records(
        document.records,
        "kara:scene:v1:" + quote(scene_owner, safe="") + ":",
        set(),
    )
    imported = (
        import_karaoke(document, owner=owner, settings=import_settings)
        if items is None
        else None
    )
    if imported is not None:
        items = imported.items
    assert items is not None
    if len({item.id for item in items}) != len(items):
        raise ValueError("duplicate karaoke item ids")
    selected_tracks: dict[str, BoundTrack] = {}
    if tracks is not None:
        selected_tracks = bind_tracks(tracks, items)
    result = document
    if imported is not None:
        for source in imported.sources:
            line = result.records[source.record_index]
            assert isinstance(line, Line)
            if tracks is not None and source.item_id not in selected_tracks:
                # Restore previously owned sources when the selection changes.
                line.comment = False
                line.effect = source.original_effect
                continue
            line.comment = True
            line.effect = source_marker(owner, source)
    resolution = (int(result.meta.res_x), int(result.meta.res_y))
    settings = settings or OutputSettings(resolution=resolution)
    if settings.resolution != resolution:
        raise ValueError("output resolution must match document PlayRes")
    prefix = f"karaoke:v1:{quote(owner, safe='')}:"
    result.records = [
        r
        for r in result.records
        if not isinstance(r, Line) or not r.effect.startswith(prefix)
    ]
    layers, raw_lines, diagnostics = [], [], []
    editable_groups: list[ObjectGroup] = []
    object_count = 0
    dynamic_groups = []
    raster_groups: list[tuple[RasterPlan, int]] = []
    next_order = 0
    for item in items:
        if tracks is not None and item.id not in selected_tracks:
            continue
        selected = (
            selected_tracks[item.id]
            if tracks is not None
            else effect.get(item.style)
            if isinstance(effect, Mapping)
            else effect
        )
        fallback_origin = EventOrigin(
            (SourceRef(item.id),),
            (
                "style dispatch"
                if isinstance(effect, Mapping) and item.style not in effect
                else getattr(selected, "__qualname__", type(selected).__name__)
            ),
        )
        with _source_context(fallback_origin):
            styles = result.styles
            if item.style not in styles:
                raise ValueError(f"{item.id}: missing style {item.style!r}")
            style = styles[item.style]
            if item.margins is not None:
                style = replace(
                    style,
                    **{
                        name: value if value > 0 else getattr(style, name)
                        for name, value in zip(
                            ("margin_l", "margin_r", "margin_v"),
                            item.margins,
                            strict=True,
                        )
                    },
                )
            ruby_name = item.ruby_style or item.style + "-ruby"
            if item.ruby_style and ruby_name not in styles:
                raise ValueError(f"{item.id}: missing ruby style {ruby_name!r}")
            ruby_style = styles.get(ruby_name) or replace(
                style,
                name=ruby_name,
                fontsize=style.fontsize / 2,
                outline=style.outline / 2,
                shadow=style.shadow / 2,
                fields={},
            )
            if isinstance(effect, Mapping) and item.style not in effect:
                raise ValueError(
                    f"{item.id}: no effect configured for style {item.style!r}"
                )
            # Author configuration runs on source targets before measurement.
            if isinstance(selected, type) and issubclass(selected, Effect):
                selected = selected()
            if isinstance(selected, Effect):
                selected, style, ruby_style = selected._prepare(item, style, ruby_style)
            elif isinstance(selected, BoundTrack):
                style, ruby_style = selected.prepare_styles(style, ruby_style)
            layout = layout_line(
                item.source, style=style, ruby_style=ruby_style, resolution=resolution
            )
            context = EffectContext(
                layout,
                style,
                ruby_style,
                resolution,
                settings.max_events,
                settings.raster,
            )
            if editable_tracks:
                assert isinstance(selected, BoundTrack)
                prepared_track = selected.prepare(item, context)
                group = (
                    track_objects(item.id, prepared_track, diagnostics=diagnostics)
                    if track_builder is None
                    else track_builder(item.id, prepared_track, diagnostics)
                )
                count, highest = _object_layers(group)
                object_count += count
                if object_count > settings.max_events:
                    raise OutputCapabilityError(
                        "editable Track object budget exceeded", origin=fallback_origin
                    )
                editable_groups.append(replace(group, layer=next_order))
                next_order += highest + 1
                continue
            builder = (
                selected.build if isinstance(selected, EffectBuilder) else selected
            )
            if not callable(builder):
                raise TypeError(
                    f"{item.id}: effect must be callable or provide build()"
                )
            plan = builder(item, context)
            if not isinstance(plan, EffectPlan):
                raise TypeError(f"{item.id}: effect must return EffectPlan")
            if settings.raster is not None and plan.raster is None:
                raise OutputCapabilityError(
                    "raster output requires prepared Track targets",
                    origin=fallback_origin,
                )
            # Allocate one contiguous block per lyric, preserving local stack order.
            minimum = min((layer.order for layer in plan.layers), default=0)
            shifted = tuple(
                replace(
                    layer,
                    order=layer.order - minimum + next_order,
                    origin=layer.origin or fallback_origin,
                )
                for layer in plan.layers
            )
            if plan.raster is not None:
                if shifted or plan.dynamic is not None or plan.raw_lines:
                    raise ValueError(
                        "raster plans cannot also declare native layers or raw events"
                    )
                raster_groups.append((plan.raster, next_order * 2))
                next_order += 1
            elif plan.dynamic is None:
                layers.extend(shifted)
            else:
                dynamic_groups.append((shifted, plan.dynamic))
            next_order = max((layer.order + 1 for layer in shifted), default=next_order)
            diagnostics.extend(plan.diagnostics)
            raw_lines.extend(
                (line, fallback_origin) for line in deepcopy(plan.raw_lines)
            )
            if (
                any(layer.style.name == ruby_name for layer in plan.layers)
                and ruby_name not in styles
            ):
                # Insert inside Styles, even when Fonts or other sections intervene.
                section = next(
                    i
                    for i, record in enumerate(result.records)
                    if isinstance(record, str)
                    and record.strip().lower() == "[v4+ styles]"
                )
                position = next(
                    (
                        i
                        for i in range(section + 1, len(result.records))
                        if isinstance(record := result.records[i], str)
                        and record.strip().startswith("[")
                    ),
                    len(result.records),
                )
                result.records.insert(position, ruby_style)
    if editable_tracks:
        diagnostics.append(
            "editable Track animations use SceneBudget sampling; Track.sampling is not applied"
        )
        if track_builder is None:
            diagnostics.append(
                "editable Track opacity is applied per drawing layer, not after group compositing"
            )
        return PreparedKaraoke(
            Scene(result, owner=scene_owner).add(*editable_groups),
            tuple(dict.fromkeys(diagnostics)),
            object_count,
        )
    # Validate declared styles before evaluating any dynamic property function.
    for group in (layers, *(group for group, _ in dynamic_groups)):
        for layer in group:
            with _source_context(layer.origin):
                if layer.style.name not in result.styles:
                    raise ValueError(
                        f"{layer.source_id}: missing style {layer.style.name!r}"
                    )
    compiled = compile_layers(tuple(layers), settings=settings)
    generated = list(compiled.events)
    origins = list(compiled.origins)
    diagnostics.extend(compiled.diagnostics)
    static_events = len(generated)
    for line, origin in raw_lines:
        with _source_context(origin):
            if line.start_time < 0 or line.end_time <= line.start_time:
                raise ValueError(
                    "raw effect event must have a nonnegative, positive-duration interval"
                )
            if line.style not in result.styles:
                raise ValueError(f"raw effect event: missing style {line.style!r}")
            line.start_time, line.end_time = (
                quantize(line.start_time),
                quantize(line.end_time),
            )
            if line.end_time <= line.start_time:
                diagnostics.append(
                    "raw effect event vanished during centisecond quantization"
                )
            else:
                generated.append(line)
                origins.append(origin)
    raw_events = len(generated) - static_events
    if len(generated) > settings.max_events:
        raise OutputCapabilityError(
            f"owner {owner}: static events plus raw lines exceed {settings.max_events}"
        )
    remaining = settings.max_events - len(generated)
    sampling_plans = []
    for group, dynamic in dynamic_groups:
        prepared = prepare_sampling(group, dynamic, max_events=max(0, remaining))
        remaining -= prepared.estimate.estimated_events
        sampling_plans.append(prepared)
    # Every group passes preflight before any property callback is executed.
    if on_estimate is not None:
        on_estimate(
            RenderEstimate(
                static_events,
                raw_events,
                tuple(p.estimate for p in sampling_plans),
                settings.max_events,
                tuple(plan.estimate for plan, _ in raster_groups),
            )
        )
    for prepared in sampling_plans:
        estimate = prepared.estimate
        diagnostics.append(
            f"sampling: {estimate.target_samples} target samples at {estimate.step_ms} ms; "
            f"estimated {estimate.estimated_events} events before native subdivision"
        )
        sampled = prepared.evaluate()
        available = settings.max_events - len(generated)
        if sampled and available <= 0:
            raise OutputCapabilityError("dynamic effects exceed output event budget")
        output = compile_layers(
            sampled, settings=replace(settings, max_events=max(1, available))
        )
        generated.extend(output.events)
        origins.extend(output.origins)
        diagnostics.extend(output.diagnostics)
        layers.extend(sampled)
    if raster_groups:
        diagnostics.append(
            "raster pixel fidelity requires RGB or full-resolution chroma subtitle "
            "compositing; YUV420 blending can introduce rectangle-dependent color edges"
        )
        # Pixels need a neutral drawing style, independent of source text flags.
        name = "__kara_raster_" + quote(owner, safe="")
        neutral = Style(name=name, outline=0, shadow=0)
        if name in result.styles:
            if result.styles[name].serialize() != neutral.serialize():
                raise ValueError(
                    f"reserved raster style {name!r} has incompatible fields"
                )
        else:
            section = next(
                i
                for i, record in enumerate(result.records)
                if isinstance(record, str) and record.strip().lower() == "[v4+ styles]"
            )
            insertion = next(
                (
                    i
                    for i in range(section + 1, len(result.records))
                    if isinstance(record := result.records[i], str)
                    and record.strip().startswith("[")
                ),
                len(result.records),
            )
            result.records.insert(insertion, neutral)
        assert settings.raster is not None
        remaining_chars = settings.raster.max_output_chars
        if settings.raster.max_channel_error:
            diagnostics.append(
                f"raster spatial color error <= {settings.raster.max_channel_error}/255 "
                "per composited channel before ASS transforms; temporal sampling is separate"
            )
        for prepared, order in raster_groups:
            estimate = prepared.estimate
            diagnostics.append(
                f"raster: {estimate.frames} frames, {estimate.target_samples} target samples; exact events checked during encoding"
            )
            output = prepared.evaluate(
                style=name,
                layer=order,
                max_events=settings.max_events - len(generated),
                max_chars=remaining_chars,
            )
            remaining_chars -= sum(len(line.text) for line in output)
            generated.extend(output)
            origins.extend(prepared.origin for _ in output)
    if len(generated) > settings.max_events:
        raise OutputCapabilityError(
            f"owner {owner}: generated events plus raw lines exceed {settings.max_events}"
        )
    for index, line in enumerate(generated):
        with _source_context(origins[index]):
            if line.style not in result.styles:
                raise ValueError(
                    f"generated event {index}: missing style {line.style!r}"
                )
            line.effect = prefix + quote(line.effect or f"raw:{index}", safe="")
    scene = Scene(result, owner=scene_owner)
    for index, (event, origin) in enumerate(zip(generated, origins, strict=True)):
        assert origin is not None
        scene.add(NativeEvent(f"karaoke:{index}", event, origin))
    return PreparedKaraoke(
        scene,
        tuple(diagnostics),
        len(layers) + sum(plan.layer_count for plan, _ in raster_groups),
    )


def render_karaoke(
    document: Document,
    items: tuple[KaraokeItem, ...] | None = None,
    *,
    effect: EffectInput | None = None,
    tracks: tuple[Track | TrackGroup, ...] | None = None,
    owner: str = "default",
    settings: OutputSettings | None = None,
    import_settings: ImportSettings | None = None,
    on_estimate: Callable[[RenderEstimate], None] | None = None,
) -> RenderResult:
    """Render Track/recipe output with the historical ownership and report format.

    Use prepare_karaoke(...).scene to combine this output with new scene objects
    and apply SceneBudget to the whole composition. Both entrances preserve the
    input Document and evaluate Track property callbacks only once.
    """
    prepared = prepare_karaoke(
        document,
        items,
        effect=effect,
        tracks=tracks,
        owner=owner,
        settings=settings,
        import_settings=import_settings,
        on_estimate=on_estimate,
    )
    result = prepared.scene.document
    generated: list[Line] = []
    event_origins: list[tuple[Line, EventOrigin]] = []
    for node in prepared.scene.objects:
        assert isinstance(node, NativeEvent) and node.origin is not None
        generated.append(node.event)
        event_origins.append((node.event, node.origin))
    if generated:
        _insert_events(result, generated, None)
    return RenderResult(
        result,
        prepared.diagnostics,
        len(generated),
        prepared.layer_count,
        tuple(event_origins),
    )
