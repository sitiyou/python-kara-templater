"""Mixed lyric Scenes preserve source ownership and use one compiler budget."""

from dataclasses import replace

import pytest

from kara_templater import (
    PINK,
    Document,
    Lifetime,
    Line,
    LyricHighlights,
    LyricRule,
    NativeEvent,
    SceneBudget,
    SceneCompileError,
    StatePatch,
    Style,
    TextObject,
    Track,
    Tween,
    Vec2,
    VisualState,
    prepare_tracks,
)


def source() -> Document:
    document = Document.create(
        width=320,
        height=240,
        styles=(Style(fontname="DejaVu Sans", fontsize=20, shadow=0),),
    )
    document.records.append(Line(text=r"{\k20}AB", start_time=0, end_time=400))
    return document


def track() -> Track:
    return Track(
        id="main", preview=0, tail=0, effects=(LyricHighlights.from_singing(StatePatch(fill=PINK)),)
    )


def test_mixed_regeneration_preserves_other_owner_and_unknown_sections():
    document = source()
    document.records.extend(("[Fonts]", "fontname: retained"))
    original = document.dumps()
    scene = prepare_tracks(document, tracks=(track(),), owner="song")
    scene.add(
        TextObject(
            id="caption",
            text="caption",
            lifetime=Lifetime(0, 0.4),
            state=VisualState(position=Vec2(20, 20)),
        )
    )
    result = scene.ass.compile()
    assert "fontname: retained" in result.document.dumps()
    assert document.dumps() == original
    assert all(event in result.document.records for event, _ in result.event_origins)
    other = Line(
        text=r"{\k20}other owner", effect="kara:scene:v1:other:object", end_time=400
    )
    result.document.records.append(other)
    again = prepare_tracks(result.document, tracks=(track(),), owner="song")
    assert len(again.lines) == 1
    regenerated = again.ass.compile().document
    assert not any(line.text.endswith("caption") for line in regenerated.lines)
    assert any(line.serialize() == other.serialize() for line in regenerated.lines)
    assert "fontname: retained" in regenerated.dumps()
    assert again.ass.compile().document.dumps() == regenerated.dumps()
    restored = prepare_tracks(regenerated, tracks=(), owner="song").ass.compile().document
    assert any(not line.comment and line.text == r"{\k20}AB" for line in restored.lines)
    assert any(line.serialize() == other.serialize() for line in restored.lines)


def test_corrupt_native_provenance_fails_before_lyric_factories():
    scene = prepare_tracks(source(), tracks=(track(),))
    scene.add(
        NativeEvent("existing", Line(text="native", end_time=400, effect="original"))
    )
    output = scene.ass.compile().document
    marker = next(
        line for line in output.lines if line.text == "kara native event follows"
    )
    output.records[output.records.index(marker) + 1] = replace(marker)
    calls: list[str] = []

    def factory(line):
        calls.append(line.id)
        return line

    with pytest.raises(SceneCompileError, match="damaged native-event provenance"):
        prepare_tracks(output, tracks=(replace(track(), effects=(factory,)),))
    assert not calls


def test_mixed_scene_preflight_and_final_budgets_keep_repeated_compile_stable():
    calls: list[float] = []

    def rate(progress: float) -> float:
        calls.append(progress)
        return progress * progress

    configured = replace(
        track(),
        effects=(
            *track().effects,
            LyricRule(
                "character",
                "singing",
                Tween(StatePatch(scale=Vec2(1.2, 1.2)), rate=rate),
            ),
        ),
    )
    scene = prepare_tracks(source(), tracks=(configured,))
    scene.add(TextObject(id="extra", text="X", lifetime=Lifetime(0, 0.4)))
    with pytest.raises(SceneCompileError, match="frame sampling"):
        scene.ass.compile()
    assert not calls
    scene = prepare_tracks(source(), tracks=(track(),))
    with pytest.raises(SceneCompileError, match="budget"):
        scene.ass.compile(budget=SceneBudget(max_events=1))
    assert not calls
    # Peak/byte limits depend on emitted events and are checked after sampling.
    with pytest.raises(SceneCompileError, match="peak active"):
        scene.ass.compile(budget=SceneBudget(max_active=1))
    first = scene.ass.compile()
    assert not calls
    assert scene.ass.compile().document.dumps() == first.document.dumps()
    with pytest.raises(SceneCompileError, match="byte budget"):
        scene.ass.compile(budget=SceneBudget(max_bytes=100))
