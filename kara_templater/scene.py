"""Document-backed scene objects, independent of any lyric-specific frontend."""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Self

from .ass import Document, Line
from .geometry import Vec2, VectorPath, finite
from .object_references import StateReference
from .paint_fields import (
    Extrusion,
    LinearGradient,
    MaterialClip,
    PaintInput,
    PaintValue,
    ShaderPaint,
)
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
    from .output.ass_export import AssBudget, AssEstimate, AssResult
    from .scene_evaluation import SceneEvaluator


class SceneCompileError(ValueError):
    """An invalid scene or exceeded compilation limit with object_id and optional source origin.

    Callback causes remain available for diagnosis.
    """

    def __init__(
        self, message: str, *, object_id: str = "", origin: EventOrigin | None = None
    ) -> None:
        super().__init__(f"{object_id}: {message}" if object_id else message)
        self.object_id = object_id
        self.origin = origin
        if origin is not None:
            self.add_note(f"effect={origin.effect}; sources={origin.sources!r}")


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

    @cached_property
    def breakpoints(self) -> tuple[float, ...]:
        """Distinct local key times, including instantaneous reset boundaries."""
        return tuple(dict.fromkeys(time for time, _ in self.keyframes))

    def bounds_at(
        self, time: float, *, before: bool = False
    ) -> tuple[float, float, float, float]:
        """Evaluate bounds; before selects the left limit at a reset boundary."""
        finite(time)
        times = tuple(key[0] for key in self.keyframes)
        # Local clocks are rounded to 1e-10 s. Recover the authored knot before
        # selecting a side of a jump, even at a large absolute song offset.
        nearest = bisect_left(times, time)
        for knot in times[max(0, nearest - 1):nearest + 1]:
            if time == local_seconds(knot, 0):
                time = knot
                break
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
class _SweepClip(RectangleClip):
    """A strip measured along x + slope * (y - pivot_y) in glyph coordinates."""

    slope: float = 0.0
    pivot_y: float = 0.0


@dataclass(frozen=True, kw_only=True)
class _ColorStripClip(_SweepClip):
    """Moving color strip for scanlines with a separately sampled brush."""

    band: str = ""


class _LyricPaintClip(_SweepClip):
    """A lyric color partition on the face of a drawing."""


@dataclass(frozen=True, kw_only=True)
class _CellWipeClip(_LyricPaintClip):
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
    material: LinearGradient | None = None
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
        if self.material is not None and not isinstance(self.material, LinearGradient):
            raise TypeError("material must be a LinearGradient")
        if (
            isinstance(self.clip, (RectangleClip, VectorClip))
            and self.clip.deform is not None
            and any(
                t < -self.time_origin or t > self.lifetime.end - self.time_origin
                for t in self.clip.deform.breakpoints
            )
        ):
            raise ValueError("clip breakpoint outside object lifetime")
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
    shader_paint: ShaderPaint | None = None
    material_effects: tuple[MaterialClip, ...] = ()
    extrusion: Extrusion | None = None
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
    for an outline-only drawing. The border radius uses script pixels by default.
    With scale_border=True the radius is measured in local path coordinates.
    """

    path: VectorPath
    deform: GeometryAnimation | None = None
    filled: bool = True
    scale_border: bool = False
    shader_paint: ShaderPaint | None = None
    material_effects: tuple[MaterialClip, ...] = ()
    extrusion: Extrusion | None = None

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
    Shader preview and playback support normal screen-space rectangle clips with static
    bounds or RectangleKeyframes evaluated on the group's clock. A parent
    rectangle intersects child clips without replacing their local clocks.
    """

    children: tuple[SceneObject, ...]

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
class AssDialogue:
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
    """A Document-backed composition of visual objects and already-lowered ASS dialogues.

    add and source replacement configure generation; compile returns a new standard
    ASS Document and reports.
    """

    document: Document
    objects: list[SceneObject | AssDialogue] = field(default_factory=list)
    replace_records: set[int] = field(default_factory=set)
    owner: str = "scene"

    def add(self, *objects: SceneObject | AssDialogue) -> Self:
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

    def prepare_hook(self) -> PreparedHook:
        """Snapshot the scene for repeated window exports with a shared glyph cache."""
        return PreparedHook(self)

    def export(
        self, path: str | Path, *, fps: int = 60, start: float = 0,
        duration: float | None = None, max_bytes: int | None = None,
    ) -> None:
        """Package the scene shader and resources in a standalone libplacebo .hook.

        WGSL material functions are translated to GLSL by Naga at export time.
        Unsupported animations raise a compile error.
        Start is frame-aligned in seconds. mpv uses media PTS;
        the sequential clock in FFmpeg begins at start. Duration defaults to the remaining Scene;
        subsequent frames pass through. Render at the exported fps on an opaque
        SDR video with matching aspect ratio. Includes glyph masks and effects.
        max_bytes limits the complete file before replacing the destination.
        """
        self.prepare_hook().export(path, fps=fps, start=start, duration=duration, max_bytes=max_bytes)

    def export_resources(
        self, directory: str | Path, *, fps: int = 60, start: float = 0,
        duration: float | None = None,
    ) -> None:
        """Write the GLSL scene shader and binary textures to a new directory.

        Use preview() to open a player directly, or load these resources from
        your own host. The clock matches export(). Each .bin contains a
        row-aligned texture with dimensions given by textures.json.
        """
        self.prepare_hook().export_resources(directory, fps=fps, start=start, duration=duration)

    def preview(
        self, path: str | Path | None = None, *, fps: int = 60, start: float = 0,
        duration: float | None = None, open_browser: bool = True,
    ) -> Path:
        """Write and open a self-contained HTML scene preview with WebGL 2.

        The player loops on demand and supports seeking and editing named material inputs.
        Frame rate and time windows follow export_resources(). If path is omitted,
        write a temporary HTML file. Return the file path so it can be reopened or
        removed. Pass open_browser=False to save without launching a browser.
        If no browser can be opened, warn and return the saved path.
        """
        from .output.browser_preview import preview_in_browser

        return preview_in_browser(
            self, path, fps=fps, start=start, duration=duration, open_browser=open_browser,
        )

    @property
    def ass(self) -> AssOutput:
        """Access native ASS export for this scene."""
        return AssOutput(self)


class PreparedHook:
    """Reusable snapshot for sequential exports at arbitrary positions and frame rates.

    Prepare a new snapshot after changing the scene. Window exports share measured
    masks and the resolved object hierarchy. Each output has its own playback clock.
    """

    def __init__(self, scene: Scene) -> None:
        from .output.hook.draws import HookDrawResolver

        self._frames = HookDrawResolver(scene)

    def material_inputs(self) -> dict[str, PaintValue]:
        """List the named material defaults across the prepared Scene.

        Preview hosts can discover editable inputs before exporting a window.
        The uniforms in each exported window depend on its visible materials.
        """
        values: dict[str, PaintValue] = {}
        for leaf in self._frames.leaves:
            for clip in leaf.node.material_effects:
                for argument in clip.effect._arguments():
                    if not isinstance(argument, PaintInput):
                        continue
                    default = values.setdefault(argument.name, argument.value)
                    if default != argument.value:
                        raise SceneCompileError(
                            f"paint input {argument.name!r} has conflicting values", object_id=leaf.node.id,
                        )
        return values

    def export(
        self, path: str | Path, *, fps: int = 60, start: float = 0,
        duration: float | None = None, max_bytes: int | None = None,
    ) -> None:
        """Package the scene shader and resources in a standalone libplacebo .hook.

        WGSL material functions are translated to GLSL by Naga at export time.
        Unsupported animations raise a compile error.
        Start is frame-aligned in seconds. mpv uses media PTS;
        the sequential clock in FFmpeg begins at start. Duration defaults to the remaining Scene;
        subsequent frames pass through. Render at the exported fps on an opaque
        SDR video with matching aspect ratio. Includes glyph masks and effects.
        max_bytes limits the complete file before replacing the destination.
        """
        from .output.hook.export import export_hook

        export_hook(self._frames, Path(path), fps, start, duration, max_bytes=max_bytes)

    def export_resources(
        self, directory: str | Path, *, fps: int = 60, start: float = 0,
        duration: float | None = None,
    ) -> None:
        """Write the GLSL scene shader and binary textures to a new directory.

        The clock and rendering contract match export(). Each .bin contains a
        row-aligned texture with dimensions given by textures.json.
        """
        from .output.hook.export import export_hook

        export_hook(self._frames, Path(directory), fps, start, duration, resources=True)

@dataclass(frozen=True)
class AssOutput:
    """Native ASS output for a prepared scene."""

    scene: Scene

    def compile(
        self,
        *,
        budget: AssBudget | None = None,
        native_tweens: bool = True,
        on_estimate: Callable[[AssEstimate], None] | None = None,
    ) -> AssResult:
        """Compile a new ASS Document and reports under explicit Scene budgets.

        ASS supports native motion and hard clips. Frame sampling, paint fields,
        and feathered wipes raise SceneCompileError.
        on_estimate runs after preflight and before frame callbacks; raising
        cancels compilation without changing the scene or source document.
        """
        from .output.ass_export import AssBudget, compile_ass

        return compile_ass(
            self.scene,
            budget=AssBudget() if budget is None else budget,
            native_tweens=native_tweens,
            on_estimate=on_estimate,
        )
