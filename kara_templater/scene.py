"""Document-backed scene objects, independent of any lyric-specific frontend."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Literal, Self

from .ass import Document, Line
from .geometry import Vec2, VectorPath, finite
from .object_references import StateReference
from .paint_fields import PaintField
from .path_animation import GeometryAnimation
from .path_geometry import GeometryError
from .scene_animation import (
    AnimationClip,
    VisualState,
    evaluate_clips,
    local_seconds,
    translate_clips,
    validate_clips,
)
from .sources import EventOrigin

if TYPE_CHECKING:
    from .scene_evaluation import SceneEvaluator
    from .scene_output import SceneBudget, SceneResult


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
    """Pure local-seconds rectangle bounds; None denotes an empty mask."""

    function: Callable[[float], tuple[float, float, float, float] | None]
    breakpoints: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        finite(*self.breakpoints)
        if not callable(self.function) or any(t < 0 for t in self.breakpoints):
            raise ValueError(
                "rectangle function requires callable and nonnegative breakpoints"
            )

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
    deform: RectangleFunction | None = None

    def __post_init__(self) -> None:
        if self.space not in ("screen", "local"):
            raise ValueError("clip space must be screen or local")
        finite(self.left, self.top, self.right, self.bottom)
        if self.left >= self.right or self.top >= self.bottom:
            raise ValueError("clip must have positive width and height")


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

    Local evaluation is distinct from world-space SceneEvaluator queries.
    """

    id: str
    lifetime: Lifetime
    state: VisualState = VisualState()
    animations: tuple[AnimationClip, ...] = ()
    layer: int = 0
    origin: EventOrigin | None = None
    clip: RectangleClip | VectorClip | None = None
    material: PaintField | None = None
    reference: StateReference | None = None

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("visual objects require a nonempty id")
        if type(self.layer) is not int:
            raise TypeError("layer must be an integer")
        if (
            isinstance(self.clip, (RectangleClip, VectorClip))
            and self.clip.deform is not None
            and any(
                t < 0 or t > self.lifetime.end - self.lifetime.start
                for t in self.clip.deform.breakpoints
            )
        ):
            raise ValueError("clip breakpoint outside object lifetime")
        if self.material is not None:
            finite(*self.material.breakpoints)
            if any(
                t < 0 or t > self.lifetime.end - self.lifetime.start
                for t in self.material.breakpoints
            ):
                raise ValueError("paint breakpoint outside object lifetime")
        if self.reference is not None:
            finite(*self.reference.breakpoints)
            if any(
                clip.animation.channels & self.reference.channels
                for clip in self.animations
            ):
                raise ValueError("reference and local animation write the same channel")
        validate_clips(self.animations)
        for clip in self.animations:
            if clip.end > self.lifetime.end - self.lifetime.start + 1e-9:
                raise ValueError(f"{self.id}: animation extends beyond lifetime")

    def at(self, time: float) -> VisualState:
        """Evaluate this object at absolute seconds using its local animation clock.

        Use SceneEvaluator for parent transforms and references.
        """
        finite(time)
        return evaluate_clips(
            self.state, self.animations, local_seconds(time, self.lifetime.start)
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
            animations=translate_clips(
                self.animations, Vec2() if offset is None else offset
            ),
        )


@dataclass(frozen=True, kw_only=True)
class TextObject(VisualNode):
    """A text drawing with family name, pixel font size, shaping style, alignment, and inherited visual state.

    Unsupported affine combinations can lower to glyph geometry with explicit
    budgets.
    """

    text: str
    font: str = "DejaVu Sans"
    font_size: float = 48
    bold: bool = False
    italic: bool = False
    spacing: float = 0
    alignment: int = 7
    encoding: int = 1

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
        if any(c in self.text for c in "{}\\\r"):
            raise ValueError("TextObject accepts plain text, not ASS markup")


@dataclass(frozen=True, kw_only=True)
class PathObject(VisualNode):
    """A visual VectorPath drawing with state, lifetime, and optional geometry deformation.

    Coordinates are local to its local origin and parent transforms.
    """

    path: VectorPath
    deform: GeometryAnimation | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.deform is not None:
            if type(self.deform.max_points) is not int or self.deform.max_points < 1:
                raise ValueError("geometry animation requires a positive point bound")
            finite(*self.deform.breakpoints)
            if any(
                t < 0 or t > self.lifetime.end - self.lifetime.start
                for t in self.deform.breakpoints
            ):
                raise ValueError("geometry breakpoint outside object lifetime")

    def path_at(self, time: float) -> VectorPath | None:
        """Return the original or deformed path at absolute seconds, using the object birth as local origin."""
        finite(time)
        if self.deform is None:
            return self.path
        path = self.deform.sample(self.path, local_seconds(time, self.lifetime.start))
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
            reference = node.reference
            result = replace(
                node,
                reference=None
                if reference is None
                else reference.retarget(names, delay),
            )
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
            animations=copied.animations,
            reference=None
            if copied.reference is None
            else copied.reference.retarget(names, delay),
            children=tuple(remap(child) for child in copied.children),
        )


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

    def compile(
        self, *, budget: SceneBudget | None = None, native_tweens: bool = False
    ) -> SceneResult:
        """Compile a new ASS Document and reports under explicit Scene budgets.

        Eligible continuous Tween lowering is opt-in.
        """
        from .scene_output import SceneBudget, compile_scene

        return compile_scene(
            self,
            budget=SceneBudget() if budget is None else budget,
            native_tweens=native_tweens,
        )
