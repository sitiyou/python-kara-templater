from pathlib import Path

import pytest

from kara_templater import (
    Document,
    Engine,
    Lifetime,
    Line,
    NativeEvent,
    Scene,
    SceneBudget,
    SceneCompileError,
    Style,
    TextObject,
    apply_templates,
    preprocess,
)
from kara_templater.ass import EVENT_FORMAT, STYLE_FORMAT


def document():
    doc = Document.create(styles=(Style(fontname="DejaVu Sans"),))
    doc.records.extend(
        (
            Line(comment=True, effect="code once", text="total = 0"),
            Line(
                comment=True,
                effect="template syl noblank",
                text=r"!retime('syl')!{\pos($scenter,$smiddle)}",
            ),
            Line(text=r"{\k20}A{\k30}B", start_time=1000, end_time=2000),
            Line(text="unmatched", effect="other", start_time=1000, end_time=2000),
            "[Fonts]",
            "fontname: retained.ttf",
            "retained",
        )
    )
    return doc


def test_document_file_parity_and_parsed_regeneration(tmp_path):
    source = document()
    before = source.dumps()
    path = tmp_path / "input.ass"
    source.save(path)
    direct = apply_templates(source)
    loaded = apply_templates(Document.load(path))
    assert direct.dumps() == loaded.dumps()
    assert source.dumps() == before
    assert apply_templates(Document.parse(direct.dumps())).dumps() == direct.dumps()
    assert direct.dumps().endswith("fontname: retained.ttf\nretained\n")
    assert any(line.text == "unmatched" and not line.comment for line in direct.lines)
    assert sum(line.effect == "fx" for line in direct.lines) == 2


def test_legacy_scene_combines_with_new_objects_and_tracks_sources():
    source = document()
    index = next(
        i
        for i, record in enumerate(source.records)
        if isinstance(record, Line) and record.text == r"{\k20}A{\k30}B"
    )
    scene = Engine().to_scene(source)
    assert len(scene.objects) == 2
    for node in scene.objects:
        assert isinstance(node, NativeEvent)
        assert node.origin is not None
        assert node.origin.effect == "template:event:2"
        assert node.origin.sources[0].item_id == f"record:{index}"
    scene.add(TextObject(id="decoration", text="cue", lifetime=Lifetime(0, 1)))
    result = scene.compile()
    assert result.event_count == 3
    assert [r.strategy for r in result.objects] == [
        "native-event",
        "native-event",
        "native-static",
    ]
    assert sum(line.effect == "fx" for line in result.document.lines) == 2
    assert result.document.lines[-1].text.endswith("cue")


def test_parsing_does_not_execute_template_code():
    source = document()
    source.lines[0].text = "raise RuntimeError('executed explicitly')"
    parsed = Document.parse(source.dumps())
    assert parsed.dumps() == source.dumps()
    with pytest.raises(ValueError, match="executed explicitly"):
        apply_templates(parsed)


def test_native_empty_negative_intervals_and_budget():
    scene = Scene(Document.create()).add(
        NativeEvent("empty", Line(start_time=0, end_time=0, text="empty")),
        NativeEvent("negative", Line(start_time=-100, end_time=100, text="prelude")),
    )
    result = scene.compile()
    assert result.event_count == 2
    assert any(line.start_time == -100 for line in result.document.lines)
    assert all(
        line.start_time >= 0 for line in Document.parse(result.document.dumps()).lines
    )
    with pytest.raises(SceneCompileError, match="budget"):
        Engine(budget=SceneBudget(max_events=2)).apply(document())


def test_reordered_custom_fields_and_missing_effect_column():
    source = document()
    for index, record in enumerate(source.records):
        if isinstance(record, str) and record == "Format: " + EVENT_FORMAT:
            source.records[index] = "Format: Start, End, Style, Custom, Effect, Text"
    for line in source.lines:
        line.fields = dict.fromkeys(
            ("Start", "End", "Style", "Custom", "Effect", "Text"), ""
        )
        line.fields["Custom"] = "kept"
    result = apply_templates(Document.parse(source.dumps()))
    assert all(
        line.fields["Custom"] == "kept" for line in result.lines if line.effect == "fx"
    )
    assert apply_templates(Document.parse(result.dumps())).dumps() == result.dumps()
    # A native compatibility node still works when source Format has no Effect.
    plain = Document.parse(
        "[V4+ Styles]\nFormat: "
        + STYLE_FORMAT
        + "\n"
        + Style().serialize()
        + "\n[Events]\nFormat: Start, End, Text\nDialogue: 0:00:00.00,0:00:01.00,kept\n"
    )
    compiled = (
        Scene(plain)
        .add(NativeEvent("native", Line(text="added", end_time=1000)))
        .compile()
    )
    assert len(Document.parse(compiled.document.dumps()).lines) == 3


def test_preprocessing_retains_event_identity_and_layout_module_api():
    from kara_templater.layout import split_karaoke

    source = document()
    event = source.lines[2]
    prepared = preprocess(event, source.styles, source.meta)
    assert prepared is event
    assert prepared.kara[1].line is event
    assert split_karaoke(r"{\k20}A")[0][1].text_stripped == "A"


def test_legacy_cli_is_explicit_and_idempotent(tmp_path):
    import subprocess
    import sys

    source = Path(__file__).parent / "fixtures/v010-karaoke.ass"
    first, second = tmp_path / "first.ass", tmp_path / "second.ass"
    for incoming, output in ((source, first), (first, second)):
        run = subprocess.run(
            [
                sys.executable,
                "-m",
                "kara_templater",
                str(incoming),
                str(output),
                "--templates",
                "--video-size",
                "640",
                "480",
            ],
            capture_output=True,
            text=True,
        )
        assert run.returncode == 0, run.stderr
    assert first.read_bytes() == second.read_bytes()
    assert (
        Document.load(first).dumps()
        == apply_templates(Document.load(source), video_size=(640, 480)).dumps()
    )
    bad = subprocess.run(
        [
            sys.executable,
            "-m",
            "kara_templater",
            str(source),
            str(second),
            "--templates",
            "--pulse",
            "char",
        ],
        capture_output=True,
        text=True,
    )
    assert bad.returncode == 1
    assert "cannot be combined" in bad.stderr


def test_modern_owned_events_are_not_implicitly_templated():
    source = document()
    modern = Line(
        text="owned", effect="karaoke:v1:track:output", start_time=1000, end_time=2000
    )
    source.records.insert(-3, modern)
    result = apply_templates(source)
    assert sum(line.effect == "fx" for line in result.lines) == 2
    owned = next(line for line in result.lines if line.text == "owned")
    assert owned.serialize() == modern.serialize()


def test_mixed_scene_regeneration_keeps_order_and_native_pairs():
    def build(source):
        scene = Engine().to_scene(source)
        scene.add(TextObject(id="cue", text="cue", lifetime=Lifetime(0, 1)))
        return scene.compile().document

    first = build(document())
    second = build(Document.parse(first.dumps()))
    assert second.dumps() == first.dumps()
    assert second.lines[-1].text.endswith("cue")
