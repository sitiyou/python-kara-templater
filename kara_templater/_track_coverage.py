"""PreparedTrack → editable coverage components, before frame/ASS lowering."""

from dataclasses import dataclass, replace
from math import isclose

from ._scene_coverage import SceneCoverageSampler
from ._track_compiler import PreparedTrack
from ._track_raster import _patch
from ._track_scene import _text_object, _validate_target
from .behaviors import BoundProperty, sample_hierarchy, sample_properties
from .composition import Glow, Paint
from .coverage_animation import CoveragePartition, GlowFunction, ScopeOpacity
from .geometry import Vec2
from .material_animation import sample_materials
from .raster_settings import RasterSettings
from .scene import Lifetime, ObjectGroup, TextObject
from .scene_animation import VisualState
from .scene_output import SceneBudget
from .sources import EventOrigin
from .targets import VisualTarget
from .timeline import Region, union_regions


@dataclass(frozen=True)
class CoverageTrack:
    group: ObjectGroup
    resolution: tuple[int, int]
    components: tuple[str, ...]
    glows: dict[str, GlowFunction]
    partitions: dict[str, CoveragePartition]
    scope_opacities: dict[str, tuple[ScopeOpacity, ...]]
    diagnostics: tuple[str, ...]

    def sampler(
        self, *, settings: RasterSettings, budget: SceneBudget
    ) -> SceneCoverageSampler:
        return SceneCoverageSampler(
            self.group,
            resolution=self.resolution,
            glows=self.glows,
            components=self.components,
            partitions=self.partitions,
            scope_opacities=self.scope_opacities,
            settings=settings,
            budget=budget,
        )


def track_coverage(
    item_id: str,
    prepared: PreparedTrack,
    *,
    max_glow_blur: float,
    max_glow_border: float,
) -> CoverageTrack:
    """Keep Track's source components and scopes while making geometry editable.

    Declared glow bounds cover final script-pixel values, including animation
    scale. Native text decorations unsupported by editable TextObject fail early.
    Ownership fronts follow positive axis-aligned geometry; rotated/sheared fronts
    need a two-dimensional coverage partition and are explicitly diagnosed.
    """
    window = prepared.lyrics.window
    lifetime = Lifetime(window.start_ms / 1000, window.end_ms / 1000)
    if prepared.highlight_styles or prepared.overlap != "union":
        raise ValueError(
            "Track coverage supports union highlights with a shared paint; "
            "use native or editable output for per-highlight paints and priority/layer composition"
        )
    geometry = replace(
        prepared,
        properties={
            key: tuple(m for m in motions if m.property != "opacity")
            for key, motions in prepared.properties.items()
        },
    )
    grouped: dict[int, dict[str, list[TextObject]]] = {}
    glows: dict[str, GlowFunction] = {}
    partitions: dict[str, CoveragePartition] = {}
    scopes: dict[str, tuple[ScopeOpacity, ...]] = {}

    def scope_rule(owner: str, motions: tuple[BoundProperty, ...]) -> ScopeOpacity:
        points = tuple(
            sorted(
                {
                    (t - window.start_ms) / 1000
                    for m in motions
                    for t in (*m.interval, *m.breakpoints)
                    if window.start_ms <= t <= window.end_ms
                }
            )
        )

        def sample(time: float) -> float:
            return sample_properties(motions, window.start_ms + time * 1000).get(
                "opacity", 1
            )

        return ScopeOpacity(owner, sample, points)

    def emit(
        target: VisualTarget, paint: Paint, after: bool, unit_id: str
    ) -> TextObject:
        origin = EventOrigin(
            target.sources, "Track", tuple(track.id for track in target.tracks)
        )
        _validate_target(target, origin)
        node = _text_object(
            item_id,
            geometry,
            replace(target, paints=replace(target.paints, before=paint)),
            lifetime,
            origin,
            False,
        )
        node = replace(
            node, id=f"{item_id}/{target.id}/{'after' if after else 'before'}"
        )
        motions = prepared.properties.get(target.id, ())
        materials = prepared.materials.get(f"{item_id}/{target.id}", ())
        initial = Vec2(target.style.scale_x / 100, target.style.scale_y / 100)
        if initial.x <= 0 or initial.y <= 0:
            raise ValueError(
                f"{node.id}: coverage Track requires positive initial font scale"
            )

        def factor(state: VisualState) -> float:
            if (
                state.rotation
                or state.skew != Vec2()
                or min(state.scale.x, state.scale.y) <= 0
            ):
                raise ValueError(
                    "Track coverage fronts require positive axis-aligned geometry"
                )
            x, y = state.scale.x / initial.x, state.scale.y / initial.y
            if not isclose(x, y, rel_tol=1e-9, abs_tol=1e-9):
                raise ValueError(
                    "Track coverage appearance requires uniform geometry scale"
                )
            return x

        points = tuple(
            sorted(
                {
                    (t - window.start_ms) / 1000
                    for track in target.tracks
                    for part in track.passes
                    for fraction, _ in part.curve.knots
                    if window.start_ms
                    <= (t := part.start_ms + fraction * (part.end_ms - part.start_ms))
                    <= window.end_ms
                }
            )
        )

        def regions(state: VisualState, time: float) -> tuple[Region, ...]:
            scale = factor(state)
            output: list[Region] = []
            for track in target.tracks:
                for region in track.regions_at(window.start_ms + time * 1000):
                    left = -1e12 if region.left <= target.body.left else region.left
                    right = 1e12 if region.right >= target.body.right else region.right
                    output.append(
                        Region(
                            state.position.x + (left - target.box.center) * scale,
                            state.position.x + (right - target.box.center) * scale,
                        )
                    )
            return union_regions(output)

        if target.tracks:
            partitions[node.id] = CoveragePartition(
                regions,
                max(1, sum(len(track.passes) for track in target.tracks)),
                inside=after,
                breakpoints=points,
            )
        if paint.glow is not None:

            def halo(state: VisualState, time: float) -> Glow | None:
                values = sample_materials(materials, window.start_ms + time * 1000)
                result = _patch(paint, values).glow
                if result is None:
                    return None
                scale = factor(state)
                properties = sample_hierarchy(
                    tuple(m for m in motions if m.property != "opacity"),
                    window.start_ms + time * 1000,
                )
                blur = properties.get("glow_blur")
                return replace(
                    result,
                    border=result.border * scale,
                    blur=(result.blur if blur is None else blur) * scale,
                )

            knots = set(points)
            # Glow-only animations need their own discontinuities: the fill node
            # has no state clip when its channels are all unchanged.
            knots.update(
                (t - window.start_ms) / 1000
                for motion in motions
                for t in (*motion.interval, *motion.breakpoints)
                if window.start_ms <= t <= window.end_ms
            )
            knots.update(
                (t - window.start_ms) / 1000
                for material in materials
                for t in (
                    *material.interval,
                    *(frame[0] for frame in material.frames),
                    *(
                        material.numeric.breakpoints
                        if material.numeric is not None
                        else ()
                    ),
                )
                if window.start_ms <= t <= window.end_ms
            )
            glows[node.id] = GlowFunction(
                halo,
                max_blur=max_glow_blur,
                max_border=max_glow_border,
                breakpoints=tuple(sorted(knots)),
            )
        rules = tuple(
            scope_rule(owner, selected)
            for name, owner in (
                ("local", node.id),
                ("unit", unit_id),
                ("group", item_id),
            )
            if (
                selected := tuple(
                    m for m in motions if m.property == "opacity" and m.scope == name
                )
            )
        )
        if rules:
            scopes[node.id] = rules
        return node

    for target in prepared.lyrics.targets:
        unit = target.sources[0].unit_index
        if unit is None:
            raise ValueError("coverage Track requires a source unit identity")
        unit_id = f"{item_id}/unit:{unit}"
        reading = target.sources[0].segment_index if target.kind == "ruby" else None
        component = f"{unit_id}/{target.kind}:{reading}"
        members = grouped.setdefault(unit, {}).setdefault(component, [])
        members.append(emit(target, target.paints.before, False, unit_id))
        if target.tracks:
            members.append(emit(target, target.paints.after, True, unit_id))
    units: list[ObjectGroup] = []
    components: list[str] = []
    for unit, groups in grouped.items():
        children: list[ObjectGroup] = []
        for identity, members in groups.items():
            components.append(identity)
            children.append(
                ObjectGroup(
                    id=identity,
                    lifetime=lifetime,
                    children=tuple(members),
                    layer=len(children),
                )
            )
        units.append(
            ObjectGroup(
                id=f"{item_id}/unit:{unit}",
                lifetime=lifetime,
                children=tuple(children),
                layer=len(units),
            )
        )
    return CoverageTrack(
        ObjectGroup(id=item_id, lifetime=lifetime, children=tuple(units)),
        prepared.context.resolution,
        tuple(components),
        glows,
        partitions,
        scopes,
        prepared.lyrics.diagnostics,
    )
