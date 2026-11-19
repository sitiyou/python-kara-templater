"""Document-backed scene objects, independent of any lyric-specific frontend."""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Self

from .ass import Document, Line
from .coverage_animation import Coverage
from .geometry import Vec2, VectorPath, finite
from .object_references import StateReference
from .paint_fields import PaintActivity, PaintField
from .path_animation import GeometryAnimation
from .path_geometry import GeometryError
from .scene_animation import (
    AnimationClip,
    StateAnimation,
    VisualState,
    evaluate_clips,
    local_seconds,
    translate_clips,
    validate_clips,
)
from .sources import EventOrigin

if TYPE_CHECKING:
    from .scene_evaluation import SceneEvaluator
    from .scene_output import SceneBudget, SceneEstimate, SceneResult


@dataclass(frozen=True)
class Lifetime:
    """An absolute half-open seconds interval with 0 <= start < end.

    Parent lifetimes further restrict child visibility without changing local
    animation clocks.
    """

    start: float
    end: float

    def __post_init__(self) -> None:
        finite(self.start, self.end)
        if self.start < 0 or self.end <= self.start:
            raise ValueError("lifetime requires 0 <= start < end")

    def contains(self, time: float) -> bool:
        """Whether an absolute seconds time lies in this half-open lifetime."""
        return self.start <= time < self.end


@dataclass(frozen=True)
class RectangleFunction:
    """Pure signed-local-seconds rectangle bounds; None denotes an empty mask.

    The owning object validates breakpoint times against its absolute clock.
    """

    function: Callable[[float], tuple[float, float, float, float] | None]
    breakpoints: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        finite(*self.breakpoints)
        if not callable(self.function):
            raise ValueError("rectangle function requires a callable")

    def sample(self, time: float) -> tuple[float, float, float, float] | None:
        """Evaluate local-seconds bounds; None represents an empty rectangle mask."""
        bounds = self.function(time)
        if bounds is None:
            return None
        left, top, right, bottom = bounds
        finite(left, top, right, bottom)
        if left >= right or top >= bottom:
            raise ValueError("rectangle callback must return positive bounds or None")
        return bounds


@dataclass(frozen=True)
class RectangleKeyframes:
    """Known piecewise-linear rectangle bounds in signed local seconds.

    Each keyframe is (time, (left, top, right, bottom)). End values hold outside
    the key range. Two keys at the same time encode an instantaneous reset:
    the first is the left limit and the second takes effect at that time.
    Zero width or height is an empty mask, with its coordinates retained for
    interpolation. The owning object validates absolute breakpoint times.
    """

    keyframes: tuple[tuple[float, tuple[float, float, float, float]], ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "keyframes",
            tuple((time, tuple(bounds)) for time, bounds in self.keyframes),
        )
        if not self.keyframes:
            raise ValueError("rectangle keyframes cannot be empty")
        for index, (time, bounds) in enumerate(self.keyframes):
            finite(time, *bounds)
            left, top, right, bottom = bounds
            if left > right or top > bottom:
                raise ValueError("rectangle keyframes cannot have inverted bounds")
            if index and time < self.keyframes[index - 1][0]:
                raise ValueError("rectangle keyframe times must be nondecreasing")
            if index > 1 and time == self.keyframes[index - 2][0]:
                raise ValueError("rectangle resets require at most two keys at a time")

    @property
    def breakpoints(self) -> tuple[float, ...]:
        """Distinct local key times, including instantaneous reset boundaries."""
        return tuple(dict.fromkeys(time for time, _ in self.keyframes))

    def bounds_at(
        self, time: float, *, before: bool = False
    ) -> tuple[float, float, float, float]:
        """Evaluate bounds; before selects the left limit at a reset boundary."""
        finite(time)
        times = tuple(key[0] for key in self.keyframes)
        index = (bisect_left if before else bisect_right)(times, time)
        if index == 0:
            return self.keyframes[0][1]
        if index == len(times):
            return self.keyframes[-1][1]
        start, first = self.keyframes[index - 1]
        end, last = self.keyframes[index]
        progress = (time - start) / (end - start)
        return (
            first[0] + (last[0] - first[0]) * progress,
            first[1] + (last[1] - first[1]) * progress,
            first[2] + (last[2] - first[2]) * progress,
            first[3] + (last[3] - first[3]) * progress,
        )

    def sample(self, time: float) -> tuple[float, float, float, float] | None:
        """Evaluate the same mask protocol as RectangleFunction."""
        left, top, right, bottom = self.bounds_at(time)
        return None if left == right or top == bottom else (left, top, right, bottom)


@dataclass(frozen=True)
class RectangleClip:
    """A positive-area normal or inverse rectangle in screen or object-local space.

    Optional deformation evaluates local seconds and can produce an empty mask.
    """

    left: float
    top: float
    right: float
    bottom: float
    inverse: bool = False
    space: Literal["screen", "local"] = "screen"
    deform: RectangleFunction | RectangleKeyframes | None = None

    def __post_init__(self) -> None:
        if self.space not in ("screen", "local"):
            raise ValueError("clip space must be screen or local")
        finite(self.left, self.top, self.right, self.bottom)
        if self.left >= self.right or self.top >= self.bottom:
            raise ValueError("clip must have positive width and height")


@dataclass(frozen=True, kw_only=True)
class _CellWipeClip(RectangleClip):
    """Vertical cell traverse. Core times use the same local clock as the rectangle."""
    start: float
    end: float


@dataclass(frozen=True)
class VectorClip:
    """A filled mask; deform uses object-local seconds. None is an empty region.

    Empty normal masks hide the object; empty inverse masks reveal it entirely.
    Local coordinates are relative to the object's alignment anchor.
    """

    path: VectorPath
    inverse: bool = False
    space: Literal["screen", "local"] = "screen"
    deform: GeometryAnimation | None = None

    def __post_init__(self) -> None:
        if self.space not in ("screen", "local"):
            raise ValueError("clip space must be screen or local")
        if self.deform is not None:
            if type(self.deform.max_points) is not int or self.deform.max_points < 1:
                raise ValueError("clip animation requires a positive point bound")
            finite(*self.deform.breakpoints)


@dataclass(frozen=True, kw_only=True)
class VisualNode:
    """Common state, lifetime, animation, clip, material, reference, and source metadata for Scene visuals.

    lifetime controls visibility. clock_start optionally preserves an absolute
    local-time origin when visibility changes; otherwise the origin is
    lifetime.start. Earlier visibility gives callbacks negative local seconds;
    scheduled animations remain unstarted until their clip start.
    Copies shift both visibility and an explicit clock origin.
    Local evaluation is distinct from world-space SceneEvaluator queries.
    """

    id: str
    lifetime: Lifetime
    state: VisualState = VisualState()
    clock_start: float | None = None
    animations: tuple[AnimationClip, ...] = ()
    layer: int = 0
    origin: EventOrigin | None = None
    clip: RectangleClip | VectorClip | None = None
    material: PaintField | None = None
    reference: StateReference | None = None

    @property
    def time_origin(self) -> float:
        """Absolute seconds origin for local animation, geometry and paint clocks."""
        return self.lifetime.start if self.clock_start is None else self.clock_start

    def __post_init__(self) -> None:
        finite(self.time_origin)
        if not 0 <= self.time_origin <= self.lifetime.end:
            raise ValueError(
                "clock origin must be nonnegative and no later than display end"
            )
        if not self.id:
            raise ValueError("visual objects require a nonempty id")
        if type(self.layer) is not int:
            raise TypeError("layer must be an integer")
        if (
            isinstance(self.clip, (RectangleClip, VectorClip))
            and self.clip.deform is not None
            and any(
                t < -self.time_origin or t > self.lifetime.end - self.time_origin
                for t in self.clip.deform.breakpoints
            )
        ):
            raise ValueError("clip breakpoint outside object lifetime")
        if self.material is not None:
            finite(*self.material.breakpoints)
            if any(
                t < -self.time_origin or t > self.lifetime.end - self.time_origin
                for t in self.material.breakpoints
            ):
                raise ValueError("paint breakpoint outside object lifetime")
            if isinstance(self.material, PaintActivity):
                for interval in self.material.active_intervals:
                    if (
                        interval.start < -self.time_origin
                        or interval.end <= interval.start
                        or interval.end > self.lifetime.end - self.time_origin
                        or interval.start not in self.material.breakpoints
                        or interval.end not in self.material.breakpoints
                    ):
                        raise ValueError(
                            "paint activity must fit the lifetime and declare its endpoints as breakpoints"
                        )
        if self.reference is not None:
            finite(*self.reference.breakpoints)
            if any(
                clip.animation.channels & self.reference.channels
                for clip in self.animations
            ):
                raise ValueError("reference and local animation write the same channel")
        validate_clips(self.animations)
        for clip in self.animations:
            if clip.start < -self.time_origin - 1e-9:
                raise ValueError(
                    f"{self.id}: animation starts before absolute time zero"
                )
            if clip.end > self.lifetime.end - self.time_origin + 1e-9:
                raise ValueError(f"{self.id}: animation extends beyond lifetime")

    def at(self, time: float) -> VisualState:
        """Evaluate this object at absolute seconds using its local animation clock.

        Use SceneEvaluator for parent transforms and references.
        """
        finite(time)
        return evaluate_clips(
            self.state, self.animations, local_seconds(time, self.time_origin)
        )

    def animate(
        self,
        animation: StateAnimation,
        *,
        duration: float,
        at: float = 0,
        hold: bool = True,
        breakpoints: tuple[float, ...] = (),
    ) -> Self:
        """Return a new node with an animation bound at local seconds from birth.

        The same operation works on text, paths and groups. Existing clips are
        preserved; conflicting channels or a clip beyond the lifetime raise
        before changing anything. Use a timeline for longer schedules.
        """
        return replace(
            self,
            animations=(
                *self.animations,
                AnimationClip(at, duration, animation, hold, breakpoints),
            ),
        )

    def copy(self, *, id: str, offset: Vec2 | None = None, delay: float = 0) -> Self:
        """Independent immutable object; animation clocks stay relative to birth."""
        return replace(
            self,
            id=id,
            reference=None
            if self.reference is None
            else self.reference.shifted(delay).translated(
                Vec2() if offset is None else offset
            ),
            state=replace(
                self.state,
                position=self.state.position
                + (
                    Vec2()
                    if offset is None
                    or (
                        self.reference is not None
                        and "position" in self.reference.channels
                    )
                    else offset
                ),
            ),
            lifetime=Lifetime(self.lifetime.start + delay, self.lifetime.end + delay),
            clock_start=None if self.clock_start is None else self.clock_start + delay,
            animations=translate_clips(
                self.animations, Vec2() if offset is None else offset
            ),
        )

    def _retarget_copy(self, names: Mapping[str, str], delay: float) -> Self:
        """Retarget copied dependency metadata after the whole tree is known."""
        return replace(
            self,
            reference=None
            if self.reference is None
            else self.reference.retarget(names, delay),
        )


@dataclass(frozen=True, kw_only=True)
class TextObject(VisualNode):
    """A text drawing with family name, pixel font size, shaping style, alignment, and inherited visual state.

    Unsupported affine combinations can lower to glyph geometry with explicit
    budgets. Text is literal Unicode: braces and backslashes are displayed,
    not interpreted as ASS tags; newlines become hard line breaks. CR and NUL
    are rejected. Set scale_border to scale the outline radius along each glyph
    axis with the text. The default ASS outline radius uses script pixels.
    Set filled=False for outline-only text.
    For affine paths baked into screen coordinates, ASS approximates a sheared
    or tilted elliptical outline using its horizontal and vertical radii.
    """

    text: str
    font: str = "DejaVu Sans"
    font_size: float = 48
    bold: bool = False
    italic: bool = False
    spacing: float = 0
    alignment: int = 7
    encoding: int = 1
    scale_border: bool = False
    filled: bool = True

    def __post_init__(self) -> None:
        super().__post_init__()
        finite(self.font_size, self.spacing)
        if (
            self.font_size <= 0
            or not self.font
            or any(c in self.font for c in "{}\\\r\n")
        ):
            raise ValueError("font needs a safe name and positive size")
        if type(self.alignment) is not int or not 1 <= self.alignment <= 9:
            raise ValueError("ASS alignment must be in 1..9")
        if type(self.encoding) is not int or self.encoding < 0:
            raise ValueError("font encoding must be a nonnegative integer")
        if any(c in self.text for c in "\r\x00"):
            raise ValueError("TextObject text cannot contain CR or NUL")


@dataclass(frozen=True, kw_only=True)
class PathObject(VisualNode):
    """A visual VectorPath drawing with state, lifetime, and optional geometry deformation.

    Coordinates are local to its local origin and parent transforms. Set filled=False
    for an outline-only drawing; border sets the outline radius in script pixels.
    """

    path: VectorPath
    deform: GeometryAnimation | None = None
    filled: bool = True

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.deform is not None:
            if type(self.deform.max_points) is not int or self.deform.max_points < 1:
                raise ValueError("geometry animation requires a positive point bound")
            finite(*self.deform.breakpoints)
            if any(
                local_seconds(t, 0) < local_seconds(0, self.time_origin)
                or local_seconds(t, 0)
                > local_seconds(self.lifetime.end, self.time_origin)
                for t in self.deform.breakpoints
            ):
                raise ValueError("geometry breakpoint outside object lifetime")

    def path_at(self, time: float) -> VectorPath | None:
        """Return the original or deformed path at absolute seconds, using the object birth as local origin."""
        finite(time)
        if self.deform is None:
            return self.path
        path = self.deform.sample(self.path, local_seconds(time, self.time_origin))
        if path is not None and path.point_count > self.deform.max_points:
            raise GeometryError("geometry callback exceeded its declared point bound")
        return path


@dataclass(frozen=True, kw_only=True)
class ObjectGroup(VisualNode):
    """Local child coordinates; absolute lifetimes intersect parent lifetimes.

    Opacity is inherited per child, not offscreen compositing of the group.
    Group paint is not inherited; use explicit child appearances instead.
    """

    children: tuple[SceneObject, ...]
    coverage: Coverage | None = None

    def _retarget_copy(self, names: Mapping[str, str], delay: float) -> Self:
        copied = super()._retarget_copy(names, delay)
        return replace(
            copied,
            coverage=None if self.coverage is None else self.coverage.retarget(names),
        )

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.material is not None:
            raise ValueError("group paint is not inherited; apply material to children")
        if (
            self.state.fill != VisualState().fill
            or self.state.outline != VisualState().outline
            or self.state.border
            or self.state.blur
            or self.state.shadow != Vec2()
        ):
            raise ValueError(
                "group paint is not inherited; configure child appearances"
            )
        supported = frozenset(("position", "scale", "rotation", "skew", "opacity"))
        if self.reference is not None and not self.reference.channels <= supported:
            raise ValueError(
                "group references support position, scale, rotation, skew, opacity"
            )
        if any(not clip.animation.channels <= supported for clip in self.animations):
            raise ValueError(
                "group animations support position, scale, rotation, skew, opacity"
            )

    def copy(self, *, id: str, offset: Vec2 | None = None, delay: float = 0) -> Self:
        """Copy the full hierarchy with unique identities, delayed local clocks, and remapped internal references."""
        names: dict[str, str] = {}

        def clone(
            node: SceneObject, identity: str, shift: Vec2 | None = None
        ) -> SceneObject:
            copied = VisualNode.copy(node, id=identity, offset=shift, delay=delay)
            names[node.id] = copied.id
            if isinstance(node, ObjectGroup) and isinstance(copied, ObjectGroup):
                copied = replace(
                    copied,
                    children=tuple(
                        clone(
                            child,
                            child.id
                            if identity == node.id
                            else f"{identity}/{child.id}",
                        )
                        for child in node.children
                    ),
                )
            return copied

        copied = clone(self, id, offset)
        assert isinstance(copied, ObjectGroup)

        def remap(node: SceneObject) -> SceneObject:
            result = node._retarget_copy(names, delay)
            if isinstance(result, ObjectGroup):
                result = replace(
                    result, children=tuple(remap(child) for child in result.children)
                )
            return result

        return replace(
            self,
            state=copied.state,
            id=copied.id,
            lifetime=copied.lifetime,
            clock_start=copied.clock_start,
            animations=copied.animations,
            reference=copied.reference,
            children=tuple(remap(child) for child in copied.children),
        )._retarget_copy(names, delay)


type SceneObject = TextObject | PathObject | ObjectGroup


@dataclass(frozen=True)
class NativeEvent:
    """Already-lowered Dialogue, including historical empty/negative intervals.

    Native timing follows Document serialization (negative times clamp to zero),
    rather than the positive display lifetime required by new visual objects.
    """

    id: str
    event: Line
    origin: EventOrigin | None = None

    def __post_init__(self) -> None:
        if not self.id or self.event.comment:
            raise ValueError("native nodes require an id and a Dialogue event")
        finite(self.event.start_time, self.event.end_time)


@dataclass
class Scene:
    """A Document-backed composition of visual objects and already-lowered NativeEvents.

    add and source replacement configure generation; compile returns a new standard
    ASS Document and reports.
    """

    document: Document
    objects: list[SceneObject | NativeEvent] = field(default_factory=list)
    replace_records: set[int] = field(default_factory=set)
    owner: str = "scene"

    def add(self, *objects: SceneObject | NativeEvent) -> Self:
        """Append typed visual/native objects and return this Scene for composition."""
        self.objects.extend(objects)
        return self

    def replace_source(self, record_index: int) -> None:
        """Mark a valid source event record for retention as a Comment during compilation."""
        if not 0 <= record_index < len(self.document.records) or not isinstance(
            self.document.records[record_index], Line
        ):
            raise ValueError("source replacement requires an event record index")
        self.replace_records.add(record_index)

    def evaluator(self) -> SceneEvaluator:
        """Construct a seekable world-space evaluator for this scene hierarchy and its references."""
        from .scene_evaluation import SceneEvaluator

        return SceneEvaluator(self)

    def export_hook(
        self, path: str | Path, *, fps: int = 60, start: float = 0,
        duration: float | None = None,
    ) -> None:
        """Write a standalone libplacebo .hook for a constant-frame-rate video.

        Export animation parameters and sample unsupported intervals on the fps grid.
        Start is frame-aligned in seconds. mpv uses media PTS;
        the sequential clock in FFmpeg begins at start. Duration defaults to the remaining Scene;
        subsequent frames pass through. Render at the exported fps on an opaque
        SDR video with matching aspect ratio. Includes glyph masks and effects.
        """
        from ._gpu_hook import export_hook

        export_hook(self, Path(path), fps, start, duration)

    def enhance(self, fallback: Document, *, fps: int = 60) -> Document:
        """Attach sampled GPU effects to an explicit ordinary-ASS fallback.

        Returns a new Document with versioned private Comment records. Ordinary
        players display fallback unchanged; render_enhanced replaces its visual
        presentation with this complete Scene. Resolution must match. Existing
        Python callbacks run at export only; portable data stores reusable glyph
        masks and numeric draws at integer fps (1..240), not executable code.
        This initial backend supports text/static paths, affine animation, normal
        local/screen rectangle clips and continuous LinearGradient. Unsupported
        materials, native events, coverage groups, inherited/vector/inverse clips
        and deformed paths raise. Export has bounded frame/mask/payload budgets.
        """
        from ._gpu_bundle import encode_scene

        return encode_scene(self, fallback, fps=fps)

    def compile(
        self,
        *,
        budget: SceneBudget | None = None,
        native_tweens: bool = False,
        on_estimate: Callable[[SceneEstimate], None] | None = None,
    ) -> SceneResult:
        """Compile a new ASS Document and reports under explicit Scene budgets.

        Eligible continuous Tween lowering is opt-in.
        on_estimate runs after preflight and before frame callbacks; raising
        cancels compilation without changing the scene or source document.
        """
        from .scene_output import SceneBudget, compile_scene

        return compile_scene(
            self,
            budget=SceneBudget() if budget is None else budget,
            native_tweens=native_tweens,
            on_estimate=on_estimate,
        )
