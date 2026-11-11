"""Render structured karaoke items into a copied ASS document."""

from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass, replace
from typing import Protocol, runtime_checkable
from urllib.parse import quote

from .ass import Document, Line
from .ass_output import OutputCapabilityError, OutputSettings, compile_layers, quantize
from .effect import Effect
from .import_ass import ImportSettings, import_karaoke, source_marker
from .layout import layout_line
from .recipe import EffectContext, EffectPlan, KaraokeItem
from .sampling import SamplingEstimate, prepare_sampling
from .sources import EventOrigin, SourceRef, _source_context


@runtime_checkable
class EffectBuilder(Protocol):
    def build(self, item: KaraokeItem, context: EffectContext) -> EffectPlan: ...


type EffectFactory = type[Effect] | EffectBuilder | Callable[
    [KaraokeItem, EffectContext], EffectPlan
]
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

    @property
    def estimated_events(self) -> int:
        return (
            self.static_events
            + self.raw_events
            + sum(s.estimated_events for s in self.sampling)
        )

    @property
    def target_samples(self) -> int:
        return sum(s.target_samples for s in self.sampling)


@dataclass(frozen=True)
class RenderResult:
    document: Document
    diagnostics: tuple[str, ...]
    event_count: int
    layer_count: int
    # Entries refer to the actual generated Line objects in document order.
    event_origins: tuple[tuple[Line, EventOrigin], ...] = ()


def render_karaoke(
    document: Document,
    items: tuple[KaraokeItem, ...] | None = None,
    *,
    effect: EffectInput,
    owner: str = "default",
    settings: OutputSettings | None = None,
    import_settings: ImportSettings | None = None,
    on_estimate: Callable[[RenderEstimate], None] | None = None,
) -> RenderResult:
    """Generate only this owner's events; preserve sources and other owners.

    effect is a recipe with build(item, context), a callable, or a mapping from
    ASS style names to either. With items omitted, import timed ASS dialogue and
    retain it as owned source comments. Explicit structured items leave dialogue
    unchanged. Both paths preserve the input document.
    on_estimate runs once after preflight and before dynamic property functions.
    It may raise to cancel rendering. Recipe builders have already run by then.
    """
    if not isinstance(owner, str) or not owner:
        raise ValueError("render owner must be a nonempty string")
    if on_estimate is not None and not callable(on_estimate):
        raise TypeError("on_estimate must be callable")
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
    result = deepcopy(document)
    if imported is not None:
        for source in imported.sources:
            line = result.records[source.record_index]
            assert isinstance(line, Line)
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
    dynamic_groups = []
    next_order = 0
    for item in items:
        selected = effect.get(item.style) if isinstance(effect, Mapping) else effect
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
            layout = layout_line(
                item.source, style=style, ruby_style=ruby_style, resolution=resolution
            )
            context = EffectContext(
                layout, style, ruby_style, resolution, settings.max_events
            )
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
            if plan.dynamic is None:
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
    # Insert inside Events, before a possible following ASS section.
    events_section = next(
        (
            i
            for i, r in enumerate(result.records)
            if isinstance(r, str) and r.strip().lower() == "[events]"
        ),
        None,
    )
    if events_section is None:
        from .ass import EVENT_FORMAT

        result.records.extend(("[Events]", "Format: " + EVENT_FORMAT))
        insertion = len(result.records)
    else:
        insertion = next(
            (
                i
                for i in range(events_section + 1, len(result.records))
                if isinstance(record := result.records[i], str)
                and record.strip().startswith("[")
            ),
            len(result.records),
        )
    result.records[insertion:insertion] = generated
    event_origins = []
    for event, origin in zip(generated, origins, strict=True):
        assert origin is not None
        event_origins.append((event, origin))
    return RenderResult(
        result,
        tuple(diagnostics),
        len(generated),
        len(layers),
        tuple(event_origins),
    )
