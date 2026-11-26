"""Declarative controls and placement for composing built-in lyric effects."""

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from math import isfinite
from re import fullmatch
from typing import Literal, cast, get_args

from .composition import Color, Glow, SecondaryOutline
from .cues import BarsCue, CueFactory, CuePreset, TextCue
from .geometry import Vec2
from .karaoke_cues import SignalCue, VolumeCue
from .karaoke_effects import (
    KaraokeDecoration,
    KaraokeEffects,
    KaraokeEntry,
    KaraokeExit,
    KaraokeHighlight,
)
from .lyric_effects import LyricEcho
from .lyric_line import LyricLine, LyricRule
from .lyric_particles import LyricParticles, Petal, Sparkle
from .lyrics.highlights import LyricGradient
from .lyrics.placement import KaraokeRows, Layout
from .lyrics.tracks import LyricEffect, Track
from .paint_fields import Extrusion, PaintControl, PaintInput
from .scene import ObjectGroup, SceneObject, TextObject
from .scene_animation import (
    DriftOut,
    FadeIn,
    FadeOut,
    Jump,
    ScalePulse,
    Slide,
    StatePatch,
    Tween,
)

type ComponentValue = str | bool | float
type ComponentTarget = Literal["track", "body", "ruby"]


@dataclass(frozen=True)
class ComponentParameter:
    """Control declaration with an optional scalar range and GPU update support.

    Colors are six hexadecimal digits. Numeric limits are inclusive.
    Real-time controls are opt-in bindings on component instances.
    """

    label: str
    kind: Literal["number", "integer", "color", "boolean", "text", "choice"]
    default: ComponentValue
    bounds: tuple[float, float] | None = None
    step: float | None = None
    unit: str = ""
    choices: tuple[str, ...] = ()
    live: bool = False
    advanced: bool = False

    def resolve(self, value: ComponentValue) -> ComponentValue:
        """Validate and normalize a submitted value against the declaration."""
        match self.kind:
            case "number" | "integer":
                if isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value):
                    lo, hi = self.bounds or (-float("inf"), float("inf"))
                    if lo <= value <= hi:
                        if self.kind == "number":
                            return value
                        if int(value) == value:
                            return int(value)
            case "color":
                if isinstance(value, str) and fullmatch(r"[0-9a-fA-F]{6}", value):
                    return value.upper()
            case "boolean":
                if isinstance(value, bool):
                    return value
            case "text":
                if isinstance(value, str) and value.strip():
                    return value
            case "choice":
                if value in self.choices:
                    return value
        raise ValueError(f"invalid {self.label}: {value!r}")


@dataclass(frozen=True)
class EffectComponent:
    """An editable component's slot, permitted targets and parameter controls.

    When repeatable is false, one selection occupies the slot per target.
    A track-wide selection occupies its slot for both body and readings.
    """

    label: str
    slot: str
    targets: tuple[ComponentTarget, ...] = ("track",)
    repeatable: bool = False
    parameters: Mapping[str, ComponentParameter] = field(default_factory=dict)


@dataclass(frozen=True)
class ComponentSelection:
    """A component configured on one track, with explicit optional input names.

    Parameters omitted by the caller use the component defaults. Controls can
    narrow and label named inputs. Reusing a name links inputs that have the
    same type, value and declaration.
    """

    id: str
    component: str
    target: ComponentTarget = "track"
    values: Mapping[str, ComponentValue] = field(default_factory=dict)
    bindings: Mapping[str, str] = field(default_factory=dict)
    controls: Mapping[str, PaintControl] = field(default_factory=dict)


def _number(label: str, default: float, lo: float, hi: float, unit: str = "",
            *, step: float = 0.1, live: bool = False, advanced: bool = False) -> ComponentParameter:
    return ComponentParameter(label, "number", default, (lo, hi), step, unit, live=live, advanced=advanced)


def _color(label: str, default: str, *, live: bool = False) -> ComponentParameter:
    return ComponentParameter(label, "color", default, live=live)


def _choice(label: str, default: str, *choices: str) -> ComponentParameter:
    return ComponentParameter(label, "choice", default, choices=choices)


def effect_components(*, script_height: int = 1080) -> dict[str, EffectComponent]:
    """Return the built-in effect catalog with defaults for the script resolution."""
    ratio = script_height / 1080
    recipe = KaraokeEffects()
    glyphs: tuple[ComponentTarget, ...] = ("body", "ruby")
    pixel = "px"
    scan = {
        "scanline_color": _color("Scanline color", "D5FAFF", live=True),
        "scanline_strength": _number("Strength", 1, 0, 1, step=0.01, live=True),
        "scanline_width": _number("Width", max(1, round(16 * ratio)), 0.1, max(1, 96 * ratio), pixel, live=True),
        "scanline_softness": _number("Softness", round(8 * ratio), 0, max(1, 48 * ratio), pixel, live=True),
        "ruby_scanline": _choice("Reading coverage", "both", "both", "reading"),
    }
    direction = {
        "reverse_wipe": ComponentParameter("Reverse wipe", "boolean", False, advanced=True),
        "sweep_angle": _number("Front angle", 0, -60, 60, "°", advanced=True),
    }
    ornaments = {
        "particle_size": _number("Size", recipe.particle_size, 0.05, 2, "em", step=0.01),
        "particle_rate": _number("Rate multiplier", 1, 0.1, 3),
        "particle_layers": _choice("Paint layers", "solid", "solid", "stroke", "decor", "all"),
    }
    result: dict[str, EffectComponent] = {}
    for slot, values in (
        ("entry", get_args(KaraokeEntry.__value__)),
        ("exit", get_args(KaraokeExit.__value__)),
        ("highlight", get_args(KaraokeHighlight.__value__)),
        ("decoration", get_args(KaraokeDecoration.__value__)),
    ):
        for name in values:
            params: dict[str, ComponentParameter] = {}
            if name != "none" and slot in ("entry", "exit"):
                params = {
                    f"{slot}_duration": _number("Duration", recipe.entry_duration, 0, 3, "s", step=0.01),
                    f"{slot}_unit": _choice("Timing unit", "preset", "preset", "character"),
                }
            if slot == "highlight":
                params = {**direction, **(scan if "scanline" in name else {})}
            if slot == "decoration" and name != "none":
                params = ornaments
            kind = f"{slot}-{name.replace('_', '-')}"
            label = {
                "highlight-none": "Steady wipe",
                "highlight-no-wipe": "Change color at note onset",
            }.get(kind, name.replace("_", " ").capitalize())
            result[kind] = EffectComponent(label, slot, parameters=params)

    band_geometry = {
        name: replace(scan[name], live=False)
        for name in ("scanline_width", "scanline_softness", "ruby_scanline")
    }
    for variant, label in (
        ("brighten", "Brighten both sides"),
        ("follow-before", "Follow waiting color"),
        ("follow-after", "Follow sung color"),
        ("gradient", "Gradient scanline"),
    ):
        paint = (
            {"start": _color("First color", "74E5F3"), "end": _color("Last color", "FFA3CF")}
            if variant == "gradient" else
            {"scanline_brightness": _number("Brightness", 0.6, 0, 1, step=0.01)}
        )
        result[f"band-{variant}"] = EffectComponent(label, "highlight", parameters={**direction, **band_geometry, **paint})

    result.update({
        "transition-stagger": EffectComponent("Transition stagger", "transition", parameters={
            "stagger": _number("Stagger", recipe.stagger, 0, 0.99, step=0.01),
        }),
        "soft-front": EffectComponent("Soft, tinted wipe front", "front", parameters={
            "hook_feather": _number("Feather", round(10 * ratio, 2), 0, max(1, 64 * ratio), pixel),
            "front_color": _color("Front color", "D5FAFF"),
        }),
        "stroke-flash": EffectComponent("Outline flash", "flash"),
        "lyric-colors": EffectComponent("Lyric colors", "colors", parameters={
            "before_fill": _color("Waiting fill", "D6DCEA"),
            "after_fill": _color("Sung fill", "7DEAF6"),
            "before_outline": _color("Waiting outline", "16192F"),
            "after_outline": _color("Sung outline", "16192F"),
            "dual_outline": ComponentParameter("Sweep outline color", "boolean", True),
        }),
        "outline": EffectComponent("Outer outline", "outer-stroke", parameters={
            "color": _color("Color", "1B233C"),
            "width": _number("Width", max(1, 3 * ratio), 0, max(1, 20 * ratio), pixel),
        }),
        "glow": EffectComponent("Lyric glow", "glow", parameters={
            "color": _color("Color", "77F2FF"),
            "blur": _number("Blur", max(1, 12 * ratio), 0, max(1, 48 * ratio), pixel),
            "border": _number("Spread", max(1, 4 * ratio), 0, max(1, 32 * ratio), pixel, advanced=True),
            "opacity": _number("Opacity", 0.65, 0, 1, step=0.01),
        }),
        "lyric-gradient": EffectComponent("Lyric gradient", "material", parameters={
            "start": _color("First color", "FFDC93"),
            "end": _color("Last color", "F49E70"),
            "axis": _choice("Direction", "y", "x", "y"),
            "phase": _choice("Timing", "sung", "waiting", "sung"),
        }),
        "extrusion": EffectComponent("Extruded letters", "extrusion", parameters={
            "x": _number("Horizontal offset", 4, -24, 24, pixel),
            "y": _number("Vertical offset", 5, -24, 24, pixel),
            "color": _color("Front color", "BD5985"),
            "back": _color("Back color", "5C2648"),
        }),
        "typography": EffectComponent("Glyph style", "typography", glyphs, parameters={
            "fontname": ComponentParameter("Font family", "text", "Noto Sans CJK JP"),
            "fontsize": _number("Font size", max(1, 54 * ratio), 1, max(1, 160 * ratio), pixel),
            "bold": ComponentParameter("Bold", "boolean", False),
            "italic": ComponentParameter("Italic", "boolean", False),
            "spacing": _number("Letter spacing", 0, -4, 40, pixel, advanced=True),
            "outline": _number("Primary outline", min(3, 2 * ratio), 0, max(1, 24 * ratio), pixel),
            "shadow": _number("Shadow", 0, 0, max(1, 24 * ratio), pixel, advanced=True),
            "scale_x": _number("Horizontal scale", 100, 20, 200, "%", advanced=True),
            "scale_y": _number("Vertical scale", 100, 20, 200, "%", advanced=True),
        }),
        "ruby-layout": EffectComponent("Reading layout", "ruby-layout", parameters={
            "ruby_gap": _number("Reading gap", 6, -10, 32, pixel),
            "ruby_alignment": _choice("Reading alignment", "line", "line", "group"),
        }),
        "glyph-blur": EffectComponent("Glyph blur", "blur", glyphs, parameters={
            "blur": _number("Blur", 2, 0, max(1, 24 * ratio), pixel),
        }),
        "offset-shadow": EffectComponent("Offset shadow", "shadow", glyphs, parameters={
            "x": _number("Horizontal offset", 3, -24, 24, pixel),
            "y": _number("Vertical offset", 3, -24, 24, pixel),
        }),
        "echo": EffectComponent("Onset echo", "effects", glyphs, True, {
            "count": ComponentParameter("Copies", "integer", 2, (1, 4), 1),
            "offset": _number("Vertical offset", -8, -40, 40, pixel),
            "duration": _number("Duration", 0.45, 0.05, 1.2, "s", step=0.01),
            "opacity": _number("Opacity", 0.35, 0, 0.9, step=0.01),
        }),
        "jump": EffectComponent("Jump", "effects", glyphs, True, {
            "height": _number("Height", max(1, 14 * ratio), 0, max(1, 100 * ratio), pixel),
        }),
        "scale-pulse": EffectComponent("Scale pulse", "effects", glyphs, True, {
            "scale": _number("Scale", 1.2, 0.5, 2.5, step=0.01),
        }),
        "slide": EffectComponent("Slide", "entry", glyphs, parameters={
            "offset": _number("Horizontal offset", -24, -200, 200, pixel),
            "duration": _number("Duration", 0.3, 0.01, 2, "s", step=0.01),
        }),
        "fade-in": EffectComponent("Fade in", "entry", glyphs, parameters={
            "duration": _number("Duration", 0.3, 0.01, 2, "s", step=0.01),
        }),
        "fade-out": EffectComponent("Fade out", "exit", glyphs, parameters={
            "duration": _number("Duration", 0.3, 0.01, 2, "s", step=0.01),
        }),
        "drift-out": EffectComponent("Drift out", "exit", glyphs, parameters={
            "duration": _number("Duration", 0.35, 0.01, 2, "s", step=0.01),
            "offset": _number("Vertical offset", -16, -80, 80, pixel),
            "scale": _number("Scale", 0.96, 0.5, 2, step=0.01),
        }),
        "tween-scale": EffectComponent("Scale tween", "effects", glyphs, True, {
            "scale": _number("Scale", 0.8, 0.5, 2.5, step=0.01),
        }),
        "layout": EffectComponent("Row layout", "layout", parameters={
            "rows": ComponentParameter("Rows", "integer", 2, (1, 6), 1),
            "alignment": _choice("Alignment", "center", "left", "center", "right", "alternating"),
            "vertical": ComponentParameter("Vertical", "boolean", False),
            "right_to_left": ComponentParameter("Right to left", "boolean", False, advanced=True),
        }),
        "karaoke-rows": EffectComponent("Alternating karaoke rows", "layout", parameters={
            "vertical": ComponentParameter("Vertical", "boolean", False),
            "right_to_left": ComponentParameter("Right to left", "boolean", False, advanced=True),
        }),
    })
    for kind, label in (("bars", "Countdown bars"), ("volume", "Pulsing volume bars"),
                        ("signal", "Countdown lamps"), ("text", "Text countdown")):
        result[f"{kind}-cue"] = EffectComponent(label, "cue", parameters={
            "duration": _number("Duration", 1.2, 0.2, 4, "s", step=0.01),
            "color": _color("Color", "E8F4FF"),
        })
    for kind, label in (("sparkle", "Sparkle emitter"), ("petal", "Falling petals")):
        result[kind] = EffectComponent(label, "particles", repeatable=True, parameters={
            "color": _color("Color", "FFD9EA"),
            "rate": _number("Emissions per second", 6, 1, 16),
            "duration": _number("Duration", 0.45, 0.1, 1.5, "s"),
            "size": _number("Size", 4, 1, 20, pixel),
            "placement": _choice("Origin", "front", "front", "line"),
        })
    return result


def _resolve(selection: ComponentSelection, component: EffectComponent) -> dict[str, ComponentValue | Color | PaintInput]:
    fields = component.parameters
    if (set(selection.values) | set(selection.bindings)) - fields.keys():
        raise ValueError(f"unknown parameter on {selection.id!r}")
    if set(selection.controls) - selection.bindings.keys():
        raise ValueError("paint control overrides need a named binding")
    values: dict[str, ComponentValue | Color | PaintInput] = {}
    for name, parameter in fields.items():
        chosen = parameter.resolve(selection.values.get(name, parameter.default))
        actual = Color.hex("#" + chosen) if isinstance(chosen, str) and parameter.kind == "color" else chosen
        if binding := selection.bindings.get(name):
            if not parameter.live or isinstance(actual, (bool, str)):
                raise ValueError(f"{name!r} cannot be bound to a paint input")
            control = selection.controls.get(name, PaintControl())
            bounds = control.bounds or parameter.bounds
            if bounds and (parameter.bounds is None
                           or not parameter.bounds[0] <= bounds[0] < bounds[1] <= parameter.bounds[1]):
                raise ValueError(f"{name!r} reranges outside the component limits")
            actual = PaintInput(binding, actual, replace(
                control, bounds=bounds, step=control.step or parameter.step,
                unit=parameter.unit, label=control.label or parameter.label,
            ))
        values[name] = actual
    return values


def _glyph_patch(target: Literal["character", "ruby"], patch: StatePatch) -> LyricEffect:
    def apply(line: LyricLine) -> LyricLine:
        ids = {id for glyph in line.query(target) for id in (glyph.node_id, *glyph.aliases)}

        def decorate(node: SceneObject) -> SceneObject:
            if isinstance(node, ObjectGroup):
                return replace(node, children=tuple(decorate(child) for child in node.children))
            if isinstance(node, TextObject) and node.id in ids:
                return replace(node, state=patch.interpolate(node.state, 1))
            return node

        return replace(line, children=tuple(decorate(child) for child in line.children))
    return apply


def compose_track(track: Track, selections: tuple[ComponentSelection, ...],
                  *, script_height: int = 1080) -> Track:
    """Apply editable components to a Track using normal lyric and scene builders.

    An existing KaraokeEffects provides defaults for its slots. Otherwise the
    track starts with a steady wipe. Additional lyric rules are applied after
    the built-in recipe in declared order and follow its animation constraints.
    Track styles, including explicitly defined reading styles, remain the basis
    of typography customization.
    """
    catalog = effect_components(script_height=script_height)
    karaoke = next((effect for effect in track.effects if isinstance(effect, KaraokeEffects)),
                   KaraokeEffects(entry="none", exit="none", highlight="none"))
    other = [effect for effect in track.effects if not isinstance(effect, KaraokeEffects)]
    styles = list(track.styles)
    extra: list[LyricEffect] = []
    occupied: set[tuple[str, ComponentTarget]] = set()
    ids: set[str] = set()
    recipe_values: dict[str, object] = {}
    track_values: dict[str, object] = {}
    for selection in selections:
        spec = catalog.get(selection.component)
        if spec is None or selection.target not in spec.targets:
            raise ValueError(f"invalid component or target {selection.component!r}/{selection.target}")
        key = spec.slot, selection.target
        target = selection.target
        clash = not spec.repeatable and any(
            slot == spec.slot and (scope == target or scope == "track" or target == "track")
            for slot, scope in occupied
        )
        if not selection.id or selection.id in ids or clash:
            raise ValueError(f"duplicate component ID or occupied slot: {selection.id!r}")
        occupied.add(key)
        ids.add(selection.id)
        values = _resolve(selection, spec)
        glyph_target = "ruby" if target == "ruby" else "character"
        match spec.slot:
            case "entry" | "exit" | "highlight" | "decoration":
                if selection.component in {"slide", "fade-in", "fade-out", "drift-out"}:
                    entering = spec.slot == "entry"
                    animation = {
                        "fade-in": FadeIn(),
                        "fade-out": FadeOut(),
                        "slide": Slide(Vec2(cast("float", values.get("offset", 0)), 0), entering=True),
                        "drift-out": DriftOut(
                            Vec2(0, cast("float", values.get("offset", 0))),
                            cast("float", values.get("scale", 1)),
                        ),
                    }[selection.component]
                    recipe_values[spec.slot] = "none"
                    extra.append(LyricRule(
                        target=glyph_target, anchor="enter" if entering else "exit",
                        animation=animation, duration=cast("float", values["duration"]),
                    ))
                    continue
                if selection.component.startswith("band-"):
                    mode = selection.component.removeprefix("band-").replace("-", "_")
                    recipe_values["highlight"] = "scanline"
                    recipe_values["scanline_mode"] = "color" if mode == "gradient" else mode
                    if mode == "gradient":
                        recipe_values["scanline_material"] = LyricGradient((
                            cast("Color", values.pop("start")), cast("Color", values.pop("end")),
                        ))
                    recipe_values.update(values)
                    continue
                recipe_values.update(values)
                recipe_values[spec.slot] = selection.component.split("-", 1)[1].replace("-", "_")
            case "transition" | "front" | "colors":
                recipe_values.update(values)
            case "flash":
                recipe_values["stroke_flash"] = True
            case "glow":
                recipe_values["glow"] = Glow(
                    cast("Color", values["color"]), cast("float", values["blur"]),
                    cast("float", values["border"]), cast("float", values["opacity"]),
                )
            case "material":
                property_name = "base_material" if values["phase"] == "waiting" else "material"
                recipe_values[property_name] = LyricGradient(
                    (cast("Color", values["start"]), cast("Color", values["end"])),
                    cast('Literal["x", "y"]', values["axis"]),
                )
            case "extrusion":
                track_values["extrusion"] = Extrusion(
                    Vec2(cast("float", values["x"]), cast("float", values["y"])),
                    cast("Color", values["color"]), cast("Color", values["back"]),
                )
            case "outer-stroke":
                recipe_values["secondary_outline"] = SecondaryOutline(
                    cast("Color", values["color"]), cast("float", values["width"]),
                )
            case "typography":
                body = [style for style in styles if not style.name.endswith("-furigana")]
                if not body:
                    raise ValueError("typography components need explicit Track styles")
                if selection.target == "body":
                    styles = [replace(style, **values) if style in body else style for style in styles]
                else:
                    by_name = {style.name: style for style in styles if style not in body}
                    for parent in body:
                        name = parent.name + "-furigana"
                        by_name[name] = replace(by_name.get(name, replace(parent, name=name)), **values)
                    styles = body + list(by_name.values())
            case "ruby-layout":
                track_values.update(values)
            case "layout":
                track_values["vertical"] = values["vertical"]
                track_values["right_to_left"] = values["right_to_left"]
                if selection.component == "karaoke-rows":
                    track_values["layout"] = KaraokeRows()
                else:
                    alignment = cast('Literal["left", "center", "right", "alternating"]', values["alignment"])
                    track_values["layout"] = Layout(rows=cast("int", values["rows"]), alignment=alignment)
            case "cue":
                color = cast("Color", values["color"])
                cues: dict[str, CueFactory] = {
                    "bars-cue": BarsCue(color=color), "volume-cue": VolumeCue(after=color),
                    "signal-cue": SignalCue(color=color), "text-cue": TextCue(color=color),
                }
                seconds = cast("float", values["duration"])
                preset = CuePreset(factory=cues[selection.component], line_edge="above", duration=seconds, lead=seconds)
                track_values.update(chapter_cue=selection.id, cues={**track.cues, selection.id: preset})
            case "particles":
                color = cast("Color", values["color"])
                size, duration = cast("float", values["size"]), cast("float", values["duration"])
                factory = Petal(size=size, duration=duration, color=color) if selection.component == "petal" else Sparkle(
                    size=size, duration=duration, color=color,
                )
                extra.append(LyricParticles(
                    id=selection.id, rate=cast("float", values["rate"]), factory=factory,
                    placement=cast('Literal["front", "line"]', values["placement"]),
                ))
            case "blur" | "shadow":
                patch = StatePatch(blur=cast("float", values["blur"])) if spec.slot == "blur" else StatePatch(
                    shadow=Vec2(cast("float", values["x"]), cast("float", values["y"])),
                )
                extra.append(_glyph_patch(glyph_target, patch))
            case "effects":
                match selection.component:
                    case "echo":
                        extra.append(LyricEcho(
                            id=selection.id, target=glyph_target, offset=Vec2(0, cast("float", values["offset"])),
                            count=cast("int", values["count"]), duration=cast("float", values["duration"]),
                            opacity=cast("float", values["opacity"]),
                        ))
                    case "jump":
                        height = values["height"]
                        assert isinstance(height, (int, float))
                        extra.append(LyricRule(target=glyph_target, anchor="timing", animation=Jump(height)))
                    case "scale-pulse":
                        scale = values["scale"]
                        assert isinstance(scale, (int, float))
                        extra.append(LyricRule(target=glyph_target, anchor="timing", animation=ScalePulse(peak=scale)))
                    case "tween-scale":
                        scale = cast("float", values["scale"])
                        extra.append(LyricRule(
                            target=glyph_target, anchor="timing",
                            animation=Tween(StatePatch(scale=Vec2(scale, scale))), hold=False,
                        ))
    effects = (replace(karaoke, **recipe_values), *other, *extra)
    return replace(track, styles=tuple(styles), effects=effects, **track_values)
