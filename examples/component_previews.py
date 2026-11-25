"""Compare reusable karaoke components with short, isolated examples."""

from argparse import ArgumentParser
from collections.abc import Iterator
from dataclasses import replace
from math import ceil, cos, pi, sin
from pathlib import Path
from typing import get_args

from kara_templater import (
    CYAN,
    ORANGE,
    PINK,
    PURPLE,
    BarsCue,
    Box,
    Color,
    Contour,
    CubicSegment,
    CueFactory,
    CueMarker,
    CuePreset,
    CurveIn,
    Document,
    DriftOut,
    Extrusion,
    FadeIn,
    FadeOut,
    FollowObject,
    Glow,
    Jump,
    KaraokeDecoration,
    KaraokeEffects,
    KaraokeEntry,
    KaraokeExit,
    KaraokeHighlight,
    KaraokeRows,
    KaraokeTheme,
    Layout,
    Lifetime,
    Line,
    LineSegment,
    LyricEcho,
    LyricEffect,
    LyricGradient,
    LyricHighlights,
    LyricParticles,
    LyricRule,
    MorphPath,
    MoveAlong,
    ObjectGroup,
    ParticleContext,
    PathFunction,
    PathObject,
    Petal,
    ProgressCurve,
    RectangleClip,
    RectangleFunction,
    RectangleKeyframes,
    Ribbon,
    ScalePulse,
    ScatterOut,
    Scene,
    SceneObject,
    SecondaryOutline,
    ShaderMotion,
    ShaderPaint,
    SignalCue,
    Slide,
    Sparkle,
    StateAnimation,
    StateFunction,
    StatePatch,
    Style,
    TextCue,
    TextObject,
    Timeline,
    Track,
    TrailPath,
    Transform,
    Tween,
    Vec2,
    VectorClip,
    VectorGuide,
    VectorPath,
    VisualState,
    VolumeCue,
    WritePath,
    WritingStroke,
    build_lyric_scene,
    echoes,
)

FPS = 30
CENTER = Vec2(320, 180)
WORDS = r"{\k28}S{\k34}i{\k48}n{\k90}g"
TINT = LyricHighlights.from_timing(StatePatch(fill=CYAN))
DEFAULT_THEME = KaraokeTheme()
PRESETS = {
    "entry": get_args(KaraokeEntry.__value__),
    "exit": get_args(KaraokeExit.__value__),
    "highlight": get_args(KaraokeHighlight.__value__),
    "decoration": get_args(KaraokeDecoration.__value__),
}


def lyrics(
    *effects: LyricEffect,
    text: str = WORDS,
    cue: CueFactory | None = None,
    extrusion: Extrusion | None = None,
    guide: VectorGuide | None = None,
    theme: KaraokeTheme = DEFAULT_THEME,
) -> Scene:
    doc = Document.create(
        width=640,
        height=360,
        styles=(
            Style(fontname="DejaVu Sans", fontsize=86, bold=True, outline=3, shadow=0),
        ),
    )
    if cue is not None:
        text = CueMarker("intro", "count", placement="independent").markup() + text
    doc.records.append(Line(start_time=1400, end_time=3400, text=text))
    options = (
        {
            "count": CuePreset(
                factory=cue, position=Vec2(270, 90), lead=1.2, duration=1.2
            )
        }
        if cue is not None
        else {}
    )
    return build_lyric_scene(
        doc,
        theme=theme,
        tracks=(
            Track(
                id="lead",
                region=Box(40, 132, 560, 124),
                layout=Layout(alignment="center"),
                preview=0.9,
                tail=0.95,
                effects=effects,
                cues=options,
                extrusion=extrusion,
                guide_symbols={"◆": guide} if guide is not None else {},
            ),
        ),
    )


def word(text: str = "Sing") -> TextObject:
    return TextObject(
        id="word",
        text=text,
        font_size=88,
        bold=True,
        alignment=5,
        lifetime=Lifetime(0, 3),
        state=VisualState(position=CENTER, fill=CYAN),
    )


def objects(*nodes: TextObject | PathObject | ObjectGroup) -> Scene:
    return Scene(Document.create(width=640, height=360)).add(*nodes)


def motion(animation: StateAnimation, *, at: float = 0.3) -> Scene:
    return objects(word().animate(animation, at=at, duration=1.6))


def typography_comparison(name: str) -> Scene:
    """Keep the lettering and background fixed while changing one text style."""
    base = replace(
        word(),
        font_size=69,
        bold=False,
        state=VisualState(fill=Color.hex("#EDE8FF")),
    )
    match name:
        case "family":
            variant = replace(base, font="DejaVu Serif")
        case "size":
            variant = replace(base, font_size=94)
        case "bold":
            variant = replace(base, bold=True)
        case "italic":
            variant = replace(base, italic=True)
        case "spacing":
            variant = replace(base, spacing=18)
        case "scale":
            variant = replace(base, state=replace(base.state, scale=Vec2(0.78, 1.32)))
        case "border":
            variant = replace(base, state=replace(base.state, border=7, outline=PURPLE))
        case "blur":
            variant = replace(base, state=replace(base.state, blur=9))
        case "shadow":
            variant = replace(base, state=replace(base.state, shadow=Vec2(9, 12)))
        case _:
            raise ValueError(f"Unknown typography preview {name!r}")
    return objects(
        replace(
            base, id="reference", state=replace(base.state, position=Vec2(160, 180))
        ),
        replace(
            variant, id="variant", state=replace(variant.state, position=Vec2(480, 180))
        ),
    )


def sweep_pair(
    reference: KaraokeEffects,
    variant: KaraokeEffects,
    *,
    ruby: bool = False,
) -> Scene:
    """Play two instances of the same sustained note on a shared clock."""
    text = r"{\k210}歌声|うたごえ" if ruby else r"{\k210}GLOW"
    style = Style(
        fontname="Noto Sans CJK JP" if ruby else "DejaVu Sans",
        fontsize=83 if ruby else 66,
        bold=True,
        outline=2,
        shadow=0,
    )
    doc = Document.create(
        width=640,
        height=360,
        styles=(replace(style, name="Reference"), replace(style, name="Variant")),
    )
    doc.records.extend(
        (
            Line(text=text, style="Reference", start_time=300, end_time=2400),
            Line(text=text, style="Variant", start_time=300, end_time=2400),
        )
    )
    return build_lyric_scene(
        doc,
        tracks=(
            Track(
                id="reference",
                source=lambda line: line.style == "Reference",
                region=Box(0, 112, 320, 144),
                layout=Layout(alignment="center"),
                effects=(reference,),
            ),
            Track(
                id="variant",
                source=lambda line: line.style == "Variant",
                region=Box(320, 112, 320, 144),
                layout=Layout(alignment="center"),
                effects=(variant,),
            ),
        ),
    )


def sweep_comparison(name: str) -> Scene:
    """Compare scanline paint and the shape of the wipe front independently."""
    band = KaraokeEffects(
        entry="none",
        exit="none",
        highlight="scanline",
        before_fill=Color.hex("#7158A8"),
        after_fill=Color.hex("#DB842C"),
        scanline_color=Color.hex("#97F3FF"),
        scanline_width=26,
        scanline_softness=0,
    )
    wipe = replace(band, highlight="none")
    match name:
        case "color":
            return sweep_pair(wipe, band)
        case "brighten" | "follow_before" | "follow_after":
            return sweep_pair(band, replace(band, scanline_mode=name))
        case "width":
            return sweep_pair(replace(band, scanline_width=9), band)
        case "softness":
            return sweep_pair(band, replace(band, scanline_softness=13))
        case "strength":
            return sweep_pair(band, replace(band, scanline_strength=0.35))
        case "gradient":
            material = LyricGradient((CYAN, PINK, Color.hex("#FDE18D")))
            return sweep_pair(band, replace(band, scanline_material=material))
        case "feather":
            return sweep_pair(wipe, replace(wipe, hook_feather=24))
        case "front_tint":
            soft = replace(wipe, hook_feather=24)
            return sweep_pair(soft, replace(soft, front_color=CYAN))
        case "angle":
            return sweep_pair(band, replace(band, sweep_angle=28))
        case "reverse":
            return sweep_pair(band, replace(band, reverse_wipe=True))
        case "ruby":
            return sweep_pair(band, replace(band, ruby_scanline="reading"), ruby=True)
        case _:
            raise ValueError(f"Unknown sweep preview {name!r}")


def geometry() -> Contour:
    return Contour(
        Vec2(-145, 24),
        (CubicSegment(Vec2(-57, -146), Vec2(12, 122), Vec2(145, -28)),),
        closed=False,
    )


def path_deformation(name: str) -> PathObject:
    match name:
        case "trail-path":
            deform = TrailPath(geometry(), duration=1.8, lag=0.42, width=6)
            path = deform.full_path
        case "write-path":
            stem = Contour(Vec2(0, -75), (LineSegment(Vec2(0, 48)),), closed=False)
            top = Contour(Vec2(-54, -66), (LineSegment(Vec2(54, -66)),), closed=False)
            deform = WritePath(
                (WritingStroke(stem, 0.25, 0.65), WritingStroke(top, 1.12, 0.65)),
                width=12,
            )
            path = deform.full_path
        case "morph-path":
            path = VectorPath.polygon(
                Vec2(-85, 55), Vec2(0, -78), Vec2(85, 55), Vec2(0, 36)
            )
            deform = MorphPath(
                VectorPath.polygon(
                    Vec2(-85, 0),
                    Vec2(0, -80),
                    Vec2(85, 0),
                    Vec2(0, 80),
                ),
                start=0.25,
                duration=1.6,
            )
        case "path-function":
            path = VectorPath.polygon(Vec2(-85, 45), Vec2(0, -75), Vec2(85, 45))
            deform = PathFunction(
                lambda source, t: source.map(
                    lambda point: Vec2(
                        point.x,
                        point.y + point.x * min(t, 1.5) / 2,
                    )
                ),
                max_points=path.point_count,
            )
        case "ribbon":
            return Ribbon(
                color=PINK,
                width=6,
                duration=1.45,
                lag=0.45,
                travel=Vec2(150, -45),
                bend=Vec2(70, -100),
            )(
                ParticleContext(
                    id="ribbon",
                    birth=0.25,
                    seed=0,
                    position=Vec2(245, 217),
                    origin=None,
                )
            )
        case _:
            raise ValueError(f"Unknown path preview {name!r}")
    return PathObject(
        id=name,
        path=path,
        deform=deform,
        lifetime=Lifetime(0, 3),
        state=VisualState(position=CENTER, fill=CYAN),
    )


def dot(id: str, radius: float, color: Color) -> PathObject:
    return PathObject(
        id=id,
        path=VectorPath.circle(radius),
        lifetime=Lifetime(0, 3),
        state=VisualState(position=CENTER, fill=color),
    )


def drawings(
    node: SceneObject, start: float, end: float
) -> Iterator[tuple[TextObject | PathObject, float, float]]:
    start = max(start, node.lifetime.start)
    end = min(end, node.lifetime.end)
    if isinstance(node, ObjectGroup):
        for child in node.children:
            yield from drawings(child, start, end)
    else:
        yield node, start, end


def sampled(scene: Scene) -> Scene:
    """Preview evaluator-only components as static drawings at each Hook frame."""
    output = Scene(scene.document)
    evaluator = scene.evaluator()
    leaves = (
        drawing
        for root in scene.objects
        if isinstance(root, (TextObject, PathObject, ObjectGroup))
        for drawing in drawings(root, root.lifetime.start, root.lifetime.end)
    )
    for node, start, end in leaves:
        for frame in range(ceil(start * FPS), ceil(end * FPS)):
            at = frame / FPS
            lifetime = Lifetime(at, (frame + 1) / FPS)
            drawing = node
            if isinstance(node, PathObject) and node.deform is not None:
                path = node.path_at(at)
                if path is None:
                    continue
                drawing = replace(node, path=path, deform=None)
            drawing = replace(
                drawing,
                id=f"{node.id}/{frame}",
                state=evaluator.at(node.id, at),
                lifetime=lifetime,
                clock_start=None,
                animations=(),
                reference=None,
            )
            if isinstance(node.clip, RectangleClip) and node.clip.deform is not None:
                bounds = node.clip.deform.sample(at - node.time_origin)
                if bounds is None or bounds[0] >= bounds[2] or bounds[1] >= bounds[3]:
                    continue
                drawing = replace(
                    drawing, clip=RectangleClip(*bounds, space=node.clip.space)
                )
            output.add(drawing)
    return output


def follow_object() -> Scene:
    leader = dot("leader", 15, CYAN).animate(MoveAlong(geometry()), duration=2)
    follower = replace(
        dot("follower", 10, PINK),
        reference=FollowObject(leader.id, delay=0.24, offset=Vec2(0, 27)),
    )
    return sampled(objects(leader, follower))


def shader_arc(base: VisualState, progress: float) -> VisualState:
    angle = 3.14159265 * progress
    return replace(
        base, position=base.position + Vec2(180 * (progress - 0.5), -72 * sin(angle))
    )


def alternating_rows() -> Scene:
    doc = Document.create(
        width=640,
        height=360,
        styles=(Style(fontname="DejaVu Sans", fontsize=54, bold=True, shadow=0),),
    )
    doc.records.extend(
        (
            Line(start_time=600, end_time=1630, text=r"{\k38}Here {\k65}we"),
            Line(start_time=1700, end_time=2800, text=r"{\k110}go"),
        )
    )
    return build_lyric_scene(
        doc,
        tracks=(
            Track(
                id="lead",
                layout=KaraokeRows(),
                effects=(TINT,),
            ),
        ),
    )


def build(name: str) -> Scene:
    """Build the scene demonstrated on a component card."""
    group, _, slug = name.partition("-")
    value = slug.replace("-", "_")
    if group == "type":
        return typography_comparison(value)
    if group == "sweep":
        return sweep_comparison(value)
    if value in PRESETS.get(group, ()):
        baseline = KaraokeEffects(entry="none", exit="none", highlight="none")
        return lyrics(replace(baseline, **{group: value}))
    match name:
        case "default-recipe":
            return lyrics(KaraokeEffects())
        case "duotone":
            return lyrics(KaraokeEffects.duotone())
        case "stroke-flash":
            return lyrics(KaraokeEffects(highlight="none", stroke_flash=True))
        case "karaoke-rows":
            return alternating_rows()
        case "vector-guide":
            triangle = VectorPath.polygon(
                Vec2(0.08, -0.72), Vec2(0.63, -0.38), Vec2(0.08, -0.04)
            )
            return lyrics(
                TINT,
                text=r"{\k40}◆{\k160}Sing",
                guide=VectorGuide(triangle, advance=0.72),
            )
        case "lyric-highlights":
            return lyrics(
                LyricHighlights.from_timing(
                    StatePatch(fill=CYAN),
                    segment_colors={(1, 0): PINK, (2, 0): ORANGE},
                )
            )
        case "karaoke-theme":
            return lyrics(
                KaraokeEffects.duotone(),
                theme=KaraokeTheme(before_fill=PURPLE, after_fill=CYAN),
            )
        case "lyric-gradient":
            return lyrics(
                KaraokeEffects(
                    highlight="none", material=LyricGradient((CYAN, PINK, ORANGE))
                )
            )
        case "glow":
            return lyrics(
                KaraokeEffects(highlight="none", glow=Glow(PINK, blur=9, border=7))
            )
        case "secondary-outline":
            return lyrics(
                KaraokeEffects(
                    highlight="none",
                    after_secondary_outline=SecondaryOutline(PURPLE, width=5),
                )
            )
        case "extrusion":
            return lyrics(
                TINT, extrusion=Extrusion(Vec2(11, 16), PURPLE, back_color=PINK)
            )
        case "shader-paint":
            return objects(
                replace(
                    word(),
                    shader_paint=ShaderPaint(
                        "ink = mix(ink, vec3(1.0, 0.46, 0.70), 0.5+0.5*sin(0.060*local.x - 6.0*time));",
                    ),
                )
            )
        case "bars-cue":
            return lyrics(TINT, cue=BarsCue(width=105, height=43))
        case "text-cue":
            return lyrics(TINT, cue=TextCue(font_size=42))
        case "volume-cue":
            return lyrics(TINT, cue=VolumeCue(height=38))
        case "signal-cue":
            return lyrics(TINT, cue=SignalCue(shape="star", size=30, spacing=5))
        case "sparkle":
            return lyrics(TINT, LyricParticles(factory=Sparkle(size=9), rate=20))
        case "petal":
            return lyrics(TINT, LyricParticles(factory=Petal(size=11), rate=12))
        case "lyric-echo":
            return lyrics(
                TINT, LyricEcho(offset=Vec2(0, -15), paint=StatePatch(fill=PINK))
            )
        case "echoes":
            original = word().animate(Jump(height=80), at=0.35, duration=1.2)
            return sampled(objects(original, *echoes(original, spacing=0.10)))
        case "follow-object":
            return follow_object()
        case "scatter-out":
            return sampled(
                lyrics(
                    LyricRule(
                        "character", "exit", ScatterOut(), duration=0.75, stagger=0.07
                    ),
                )
            )
        case "fade-in":
            return motion(FadeIn(), at=0)
        case "fade-out":
            return motion(FadeOut())
        case "jump":
            return motion(Jump(height=70))
        case "scale-pulse":
            return motion(ScalePulse(peak=1.45))
        case "slide":
            return motion(Slide(Vec2(-160, 0), entering=True), at=0)
        case "curve-in":
            return sampled(
                motion(CurveIn(offset=Vec2(-140, 60), bend=Vec2(-95, -115)), at=0)
            )
        case "drift-out":
            return motion(DriftOut(offset=Vec2(110, -90), scale=0.65))
        case "tween":
            return motion(
                Tween(
                    StatePatch(position=Vec2(420, 156), scale=Vec2(0.65, 0.65)),
                    ProgressCurve.two_stage(
                        time_fraction=0.62,
                        progress_fraction=0.24,
                    ).at,
                )
            )
        case "timeline":
            timeline = (
                Timeline()
                .play(FadeIn(), duration=0.35)
                .wait(0.3)
                .play(Jump(height=55), duration=0.8)
                .play(FadeOut(), duration=0.6)
            )
            return objects(replace(word(), animations=timeline.clips))
        case "shader-motion":
            return motion(
                ShaderMotion(
                    shader_arc,
                    frozenset({"position"}),
                    "pos += vec2(180.0*(p-0.5), -72.0*sin(3.14159265*p));",
                ),
                at=0,
            )
        case "transform":
            return sampled(motion(Transform(rotation=lambda p: 25 * sin(2 * pi * p))))
        case "state-function":
            return sampled(
                motion(
                    StateFunction(
                        lambda base, p: replace(
                            base, opacity=0.5 + 0.5 * cos(4 * pi * p)
                        ),
                        frozenset({"opacity"}),
                    )
                )
            )
        case "rectangle-clip":
            return objects(
                replace(
                    word("Reveal"),
                    clip=RectangleClip(
                        140,
                        100,
                        496,
                        260,
                        deform=RectangleKeyframes(
                            (
                                (0.0, (140, 100, 140, 260)),
                                (1.9, (140, 100, 496, 260)),
                            )
                        ),
                    ),
                )
            )
        case "rectangle-function":
            return sampled(
                objects(
                    replace(
                        word("Reveal"),
                        clip=RectangleClip(
                            160,
                            100,
                            480,
                            260,
                            deform=RectangleFunction(
                                lambda seconds: (
                                    None
                                    if seconds <= 0
                                    else (
                                        320 - 160 * min(1, seconds),
                                        100,
                                        320 + 160 * min(1, seconds),
                                        260,
                                    )
                                )
                            ),
                        ),
                    )
                )
            )
        case "vector-clip":
            mask = VectorPath.circle(109).map(lambda p: p + CENTER)
            return sampled(
                objects(
                    replace(word("Reveal"), clip=VectorClip(mask)).animate(
                        Slide(Vec2(-135, 0), entering=True),
                        duration=2,
                    )
                )
            )
        case "object-group":
            label = replace(word(), state=VisualState(fill=CYAN))
            ring = replace(
                dot("ring", 130, PINK),
                filled=False,
                state=VisualState(
                    fill=PINK,
                    border=4,
                    outline=PINK,
                ),
            )
            return objects(
                ObjectGroup(
                    id="group",
                    lifetime=Lifetime(0, 3),
                    children=(ring, label),
                    state=VisualState(position=CENTER),
                ).animate(ScalePulse(peak=1.28), at=0.3, duration=1.6)
            )
        case "move-along":
            return sampled(
                objects(
                    dot("dot", 13, PINK).animate(
                        MoveAlong(geometry()),
                        duration=2,
                    )
                )
            )
        case "trail-path" | "write-path" | "morph-path" | "path-function" | "ribbon":
            return sampled(objects(path_deformation(name)))
        case _:
            raise ValueError(f"Unknown component preview {name!r}")


def main() -> None:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("component")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    scene = build(args.component)
    if args.component == "vector-clip":
        scene.ass.compile().document.save(args.output)
    else:
        scene.export(args.output, fps=FPS)


if __name__ == "__main__":
    main()
