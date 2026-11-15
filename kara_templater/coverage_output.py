"""Document-backed, explicitly sampled coverage materials → standard ASS."""

from collections.abc import Collection, Mapping
from copy import deepcopy
from dataclasses import dataclass, replace
from hashlib import sha256
from math import ceil

from ._raster import PositionedFrame, encode_frame, quantize_frame
from ._scene_coverage import SceneCoverageSampler
from .ass import Document, Line, Style
from .composition import Glow
from .coverage_animation import CoveragePartition, GlowFunction, ScopeOpacity
from .paint_fields import PaintField
from .raster_settings import RasterSettings
from .scene import NativeEvent, ObjectGroup, PathObject, Scene, SceneObject
from .scene_output import (
    SceneBudget,
    SceneCompileError,
    SceneResult,
    _centiseconds,
    _insert_events,
)
from .sources import EventOrigin
from .timeline import DisplayWindow

_DEFAULT_SETTINGS = RasterSettings()
_DEFAULT_BUDGET = SceneBudget()


@dataclass(frozen=True)
class CoverageResult:
    """Compiled output and the actual midpoint samples (absolute seconds).

    max_channel_error bounds spatial color quantization only. Temporal motion
    is held between samples; no continuous-time image error bound is implied.
    """

    output: SceneResult
    sample_times: tuple[float, ...]
    max_channel_error: int

    @property
    def document(self) -> Document:
        return self.output.document


def _sample_grid(
    sampler: SceneCoverageSampler, settings: RasterSettings, budget: SceneBudget
) -> tuple[tuple[int, ...], float]:
    group = sampler.group
    start, end = map(_centiseconds, (group.lifetime.start, group.lifetime.end))
    frames = ceil((end - start) / 100 * budget.fps)
    if end <= start or frames > settings.max_frames:
        raise SceneCompileError(
            "coverage frame budget exceeded or empty lifetime",
            object_id=group.id,
            origin=group.origin,
        )
    times: set[float] = set()

    def visit(node: SceneObject) -> None:
        times.update(sampler.evaluator.breakpoints(node.id))
        if node.clip is not None and node.clip.deform is not None:
            times.update(node.lifetime.start + t for t in node.clip.deform.breakpoints)
        if node.material is not None:
            times.update(node.lifetime.start + t for t in node.material.breakpoints)
        if isinstance(node, PathObject) and node.deform is not None:
            times.update(node.lifetime.start + t for t in node.deform.breakpoints)
        if isinstance(node, ObjectGroup):
            for child in node.children:
                visit(child)

    visit(group)
    for name, leaf in sampler.leaves.items():
        if _centiseconds(leaf.end) <= _centiseconds(leaf.start):
            raise SceneCompileError(
                "lifetime vanishes on ASS centisecond grid",
                object_id=name,
                origin=leaf.node.origin,
            )
        birth = leaf.node.lifetime.start
        glow = sampler.glows.get(name)
        if isinstance(glow, GlowFunction):
            times.update(birth + t for t in glow.breakpoints)
        field = sampler.glow_materials.get(name)
        if field is not None:
            times.update(birth + t for t in field.breakpoints)
        partition = sampler.partitions.get(name)
        if partition is not None:
            times.update(birth + t for t in partition.breakpoints)
        owners = {node.id: node for node in (*leaf.parents, leaf.node)}
        for rule in sampler.scope_opacities.get(name, ()):
            times.update(
                owners[rule.owner].lifetime.start + t for t in rule.breakpoints
            )
    points = {start, end}
    points.update(_centiseconds(start / 100 + i / budget.fps) for i in range(1, frames))
    points.update(max(start, min(end, _centiseconds(t))) for t in times)
    if len(points) - 1 > settings.max_frames:
        raise SceneCompileError(
            "coverage frame budget exceeded after boundary splitting",
            object_id=group.id,
            origin=group.origin,
        )
    error = max((abs(t - _centiseconds(t) / 100) for t in times), default=0)
    return tuple(sorted(points)), error


def compile_coverage(
    document: Document,
    group: ObjectGroup,
    *,
    glows: Mapping[str, Glow | GlowFunction] | None = None,
    glow_materials: Mapping[str, PaintField] | None = None,
    components: Collection[str] = (),
    scope_opacities: Mapping[str, tuple[ScopeOpacity, ...]] | None = None,
    partitions: Mapping[str, CoveragePartition] | None = None,
    replace_records: Collection[int] = (),
    owner: str = "coverage",
    settings: RasterSettings = _DEFAULT_SETTINGS,
    budget: SceneBudget = _DEFAULT_BUDGET,
) -> CoverageResult:
    """Compile one self-contained group without modifying its input Document.

    Sources survive unless explicitly selected by record index. Recompiling with
    the same owner replaces that owner's generated events. Fill, stroke and
    explicit glow share coverage before blur; ordinary groups close alpha scopes.
    Configuration keys are object identities and must be remapped when copying.
    All output is standard ASS, sampled at script resolution and held on an ASS
    centisecond grid. Declared discontinuities split that grid before callbacks.
    """
    if not owner:
        raise ValueError("coverage owner must be nonempty")
    source = deepcopy(document)
    meta = Document.parse(source.dumps()).meta
    resolution = (meta.res_x, meta.res_y)
    scene = Scene(source, owner=owner)
    for index in replace_records:
        scene.replace_source(index)
    style = Style(
        name="KaraCoverage_" + sha256(owner.encode()).hexdigest()[:12],
        outline=0,
        shadow=0,
        align=7,
    )
    if (
        style.name in source.styles
        and source.styles[style.name].serialize() != style.serialize()
    ):
        raise SceneCompileError("coverage style collides with a different source style")
    sampler = SceneCoverageSampler(
        group,
        resolution=resolution,
        glows={} if glows is None else glows,
        glow_materials=glow_materials,
        components=components,
        scope_opacities=scope_opacities,
        partitions=partitions,
        settings=settings,
        budget=budget,
    )
    points, time_error = _sample_grid(sampler, settings, budget)
    origins = tuple(
        leaf.node.origin
        for leaf in sampler.leaves.values()
        if leaf.node.origin is not None
    )
    sources = tuple(dict.fromkeys(ref for origin in origins for ref in origin.sources))
    tracks = tuple(
        dict.fromkeys(track for origin in origins for track in origin.track_ids)
    )
    origin = group.origin or (
        EventOrigin(sources, "coverage group", tracks) if sources else None
    )
    previous: PositionedFrame | None = None
    pending: dict[str, Line] = {}
    count = characters = 0
    for left, right in zip(points, points[1:], strict=False):
        frame = sampler.frame((left + right) / 200)
        if frame is not None:
            frame = (
                frame[0],
                frame[1],
                quantize_frame(frame[2], settings.max_channel_error),
            )
        if frame == previous:
            for event in pending.values():
                event.end_time = right * 10
            continue
        previous = frame
        encoded = (
            ()
            if frame is None
            else encode_frame(
                frame[2],
                DisplayWindow(left * 10, right * 10),
                style=style.name,
                position=(frame[0], frame[1]),
                resolution=resolution,
                neutral_style=True,
                budget=sampler.raster_budget,
            )
        )
        if len(encoded) > budget.max_active:
            raise SceneCompileError(
                "coverage peak active budget exceeded", object_id=group.id
            )
        current: dict[str, Line] = {}
        for event in encoded:
            prior = pending.get(event.text)
            if prior is not None and prior.end_time == event.start_time:
                prior.end_time = event.end_time
                current[event.text] = prior
                continue
            current[event.text] = event
            count += 1
            characters += len(event.text)
            if count * 2 > budget.max_events or characters > settings.max_output_chars:
                raise SceneCompileError(
                    "coverage output budget exceeded", object_id=group.id
                )
            event.layer = group.layer
            scene.add(NativeEvent(f"{group.id}/pixel:{count}", event, origin))
        pending = current
    # Insert after source index selection; the compiler consumes those indices
    # before installing generated styles. Adding a style here would shift them.
    output = scene.compile(budget=budget)
    _insert_events(output.document, [], style)
    byte_count = len(output.document.dumps().encode("utf-8")) + 3
    if byte_count > budget.max_bytes:
        raise SceneCompileError(
            "coverage final byte budget exceeded", object_id=group.id
        )
    output = replace(
        output,
        byte_count=byte_count,
        max_time_quantization=max(output.max_time_quantization, time_error),
    )
    return CoverageResult(
        output,
        tuple((a + b) / 200 for a, b in zip(points, points[1:], strict=False)),
        settings.max_channel_error,
    )
