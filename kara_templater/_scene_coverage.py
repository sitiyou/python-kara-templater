"""Evaluate editable scene geometry through the shared coverage-material core.

Internal migration foundation: leaves own fill/stroke/glow components by default.
Explicit component groups combine material contributions before closing their
opacity scope; ordinary groups composite completed children as atomic subtrees.
"""

from collections.abc import Collection, Mapping
from copy import copy
from dataclasses import dataclass, replace
from math import ceil
from typing import Literal

from . import _metrics
from ._coverage_stack import CoverageStack, compose_stacks
from ._material_composition import MaterialLayer, compose_material_layers
from ._material_raster import CoverageMask, MaterialBand
from ._raster import (
    PositionedFrame,
    RasterBudget,
    RasterCanvas,
    compose_frames,
    crop_frame,
)
from ._scene_clipping import ClipResolver
from .ass import Document, Style
from .composition import Color, Glow
from .coverage_animation import CoveragePartition, GlowFunction, ScopeOpacity
from .geometry import Vec2, VectorPath, finite
from .paint_fields import LinearGradient, PaintBand, PaintField
from .raster_settings import RasterSettings
from .scene import (
    ObjectGroup,
    PathObject,
    RectangleClip,
    Scene,
    SceneObject,
    VectorClip,
)
from .scene_animation import VisualState, local_seconds
from .scene_evaluation import SceneEvaluator
from .scene_output import (
    SceneBudget,
    SceneCompileError,
    _Leaf,
    _leaves,
    _painted_events,
)
from .timeline import Region


@dataclass(frozen=True)
class _LeafMaterials:
    fills: tuple[MaterialLayer, ...]
    strokes: tuple[MaterialLayer, ...]
    glows: tuple[MaterialLayer, ...]


class SceneCoverageSampler:
    """Seekable source snapshot; no frame clock or ASS output policy of its own.

    Geometry and masks use the standard Scene compiler. Glow is an explicit
    per-leaf appearance, distinct from VisualState.blur. Fields currently color
    fill/stroke; glow has an independent color or paint field. Finite-kernel
    overscan preserves offscreen contributions until final viewport cropping.
    Native events and opacity-writing references are
    rejected, rather than assigned invented component ownership.

    components names disjoint ObjectGroups whose descendants form one material
    component. Intermediate groups supply geometry, exposure and contribution
    opacity, rather than separate compositing boundaries. Same-role fragments
    add with intrinsic coverage normalization; nested components are rejected.
    Ordinary sibling components still use their declared group layer order.
    """

    def __init__(
        self,
        group: ObjectGroup,
        *,
        resolution: tuple[int, int],
        glows: Mapping[str, Glow | GlowFunction],
        glow_materials: Mapping[str, PaintField] | None = None,
        components: Collection[str] = (),
        scope_opacities: Mapping[str, tuple[ScopeOpacity, ...]] | None = None,
        partitions: Mapping[str, CoveragePartition] | None = None,
        settings: RasterSettings,
        budget: SceneBudget,
        evaluator: SceneEvaluator | None = None,
        exclude_root_opacity: bool = False,
    ) -> None:
        self.group, self.resolution = group, resolution
        self.exclude_root_opacity = exclude_root_opacity
        self.components = frozenset(components)
        self.scope_opacities: dict[str, tuple[ScopeOpacity, ...]] = (
            {}
            if scope_opacities is None
            else {name: tuple(weights) for name, weights in scope_opacities.items()}
        )
        self.partitions = {} if partitions is None else dict(partitions)
        self.glows = dict(glows)
        self.glow_materials = {} if glow_materials is None else dict(glow_materials)
        self.budget = budget
        self.raster_budget = RasterBudget(
            max_pixels=settings.max_pixels,
            max_images=settings.max_images,
            max_events=settings.max_frame_events,
            max_rectangles=settings.max_rectangles,
            max_path_chars=settings.max_frame_chars,
        )
        self.raster_budget.check_pixels(*resolution)
        self.scene = Scene(
            Document.create(width=resolution[0], height=resolution[1])
        ).add(group)
        self.evaluator = SceneEvaluator(self.scene) if evaluator is None else evaluator
        leaves, _, _, _ = _leaves(self.scene, self.evaluator, collect_coverage=False)
        if len(leaves) * 3 > budget.max_events:
            raise ValueError("coverage geometry event budget exceeded")
        self.leaves = {leaf.node.id: leaf for leaf in leaves}
        groups: set[str] = set()
        visual_ids: set[str] = set()

        def validate_components(node: SceneObject, component: str | None) -> None:
            if not isinstance(node, ObjectGroup):
                visual_ids.add(node.id)
                return
            if node is not group and node.coverage is not None:
                raise SceneCompileError(
                    "nested coverage declarations are not supported", object_id=node.id
                )
            groups.add(node.id)
            if node.id in self.components:
                if component is not None:
                    raise SceneCompileError(
                        "coverage components cannot nest",
                        object_id=node.id,
                        origin=node.origin,
                    )
                component = node.id
            for child in node.children:
                validate_components(child, component)

        validate_components(group, None)
        if self.components - groups:
            raise ValueError("coverage components must address object groups")
        if self.partitions.keys() - visual_ids:
            raise ValueError("coverage partition must address a visual leaf")
        if self.scope_opacities.keys() - visual_ids:
            raise ValueError("scope opacity must address a visual leaf")
        if self.glows.keys() - visual_ids:
            raise ValueError("coverage glow must address a visual leaf")
        if self.glow_materials.keys() - self.glows.keys():
            raise ValueError("glow materials require a configured glow")
        # Parent lifetimes may hide declared descendants completely. Validate
        # their identities, then exclude them from sampling and resource costs.
        self.glows = {
            name: value for name, value in self.glows.items() if name in self.leaves
        }
        self.glow_materials = {
            name: value
            for name, value in self.glow_materials.items()
            if name in self.leaves
        }
        self.partitions = {
            name: value
            for name, value in self.partitions.items()
            if name in self.leaves
        }
        self.scope_opacities = {
            name: value
            for name, value in self.scope_opacities.items()
            if name in self.leaves
        }
        maximum_blur = max(
            (
                glow.max_blur if isinstance(glow, GlowFunction) else glow.blur
                for glow in self.glows.values()
            ),
            default=0,
        )
        if maximum_blur > 100:
            raise ValueError("coverage glow blur must be in 0..100 ASS pixels")
        maximum_border = max(
            (
                glow.max_border if isinstance(glow, GlowFunction) else glow.border
                for glow in self.glows.values()
            ),
            default=0,
        )
        self.overscan = _metrics.blur_padding(maximum_blur)
        padding = 2 * self.overscan + ceil(maximum_border)
        self.raster_budget.check_pixels(
            resolution[0] + 2 * padding, resolution[1] + 2 * padding
        )
        if any(self.scope_opacities.values()):
            planes = max((len(leaf.parents) + 2 for leaf in leaves), default=1)
            if (resolution[0] + 2 * padding) * (
                resolution[1] + 2 * padding
            ) * planes > settings.max_pixels:
                raise ValueError("coverage opacity plane pixel budget exceeded")
        for leaf in leaves:
            owners = {node.id: node for node in (*leaf.parents, leaf.node)}
            weights = self.scope_opacities.get(leaf.node.id, ())
            if len({weight.owner for weight in weights}) != len(weights):
                raise SceneCompileError(
                    "duplicate opacity scope",
                    object_id=leaf.node.id,
                    origin=leaf.node.origin,
                )
            for weight in weights:
                owner = owners.get(weight.owner)
                if owner is None or any(
                    time < -owner.time_origin
                    or time > owner.lifetime.end - owner.time_origin
                    for time in weight.breakpoints
                ):
                    raise SceneCompileError(
                        "opacity scope must be an ancestor with valid local breakpoints",
                        object_id=leaf.node.id,
                        origin=leaf.node.origin,
                    )
            glow = self.glows.get(leaf.node.id)
            if isinstance(glow, GlowFunction) and any(
                t < -leaf.node.time_origin
                or t > leaf.node.lifetime.end - leaf.node.time_origin
                for t in glow.breakpoints
            ):
                raise SceneCompileError(
                    "glow breakpoint outside object lifetime",
                    object_id=leaf.node.id,
                    origin=leaf.node.origin,
                )
            if isinstance(glow, GlowFunction) and glow.required_interval is not None:
                interval = glow.required_interval
                if (
                    interval.start < -leaf.node.time_origin
                    or interval.end > leaf.node.lifetime.end - leaf.node.time_origin
                ):
                    raise SceneCompileError(
                        "required glow interval outside object lifetime",
                        object_id=leaf.node.id,
                        origin=leaf.node.origin,
                    )
            for node in (*leaf.parents, leaf.node):
                if node.reference is not None and "opacity" in node.reference.channels:
                    raise SceneCompileError(
                        "coverage opacity references require explicit scope ownership",
                        object_id=node.id,
                        origin=node.origin,
                    )
            node = leaf.node
            partition = self.partitions.get(node.id)
            if partition is not None:
                if any(
                    t < -node.time_origin or t > node.lifetime.end - node.time_origin
                    for t in partition.breakpoints
                ):
                    raise SceneCompileError(
                        "partition breakpoint outside object lifetime",
                        object_id=node.id,
                        origin=node.origin,
                    )
                fields = (node.material, self.glow_materials.get(node.id))
                if any(field is not None and field.axis != "x" for field in fields):
                    raise SceneCompileError(
                        "horizontal ownership partitions require horizontal color fields",
                        object_id=node.id,
                        origin=node.origin,
                    )
                bound = max(
                    field.max_bands if field is not None else 1 for field in fields
                ) * (2 * partition.max_regions + 1)
                if bound > settings.max_images:
                    raise SceneCompileError(
                        "coverage partition band budget exceeded",
                        object_id=node.id,
                        origin=node.origin,
                    )
            for material in (node.material, self.glow_materials.get(node.id)):
                if material is None:
                    continue
                finite(*material.breakpoints)
                if material.axis not in ("x", "y") or any(
                    t < -node.time_origin or t > node.lifetime.end - node.time_origin
                    for t in material.breakpoints
                ):
                    raise SceneCompileError(
                        "invalid coverage material axis or lifetime",
                        object_id=node.id,
                        origin=node.origin,
                    )
                if (
                    type(material.max_bands) is not int
                    or not 1 <= material.max_bands <= budget.max_bands
                ):
                    raise SceneCompileError(
                        "coverage material band budget exceeded",
                        object_id=node.id,
                        origin=node.origin,
                    )
            if isinstance(node, PathObject):
                bound = (
                    node.path.point_count
                    if node.deform is None
                    else max(node.path.point_count, node.deform.max_points)
                )
                if bound > budget.max_path_points:
                    raise SceneCompileError(
                        "coverage path point budget exceeded",
                        object_id=node.id,
                        origin=node.origin,
                    )
        self.clips = ClipResolver(
            self.evaluator, budget.max_path_points, budget.max_boolean_work
        )
        self.outlines: dict[str, VectorPath | None] = {}

    def _mask(
        self,
        leaf: _Leaf,
        state: VisualState,
        time: float,
        *,
        border: float,
        kind: Literal["fill", "stroke", "glow"],
    ) -> CoverageMask | None:
        path = leaf.node.path_at(time) if isinstance(leaf.node, PathObject) else None
        if isinstance(leaf.node, PathObject) and path is None:
            return None
        resolved = self.clips.combine((*leaf.parents, leaf.node), time, state)
        padding = self.overscan
        offset = Vec2(padding, padding)
        clip = resolved.clip
        if isinstance(clip, RectangleClip):
            clip = replace(
                clip,
                left=clip.left + padding,
                top=clip.top + padding,
                right=clip.right + padding,
                bottom=clip.bottom + padding,
            )
        elif isinstance(clip, VectorClip):
            clip = replace(clip, path=clip.path.map(lambda point: point + offset))
        resolved = replace(resolved, clip=clip)
        white = Color(255, 255, 255)
        mask_state = replace(
            state,
            position=state.position + offset,
            fill=white,
            outline=white,
            border=border,
            blur=0,
            shadow=Vec2(),
            opacity=1,
        )
        width, height = (value + 2 * padding for value in self.resolution)
        style = Style(name="Coverage", outline=0, shadow=0)
        painted = _painted_events(
            replace(leaf, node=replace(leaf.node, material=None)),
            mask_state,
            0,
            100,
            style.name,
            width,
            height,
            time,
            path=path,
            budget=self.budget,
            outlines=self.outlines,
            clips=self.clips,
            resolved_mask=resolved,
        )
        document = Document.create(width=width, height=height, styles=(style,))
        document.records.extend(painted.events)
        images = _metrics.rasterize(
            document.dumps(),
            0,
            width,
            height,
            self.raster_budget.max_pixels,
            self.raster_budget.max_images,
        )
        selected = tuple(
            image
            for image in images
            if kind == "glow" or image[4] == (1 if kind == "stroke" else 0)
        )
        if not selected:
            return None
        left, top = min(i[0] for i in selected), min(i[1] for i in selected)
        right, bottom = (
            max(i[0] + i[2] for i in selected),
            max(i[1] + i[3] for i in selected),
        )
        canvas = RasterCanvas(right - left, bottom - top, budget=self.raster_budget)
        for x, y, w, h, role, color, data in selected:
            canvas.over((x - left, y - top, w, h, role, color, data))
        return CoverageMask(
            left - padding,
            top - padding,
            right - left,
            bottom - top,
            canvas.finish().rgba[3::4],
        )

    def _leaf_materials(
        self, leaf: _Leaf, time: float, weights: tuple[float, ...] = (1,)
    ) -> _LeafMaterials:
        state = leaf.at(time)
        if state.blur or state.shadow != Vec2():
            raise ValueError(
                "coverage leaves require explicit glow and no native blur/shadow"
            )

        def sample_field(
            field: PaintField | None, base: VisualState
        ) -> tuple[PaintBand, ...]:
            if isinstance(field, LinearGradient) and field.space == "local":
                raise ValueError(
                    "local gradients currently require ordinary ASS compilation, not coverage materials"
                )
            start = -self.overscan
            limit = (
                self.resolution[1 if field is not None and field.axis == "y" else 0]
                + self.overscan
            )
            bands = (
                (PaintBand(start, limit, base.fill, base.outline),)
                if field is None
                else field.bands(
                    start, limit, local_seconds(time, leaf.node.time_origin), base
                )
            )
            if field is not None and len(bands) > field.max_bands:
                raise ValueError("paint field exceeded its declared band bound")
            previous = start
            for band in bands:
                if (
                    type(band.start) is not int
                    or type(band.end) is not int
                    or band.start != previous
                    or not previous < band.end <= limit
                ):
                    raise ValueError(
                        "paint bands must partition the screen with integer boundaries"
                    )
                previous = band.end
            if previous != limit:
                raise ValueError("paint bands must cover the screen")
            return bands

        bands = sample_field(leaf.node.material, state)
        ownership = self.partitions.get(leaf.node.id)
        regions = (
            ()
            if ownership is None
            else ownership.sample(state, local_seconds(time, leaf.node.time_origin))
        )

        def paint(
            kind: Literal["fill", "stroke", "glow"],
            border: float,
            glow: Glow | None = None,
        ) -> tuple[MaterialLayer, ...]:
            mask = self._mask(leaf, state, time, border=border, kind=kind)
            if mask is None:
                return ()
            field = (
                leaf.node.material
                if glow is None
                else self.glow_materials.get(leaf.node.id)
            )
            axis = "x" if field is None else field.axis
            start, end = (
                (mask.left, mask.left + mask.width)
                if axis == "x"
                else (mask.top, mask.top + mask.height)
            )
            selected = (
                bands
                if glow is None
                else sample_field(
                    field, replace(state, fill=glow.color, outline=glow.color)
                )
            )
            partition = tuple(
                MaterialBand(
                    Region(max(start, band.start), min(end, band.end)),
                    band.fill if kind != "stroke" else band.outline,
                    1 if glow is None else glow.opacity,
                )
                for band in selected
                if max(start, band.start) < min(end, band.end)
            )
            if ownership is not None:
                split: list[MaterialBand] = []
                for band in partition:
                    cuts = sorted(
                        {
                            band.region.left,
                            band.region.right,
                            *(
                                max(band.region.left, min(band.region.right, value))
                                for region in regions
                                for value in (region.left, region.right)
                            ),
                        }
                    )
                    for left, right in zip(cuts, cuts[1:], strict=False):
                        owned = (
                            any(
                                region.left <= (left + right) / 2 < region.right
                                for region in regions
                            )
                            == ownership.inside
                        )
                        split.append(
                            MaterialBand(
                                Region(left, right),
                                band.color,
                                band.opacity if owned else 0,
                            )
                        )
                partition = tuple(split)
            return (
                MaterialLayer(
                    mask,
                    partition,
                    weights=weights,
                    blur_radius=0 if glow is None else glow.blur,
                    axis=axis,
                ),
            )

        appearance = self.glows.get(leaf.node.id)
        glow = (
            appearance.sample(state, local_seconds(time, leaf.node.time_origin))
            if isinstance(appearance, GlowFunction)
            else appearance
        )
        return _LeafMaterials(
            fills=paint("fill", 0),
            strokes=paint("stroke", state.border) if state.border else (),
            glows=paint("glow", glow.border, glow) if glow is not None else (),
        )

    def _component(self, node: SceneObject, time: float) -> PositionedFrame | None:
        members: list[tuple[_Leaf, float]] = []

        def collect(child: SceneObject, opacity: float) -> None:
            if not child.lifetime.contains(time):
                return
            opacity *= child.at(time).opacity
            if isinstance(child, ObjectGroup):
                for descendant in child.children:
                    collect(descendant, opacity)
            elif (leaf := self.leaves.get(child.id)) is not None:
                members.append((leaf, opacity))

        if isinstance(node, ObjectGroup):
            for child in node.children:
                collect(child, 1)
            outer_opacity = self._opacity(node, time)
        else:
            collect(node, 1)
            outer_opacity = 1
        if not members:
            return None
        # Identity defines the component. Numeric equality only selects the
        # equivalent fast path within this already-declared ownership scope.
        uniform = len({opacity for _, opacity in members}) == 1
        materials: list[_LeafMaterials] = []
        for leaf, opacity in members:
            try:
                materials.append(
                    self._leaf_materials(leaf, time, (1,) if uniform else (1, opacity))
                )
            except Exception as error:
                if isinstance(error, SceneCompileError):
                    raise
                raise SceneCompileError(
                    str(error), object_id=leaf.node.id, origin=leaf.node.origin
                ) from error
        planes = self._compose_materials(materials)
        if not planes:
            return None
        # The intrinsic plane occludes hidden roles; close the component only
        # after fill/stroke/glow have combined. Its siblings see weighted alpha.
        return compose_frames(
            (planes[-1],),
            opacity=outer_opacity * (members[0][1] if uniform else 1),
            budget=self.raster_budget,
        )

    def _compose_materials(self, materials: list[_LeafMaterials]) -> CoverageStack:
        return compose_material_layers(
            fills=tuple(layer for material in materials for layer in material.fills),
            strokes=tuple(
                layer for material in materials for layer in material.strokes
            ),
            glows=tuple(layer for material in materials for layer in material.glows),
            budget=self.raster_budget,
        )

    def _opacity(self, node: SceneObject, time: float) -> float:
        # Native lowering factors out only the final composition alpha. Keep the
        # evaluator untouched: author callbacks still observe the original state.
        if self.exclude_root_opacity and node.id == self.group.id:
            return 1
        return node.at(time).opacity

    def _weighted_frame(self, time: float) -> PositionedFrame | None:
        def opacity(leaf: _Leaf, owner: SceneObject) -> float:
            value = owner.at(time).opacity
            for weight in self.scope_opacities.get(leaf.node.id, ()):
                if weight.owner == owner.id:
                    value *= weight.sample(local_seconds(time, owner.time_origin))
            return value

        def visit(node: SceneObject, parents: tuple[ObjectGroup, ...]) -> CoverageStack:
            if not node.lifetime.contains(time):
                return ()
            try:
                if isinstance(node, ObjectGroup) and node.id not in self.components:
                    children = tuple(
                        stack
                        for child in sorted(
                            node.children, key=lambda child: child.layer
                        )
                        if (stack := visit(child, (*parents, node)))
                    )
                    return compose_stacks(
                        children, additive=False, budget=self.raster_budget
                    )[1:]
                materials: list[_LeafMaterials] = []

                def collect(
                    child: SceneObject, containers: tuple[ObjectGroup, ...]
                ) -> None:
                    if not child.lifetime.contains(time):
                        return
                    if isinstance(child, ObjectGroup):
                        for descendant in child.children:
                            collect(descendant, (*containers, child))
                        return
                    leaf = self.leaves.get(child.id)
                    if leaf is None:
                        return
                    try:
                        value = opacity(leaf, child)
                        for owner in reversed(containers):
                            value *= opacity(leaf, owner)
                        weights = [1.0, value]
                        for owner in reversed(parents):
                            value *= opacity(leaf, owner)
                            weights.append(value)
                        materials.append(
                            self._leaf_materials(leaf, time, tuple(weights))
                        )
                    except Exception as error:
                        if isinstance(error, SceneCompileError):
                            raise
                        raise SceneCompileError(
                            str(error), object_id=child.id, origin=child.origin
                        ) from error

                collect(node, ())
                # Close this component while retaining ancestor-weighted planes.
                return self._compose_materials(materials)[1:]
            except Exception as error:
                if isinstance(error, SceneCompileError):
                    raise
                raise SceneCompileError(
                    str(error), object_id=node.id, origin=node.origin
                ) from error

        result = visit(self.group, ())
        return None if not result else crop_frame(result[-1], self.resolution)

    def frame(self, time: float) -> PositionedFrame | None:
        finite(time)
        if not self.group.lifetime.contains(time):
            return None
        # Match the finite kernel's actual support and alignment for this frame.
        # Keep evaluated appearances on a query-local copy, never on the sampler.
        evaluated: dict[str, Glow | GlowFunction] = {}
        radius = 0.0
        for identity, appearance in self.glows.items():
            leaf = self.leaves[identity]
            if not leaf.start <= time < leaf.end:
                continue
            try:
                glow = (
                    appearance.sample(
                        leaf.at(time), local_seconds(time, leaf.node.time_origin)
                    )
                    if isinstance(appearance, GlowFunction)
                    else appearance
                )
            except Exception as error:
                raise SceneCompileError(
                    str(error), object_id=identity, origin=leaf.node.origin
                ) from error
            if glow is not None:
                evaluated[identity] = glow
                radius = max(radius, glow.blur)
        sampled = copy(self)
        sampled.glows = evaluated
        sampled.overscan = _metrics.blur_padding(radius)
        return sampled._frame(time)

    def _frame(self, time: float) -> PositionedFrame | None:
        if any(self.scope_opacities.values()):
            return self._weighted_frame(time)

        def visit(node: SceneObject) -> PositionedFrame | None:
            if not node.lifetime.contains(time):
                return None
            try:
                if isinstance(node, ObjectGroup) and node.id not in self.components:
                    children = tuple(
                        frame
                        for child in sorted(
                            node.children, key=lambda child: child.layer
                        )
                        if (frame := visit(child)) is not None
                    )
                    return compose_frames(
                        children,
                        opacity=self._opacity(node, time),
                        budget=self.raster_budget,
                    )
                return self._component(node, time)
            except Exception as error:
                if isinstance(error, SceneCompileError):
                    raise
                raise SceneCompileError(
                    str(error), object_id=node.id, origin=node.origin
                ) from error

        result = visit(self.group)
        return None if result is None else crop_frame(result, self.resolution)
