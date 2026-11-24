"""A second-syllable count-in follows a rotating lyric anchor, staying upright.

"""

from dataclasses import replace
from math import cos, radians, sin

from kara_templater import (
    CYAN,
    CueMarker,
    CuePreset,
    Document,
    Lifetime,
    Line,
    PathObject,
    Scene,
    ShaderMotion,
    Style,
    TextCue,
    Vec2,
    VectorPath,
    VisualState,
    bind_cues,
    layout_document_text,
)

START = Vec2(300, 300)
TRAVEL = Vec2(220, -40)
TURN = 12
HALF_TIME = 2.5


def _swing(state: VisualState, progress: float) -> VisualState:
    return replace(state, position=START + TRAVEL * progress, rotation=TURN * progress)


def build() -> Scene:
    document = Document.create(
        styles=(Style(fontname="DejaVu Sans", fontsize=64, shadow=0),)
    )
    document.records.append(
        Line(
            text=CueMarker("second", "count", placement="independent").markup()
            + r"{\k150}FOLLOW {\k150}ME",
            start_time=1000,
            end_time=4000,
        )
    )
    record = len(document.records) - 1
    layout = layout_document_text(document, record, id="lyric", display=Lifetime(0, 5))
    second = layout.timing[1]
    bound = bind_cues(
        layout,
        {
            "count": CuePreset(
                factory=TextCue(
                    labels=("READY", "SET", "GO"), font_size=28, color=CYAN
                ),
                trigger=second.start,
            ),
        },
    )
    # An ordinary invisible child supplies a world anchor under the chosen unit.
    box = layout.range_bounds(second.start_offset, second.end_offset)
    cue_width = bound.cues[0].content.width
    anchor = PathObject(
        id="count-anchor",
        lifetime=layout.lifetime,
        path=VectorPath.circle(1),
        state=VisualState(
            position=Vec2(
                box.left + (box.width - cue_width) / 2, box.top + box.height + 24
            ),
            opacity=0,
        ),
    )
    lyric = bound.group(position=START)
    lyric = replace(lyric, children=(*lyric.children, anchor))
    motion = ShaderMotion(
        _swing, frozenset({"position", "rotation"}),
        "pos=pairAt(data)+pairAt(data+2)*p; angle=item(data+4)*p;",
        (START.x, START.y, TRAVEL.x, TRAVEL.y, TURN),
    )
    returning = replace(
        motion, function=lambda state, p: _swing(state, 1 - p),
        source="float q=1.-p; pos=pairAt(data)+pairAt(data+2)*q; angle=item(data+4)*q;",
    )
    lyric = lyric.animate(motion, duration=HALF_TIME).animate(
        returning, at=HALF_TIME, duration=HALF_TIME,
    )
    count = bound.independent[0]
    onset = count.lifetime.start / HALF_TIME
    travel = (count.lifetime.end - count.lifetime.start) / HALF_TIME
    point = anchor.state.position

    def follow(state: VisualState, progress: float) -> VisualState:
        phase = onset + progress * travel
        angle = radians(TURN * phase)
        offset = Vec2(point.x * cos(angle) - point.y * sin(angle),
                      point.x * sin(angle) + point.y * cos(angle))
        return replace(state, position=START + TRAVEL * phase + offset)

    count = count.animate(ShaderMotion(
        follow, frozenset({"position"}), """
        float phase=item(data+7)+p*item(data+8);
        pos=pairAt(data)+pairAt(data+2)*phase
            +basisOf(vec2(1.),vec2(0.),item(data+4)*phase)*pairAt(data+5);
        """, (START.x, START.y, TRAVEL.x, TRAVEL.y, TURN, point.x, point.y, onset, travel),
    ), duration=count.lifetime.end - count.lifetime.start)
    scene = Scene(document).add(lyric, count)
    scene.replace_source(record)
    return scene
