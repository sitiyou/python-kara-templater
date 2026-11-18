"""Singing colors follow measured clusters, actual positions and source clocks."""

from dataclasses import replace

import pytest
from test_orchestration import document, main

from kara_templater import (
    PINK,
    WHITE,
    LyricSweep,
    ObjectGroup,
    Scene,
    SceneBudget,
    Vec2,
    prepare_tracks,
)


def test_sweep_is_one_material_protocol_with_screen_position_and_seek():
    scene = prepare_tracks(
        document(), tracks=(main(effects=(*(main().effects), LyricSweep(fill=PINK, width=12),), ),)
    )
    line = scene.lines[0]
    group = line.children[0]
    assert isinstance(group, ObjectGroup)
    node = group.children[0]
    assert node.material is not None
    evaluator = scene.evaluator()
    before = evaluator.at(node.id, 0.5)
    after = evaluator.at(node.id, 1.6)
    assert (
        node.material.bands(0, 640, 0.5 - node.lifetime.start, before)[0].fill == WHITE
    )
    assert node.material.bands(0, 640, 1.6 - node.lifetime.start, after)[0].fill == PINK
    time = 1.25
    state = evaluator.at(node.id, time)
    local = time - node.lifetime.start
    first = node.material.bands(0, 640, local, state)
    shifted = replace(state, position=state.position + Vec2(100, 0))
    moved = node.material.bands(100, 740, local, shifted)
    assert [(band.start + 100, band.end + 100, band.fill) for band in first] == [
        (band.start, band.end, band.fill) for band in moved
    ]
    assert node.material.bands(0, 640, local, state) == first
    result = scene.compile(budget=SceneBudget(max_events=100_000))
    assert result.event_count > 1
    assert all(
        not event.text.startswith("{kara:v1")
        for event in result.document.lines
        if not event.comment
    )


def test_sweep_works_after_semantic_copy_and_rejects_unrepresentable_front():
    original = prepare_tracks(document(), tracks=(main(effects=(*(()),)),)).lines[0]
    clone = LyricSweep(fill=PINK)(original.copy(id="copy", delay=3))
    group = clone.children[0]
    assert isinstance(group, ObjectGroup)
    child = group.children[0]
    assert child.material is not None
    state = Scene(document()).add(clone).evaluator().at(child.id, 4.25)
    with pytest.raises(ValueError, match="axis-aligned"):
        child.material.bands(0, 640, 0.5, replace(state, rotation=45))
    assert child.material.breakpoints == pytest.approx((1 - original.time_origin, 1.5 - original.time_origin))


def test_color_factories_resolve_once_per_cluster_including_ruby():
    from kara_templater import BLUE, RED

    calls = []

    def color(line, target):
        calls.append((line.id, target.id))
        return RED if target.role == "character" else BLUE

    line = prepare_tracks(document(), tracks=(main(effects=(*(()),)),)).lines[0]
    decorated = LyricSweep(fill=color, outline=color, width=0)(line)
    assert decorated.layout == line.layout
    assert decorated.targets == line.targets
    count = len(decorated.query("character", "ruby"))
    assert len(calls) == 2 * count
    nodes = {}

    def collect(node):
        nodes[node.id] = node
        if isinstance(node, ObjectGroup):
            for child in node.children:
                collect(child)

    collect(decorated)
    for target in decorated.query("character", "ruby"):
        node = nodes[target.node_id]
        assert node.material is not None
        expected = RED if target.role == "character" else BLUE
        for time in (2.1, 0.5, 2.1):
            bands = node.material.bands(0, 640, time - node.lifetime.start, node.state)
            if time == 2.1:
                assert bands[0].fill == expected
                assert bands[0].outline == expected
    assert len(calls) == 2 * count


def test_sweep_receives_animated_base_paint_independent_of_binding_order():
    from kara_templater import BLUE, RED, Color, LyricRule, StatePatch, Tween

    plain = prepare_tracks(document(), tracks=(main(effects=(*(()),)),)).lines[0]
    rule = LyricRule("character", "singing", Tween(StatePatch(fill=RED, outline=BLUE)))
    sweep = LyricSweep(fill=PINK, width=0)
    before = sweep(plain.bind(rule))
    after = sweep(plain).bind(rule)
    scenes = [Scene(document()).add(line) for line in (before, after)]
    for scene, line in zip(scenes, (before, after), strict=True):
        group = line.children[0]
        assert isinstance(group, ObjectGroup)
        node = group.children[0]
        assert node.material is not None
        state = scene.evaluator().at(node.id, 1.25)
        assert state.fill == Color(255, 128, 128)
        assert state.outline == Color(0, 0, 128)
        bands = node.material.bands(0, 640, 1.25 - node.lifetime.start, state)
        assert {band.fill for band in bands} == {PINK, state.fill}
        assert all(band.outline == state.outline for band in bands)
    budget = SceneBudget(max_events=100_000)
    assert (
        scenes[0].compile(budget=budget).document.dumps()
        == scenes[1].compile(budget=budget).document.dumps()
    )


def test_bad_sweep_factory_is_rejected_during_construction_without_mutating_line():
    with pytest.raises(TypeError, match="Color values or factories"):
        LyricSweep(fill=3)  # ty: ignore[invalid-argument-type]
    line = prepare_tracks(document(), tracks=(main(effects=(*(()),)),)).lines[0]
    invalid = LyricSweep(fill=lambda line, target: 3)  # ty: ignore[invalid-argument-type]
    with pytest.raises(TypeError, match="factory must return Color"):
        invalid(line)
    group = line.children[0]
    assert isinstance(group, ObjectGroup)
    assert all(node.material is None for node in group.children)


@pytest.mark.parametrize("parsed", (False, True))
def test_cluster_color_factory_reaches_ass_for_constructed_and_parsed_sources(
    parsed, tmp_path
):
    from kara_templater import BLUE, GREEN, RED, Document, Line, Style, Track

    source = Document.create(
        width=320,
        height=180,
        styles=(Style(fontname="DejaVu Sans", fontsize=24, outline=0, shadow=0),),
    )
    source.records.append(Line(text=r"{\k20}ABCABC|abc", start_time=0, end_time=400))
    if parsed:
        path = tmp_path / "input.ass"
        source.save(path)
        source = Document.load(path)
    original = source.dumps()
    calls = []
    colors = (RED, GREEN, BLUE)

    def color(line, target):
        calls.append(target.id)
        return colors[line.query(target.role).index(target) % 3]

    configured = Track(
        id="colors", preview=0, tail=0, effects=(LyricSweep(fill=color, width=0),)
    )
    scene = prepare_tracks(source, tracks=(configured,))
    assert len(calls) == 9
    result = scene.compile(budget=SceneBudget(max_events=100_000))
    assert len(calls) == 9
    final = [
        event
        for event, _ in result.event_origins
        if event.start_time <= 350 < event.end_time
    ]
    assert len(final) == 9
    for event, text, color_value in zip(final, "ABCABCabc", colors * 3, strict=True):
        assert event.text.endswith(text)
        assert (
            rf"\1c&H{color_value.blue:02X}{color_value.green:02X}{color_value.red:02X}&"
            in event.text
        )
    assert source.dumps() == original
    assert (
        prepare_tracks(source, tracks=(configured,))
        .compile(budget=SceneBudget(max_events=100_000))
        .document.dumps()
        == result.document.dumps()
    )


def test_repeated_readings_keep_independent_sweep_clocks():
    from kara_templater import Document, Line, Style, Track

    source = Document.create(styles=(Style(fontname="DejaVu Sans", fontsize=24),))
    source.records.append(
        Line(text=r"{\k20}AB|ab{\kt40\k20}#|cd", start_time=1000, end_time=1800)
    )
    scene = prepare_tracks(
        source,
        tracks=(
            Track(
                id="repeat",
                preview=0,
                tail=0,
                effects=(LyricSweep(fill=PINK, width=0),),
            ),
        ),
    )
    line = scene.lines[0]
    readings = line.query("ruby")
    assert len(readings) == 4
    expected = ((1, 1.2), (1, 1.2), (1.4, 1.6), (1.4, 1.6))
    for target, interval in zip(readings, expected, strict=True):
        assert (target.singing[0].start, target.singing[0].end) == pytest.approx(
            interval
        )
    nodes = {}

    def collect(node):
        nodes[node.id] = node
        if isinstance(node, ObjectGroup):
            for child in node.children:
                collect(child)

    collect(line)
    for index, target in enumerate(readings):
        node = nodes[target.node_id]
        assert node.material is not None
        for time in (1.7, 1.3, 1.1, 1.7):
            state = scene.evaluator().at(node.id, time)
            bands = node.material.bands(0, 640, time - node.lifetime.start, state)
            if time == 1.3:
                assert {band.fill for band in bands} == {PINK if index < 2 else WHITE}
            elif time == 1.7:
                assert {band.fill for band in bands} == {PINK}


def test_factory_can_preserve_ruby_material_while_coloring_body():
    from kara_templater import BLUE, RED, LyricRule, StateFunction

    original = prepare_tracks(document(), tracks=(main(effects=(*(()),)),)).lines[0]
    ruby_only = LyricSweep(
        fill=lambda line, target: BLUE if target.role == "ruby" else None
    )(original)
    changed = LyricSweep(
        fill=lambda line, target: RED if target.role == "character" else None
    )(ruby_only)
    assert changed.layout == original.layout
    nodes = {}

    def collect(node):
        nodes[node.id] = node
        if isinstance(node, ObjectGroup):
            for child in node.children:
                collect(child)

    collect(ruby_only)
    ruby_fields = {
        target.node_id: nodes[target.node_id].material
        for target in ruby_only.query("ruby")
    }
    collect(changed)
    for identity, field in ruby_fields.items():
        assert field is not None
        assert nodes[identity].material is field
    assert all(
        nodes[target.node_id].material is not None
        for target in changed.query("character")
    )
    # Both omitted channels leave a preexisting material attached, and the
    # untouched fill/outline still receives ordinary animation before painting.
    untouched = LyricSweep(fill=lambda line, target: None)(original)
    animated = untouched.bind(
        LyricRule(
            "ruby",
            "enter",
            StateFunction(
                lambda state, p: replace(state, fill=BLUE),
                frozenset(("fill",)),
            ),
            duration=0.1,
        )
    )
    collect(animated)
    for target in animated.query("ruby"):
        assert nodes[target.node_id].material is None
        assert nodes[target.node_id].at(0.5).fill == BLUE


def test_local_singing_colors_preserve_role_geometry_and_base_paint():
    from kara_templater import BLUE, GREEN, RED, Document, Line, Style, Track

    source = Document.create(
        styles=(Style(fontname="DejaVu Sans", fontsize=32, outline=5, shadow=0),)
    )
    source.records.append(Line(text=r"{\k100}AB|ab", start_time=1000, end_time=2000))
    plain = prepare_tracks(
        source, tracks=(Track(id="main", preview=0, tail=0.5),)
    ).lines[0]
    first = plain.query("character")[0].node_id
    ruby_ids = {target.node_id for target in plain.query("ruby")}

    def style(node):
        if isinstance(node, ObjectGroup):
            return replace(
                node, children=tuple(style(child) for child in node.children)
            )
        return replace(
            node,
            state=replace(
                node.state,
                outline=RED if node.id == first else BLUE,
                border=3 if node.id in ruby_ids else 5,
                blur=6 if node.id in ruby_ids else 10,
            ),
        )

    base = style(plain)
    painted = LyricSweep(
        fill=lambda line, target: (
            GREEN if target.node_id == first or target.role == "ruby" else RED
        ),
        width=0,
    )(base)
    assert painted.layout == base.layout
    assert painted.targets == base.targets
    before = Scene(source).add(base).evaluator()
    after = Scene(source).add(painted).evaluator()
    nodes = {
        child.id: child
        for group in painted.children
        if isinstance(group, ObjectGroup)
        for child in group.children
    }
    for target in painted.query("character", "ruby"):
        state = after.at(target.node_id, 2.1)
        assert state == before.at(target.node_id, 2.1)
        assert state.border == (3 if target.role == "ruby" else 5)
        assert state.blur == (6 if target.role == "ruby" else 10)
        material = nodes[target.node_id].material
        assert material is not None
        bands = material.bands(
            -1000, 1000, 2.1 - nodes[target.node_id].lifetime.start, state
        )
        assert all(b.outline == state.outline for b in bands)
        expected = GREEN if target.node_id == first or target.role == "ruby" else RED
        assert all(b.fill == expected for b in bands)
    assert all(c.object.state.border == 5 for c in plain.layout.body.characters)
    assert Scene(source).add(painted).compile().event_count > 0


@pytest.mark.parametrize("delay", (0, 3))
def test_instant_singing_changes_body_and_ruby_at_exact_source_clock(delay):
    from kara_templater import (
        RED,
        Document,
        Lifetime,
        Line,
        LyricLine,
        Style,
        layout_document_lyrics,
    )
    from kara_templater._raster import rasterize
    from kara_templater.paint_fields import PaintActivity

    doc = Document.create(
        width=160,
        height=100,
        styles=(Style(fontname="DejaVu Sans", fontsize=28, outline=0, shadow=0),),
    )
    doc.records.append(Line(text=r"{\k0}A|a", start_time=1000, end_time=2000))
    index = len(doc.records) - 1
    plain = LyricLine.from_layout(
        layout_document_lyrics(doc, index, display=Lifetime(0, 3))
    )
    plain = replace(plain, state=replace(plain.state, position=Vec2(60, 60)))
    plain = plain.copy(id="instant", delay=delay)
    painted = LyricSweep(fill=RED, width=0)(plain)
    assert painted.targets == plain.targets
    nodes = {
        child.id: child
        for group in painted.children
        if isinstance(group, ObjectGroup)
        for child in group.children
    }
    for target in painted.query("character", "ruby"):
        node = nodes[target.node_id]
        assert node.material is not None
        assert isinstance(node.material, PaintActivity)
        assert node.material.active_intervals == ()
        assert node.material.breakpoints == (1,)
        for time in (0.99, 1, 1.01, 2.5):
            bands = node.material.bands(
                -1000, 1000, time + delay - node.time_origin, node.state
            )
            assert {band.fill for band in bands} == {
                node.state.fill if time < 1 else RED
            }

    def colored(node):
        if isinstance(node, ObjectGroup):
            return replace(
                node, children=tuple(colored(child) for child in node.children)
            )
        return replace(node, state=replace(node.state, fill=RED))

    budget = SceneBudget(fps=1)
    rendered = Scene(doc, replace_records={index}).add(painted).compile(budget=budget)
    for time, reference in (
        (990, plain),
        (1000, colored(plain)),
        (2500, colored(plain)),
    ):
        expected = (
            Scene(doc, replace_records={index}).add(reference).compile(budget=budget)
        )
        frame = rasterize(rendered.document.dumps(), time + delay * 1000, (160, 100))
        assert any(frame.rgba)
        assert (
            frame.rgba
            == rasterize(
                expected.document.dumps(), time + delay * 1000, (160, 100)
            ).rgba
        )
