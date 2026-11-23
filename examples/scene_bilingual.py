"""Two source lines, ruby, repeated singing and a shared world-space decoration.

"""

from dataclasses import replace
from math import pi, sin
from pathlib import Path

from kara_templater import (
    CYAN,
    PINK,
    AnimationClip,
    CueMarker,
    CuePreset,
    Document,
    Lifetime,
    Line,
    LyricLayout,
    ObjectGroup,
    PathObject,
    ReferenceFunction,
    Scene,
    StateFunction,
    StateKeyframe,
    StateLookup,
    StatePatch,
    Style,
    TextCue,
    Timeline,
    Vec2,
    VectorPath,
    VisualState,
    bind_lyric_cues,
    layout_document_lyrics,
    load_font,
    smooth_rate,
)


def pulse(state: VisualState, progress: float) -> VisualState:
    scale = 1 + 0.1 * sin(pi * progress) ** 2
    return replace(state, scale=Vec2(scale, scale))


def highlight(state: VisualState, progress: float) -> VisualState:
    return StatePatch(fill=PINK).interpolate(state, sin(pi * progress) ** 2)


def singing_line(
    layout: LyricLayout, *, id: str, position: Vec2, scale_pulse: bool = True
) -> ObjectGroup:
    """A source unit keeps its body/ruby together across every singing segment."""
    units: list[ObjectGroup] = []
    for index, unit in enumerate(layout.lyrics.units):
        intervals = tuple(
            (
                segment.singing.start - layout.body.lifetime.start,
                segment.singing.end - segment.singing.start,
            )
            for segment in unit.segments
            if segment.singing.end > segment.singing.start
        )
        group = layout.unit_group(index)
        scale_clips = tuple(
            AnimationClip(
                start, duration, StateFunction(pulse, frozenset(("scale",))), hold=False
            )
            for start, duration in intervals
        )
        color_clips = tuple(
            AnimationClip(
                start,
                duration,
                StateFunction(highlight, frozenset(("fill",))),
                hold=False,
            )
            for start, duration in intervals
        )
        units.append(
            replace(
                group,
                animations=scale_clips if scale_pulse else (),
                children=tuple(
                    replace(child, animations=color_clips) for child in group.children
                ),
            )
        )
    motion = Timeline().keyframes(
        StateKeyframe(2.5, StatePatch(position=position + Vec2(60, 0)), smooth_rate),
        StateKeyframe(5, StatePatch(position=position), smooth_rate),
    )
    return ObjectGroup(
        id=id,
        lifetime=layout.body.lifetime,
        state=VisualState(position=position),
        children=tuple(units),
        animations=motion.clips,
    )


def between_lines(state: VisualState, time: float, lookup: StateLookup) -> VisualState:
    # Root positions are deliberately the left edges of each centered line.
    # Add the separately measured centers through child anchor objects instead.
    top = lookup("top-center", time).position
    bottom = lookup("bottom-center", time).position
    return replace(state, position=top.lerp(bottom, 0.5))


def build() -> Scene:
    load_font(Path(__file__).resolve().parents[1] / "tests/fonts/KaraTestCJK.ttf")
    document = Document.create(
        styles=(
            Style(fontname="Kara Test CJK", fontsize=96, outline=2, shadow=0),
            Style(
                name="Default-furigana",
                fontname="DejaVu Sans",
                fontsize=30,
                outline=1,
                shadow=0,
            ),
            Style(
                name="English", fontname="DejaVu Sans", fontsize=50, outline=1, shadow=0
            ),
        )
    )
    sources = (
        Line(
            text=CueMarker("intro", "labels", placement="independent").markup()
            + r"{\k60}時|!toki{\kt120\k60}#{\kt200\k80}々|!doki",
            start_time=1000,
            end_time=4000,
        ),
        Line(
            text=r"{\k180}TIME {\k120}AND AGAIN",
            style="English",
            start_time=1000,
            end_time=4000,
        ),
    )
    indices = []
    for source in sources:
        indices.append(len(document.records))
        document.records.append(source)
    layouts = tuple(
        layout_document_lyrics(document, index, display=Lifetime(0, 5), ruby_gap=8)
        for index in indices
    )
    scene = Scene(document)
    for index, layout, name, y in zip(
        indices, layouts, ("top", "bottom"), (260, 460), strict=True
    ):
        scene.replace_source(index)
        line = singing_line(
            layout,
            id=name,
            position=Vec2(640 - layout.body.bounds.center, y),
            scale_pulse=name == "top",
        )
        # An invisible anchor exposes each measured line center to other objects.
        anchor = PathObject(
            id=f"{name}-center",
            lifetime=layout.body.lifetime,
            path=VectorPath.circle(1),
            state=VisualState(
                position=Vec2(layout.body.bounds.center, layout.body.bounds.middle),
                opacity=0,
            ),
        )
        scene.add(replace(line, children=(*line.children, anchor)))
    cues = bind_lyric_cues(
        layouts[0],
        {
            "labels": CuePreset(
                factory=TextCue(labels=("READY", "SET", "GO"), font_size=32),
                position=Vec2(1000, 100),
            )
        },
    )
    bridge = PathObject(
        id="between-lines",
        lifetime=Lifetime(0, 5),
        path=VectorPath.circle(7),
        state=VisualState(fill=CYAN),
        reference=ReferenceFunction(
            between_lines, ("top-center", "bottom-center"), frozenset(("position",))
        ),
    )
    return scene.add(*cues.independent, bridge)
