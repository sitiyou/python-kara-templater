import re
from dataclasses import replace

import pytest
from test_tracks import build, item

from examples.alternating_colors import document
from kara_templater import (
    BLUE,
    RED,
    Animate,
    Body,
    Display,
    DoubleLine,
    Layout,
    LineMatch,
    On,
    SingleLine,
    TextStyle,
    Track,
    TrackGroup,
    render_karaoke,
)
from kara_templater.track import bind_tracks


def selected(identity: str, color=RED, animations=()):
    return Track(
        source=lambda source: source.id == identity,
        body=Body(style=TextStyle(fill=color)),
        animations=animations,
    )


def test_shared_rows_follow_source_order_across_tracks_and_keep_styles():
    first = item(identity="a", window=(0, 3000))
    second = item(identity="b", window=(0, 3000))
    group = TrackGroup(
        selected("b", BLUE), selected("a"), layout=DoubleLine(position=(30, 60), gap=90)
    )
    bound = group.bind((first, second))
    assert (bound["a"].row, bound["b"].row) == (0, 1)
    assert bound["a"].config.body.text_style.fill == RED
    assert bound["b"].config.body.text_style.fill == BLUE
    assert all(track.layout is None for track in group.tracks)
    # Independent source placement is replaced by the group's common origin.
    result = render_karaoke(
        document(fontname="DejaVu Sans", text="AB"),
        items=(first, second),
        tracks=(group,),
    )
    assert result.event_count > 0
    text = "\n".join(line.text for line, _ in result.event_origins)
    # ASS uses centered alignment; the declaration's position is the box corner.
    positions = re.findall(r"\\pos\(([^,]+),([^)]+)\)", text)
    assert {float(y) for _, y in positions} == {88, 178}
    assert min(layer.box.left for layer in build(group, first).layers) == 30


def test_shared_capacity_includes_animation_tail_without_retiming():
    first = item(identity="a", window=(0, 2000))
    second = item(identity="b", window=(2000, 3000))
    group = TrackGroup(selected("a"), selected("b"), layout=SingleLine(position=(0, 0)))
    assert set(group.bind((first, second))) == {"a", "b"}
    group.tracks[0].animations = (
        On(Display.End, Animate(opacity=(1, 0), duration=200), extend_display=True),
    )
    with pytest.raises(ValueError, match="occupied"):
        group.bind((first, second))
    group.layout = DoubleLine(position=(0, 0))
    bound = group.bind((first, second))
    assert bound["a"].window.end_ms == 2200
    assert bound["a"].rules[0].during == (2000, 2200)
    assert (bound["a"].row, bound["b"].row) == (0, 1)


def test_group_ambiguity_is_checked_across_group_and_root_boundaries():
    source = item(identity="a")
    group = TrackGroup(selected("a"), layout=SingleLine(position=(0, 0)))
    for declarations in (
        (group, selected("a")),
        (group, group),
        (TrackGroup(selected("a"), selected("a"), layout=DoubleLine(position=(0, 0))),),
    ):
        with pytest.raises(ValueError, match="multiple Tracks"):
            bind_tracks(declarations, (source,))


def test_group_requires_unambiguous_layout_ownership():
    with pytest.raises(ValueError, match="explicit position"):
        TrackGroup(selected("a"), layout=DoubleLine())
    with pytest.raises(ValueError, match="child Tracks"):
        TrackGroup(
            Track(source=LineMatch(), layout=SingleLine()),
            layout=DoubleLine(position=(0, 0)),
        )
    with pytest.raises(TypeError, match="one or more"):
        TrackGroup(layout=SingleLine(position=(0, 0)))
    group = TrackGroup(selected("a"), layout=SingleLine(position=(0, 0)))
    group.tracks[0].layout = SingleLine()
    with pytest.raises(ValueError, match="child Tracks"):
        group.bind((item(identity="a"),))


def test_allocator_and_bound_configuration_do_not_leak_between_renders():
    class Stateful(Layout):
        def __init__(self):
            super().__init__(rows=2, position=(20, 50))
            self.calls = 0

        def allocate(self, items):
            self.calls += 1
            return super().allocate(items)

    layout = Stateful()
    group = TrackGroup(selected("a"), selected("b"), layout=layout)
    sources = (item(identity="a"), item(identity="b"))
    first, second = group.bind(sources), group.bind(sources)
    assert layout.calls == 0
    assert [value.row for value in first.values()] == [
        value.row for value in second.values()
    ]
    first["a"].config.body.text_style = TextStyle(fill=BLUE)
    assert second["a"].config.body.text_style.fill == RED
    assert first["a"].config.layout is not second["a"].config.layout
    assert first["a"].config.layout is not first["b"].config.layout


def test_separate_groups_allocate_independently_and_unmatched_input_survives():
    source = document(fontname="DejaVu Sans", text="AB")
    empty = TrackGroup(
        Track(source=LineMatch(style="missing")), layout=SingleLine(position=(0, 0))
    )
    result = render_karaoke(source, tracks=(empty,))
    assert result.event_count == 0
    assert result.document.records == source.records
    groups = (
        TrackGroup(selected("a"), layout=SingleLine(position=(0, 0))),
        TrackGroup(selected("b"), layout=SingleLine(position=(0, 100))),
    )
    bound = bind_tracks(groups, (item(identity="a"), item(identity="b")))
    assert all(value.row == 0 for value in bound.values())


def test_group_duplicate_ids_and_capacity_are_not_silently_overwritten():
    group = TrackGroup(Track(source=LineMatch()), layout=DoubleLine(position=(0, 0)))
    source = item()
    with pytest.raises(ValueError, match="duplicate"):
        group.bind((source, source))
    with pytest.raises(ValueError, match="occupied"):
        group.bind(tuple(replace(source, id=str(i)) for i in range(3)))
    assert build(group).layers
