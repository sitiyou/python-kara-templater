"""One author recipe changes layout without changing its lyric animation rules."""

import pytest

from examples.lyric_orchestration import SongLayout, build
from kara_templater import Box, Layout, LayoutContext, Vec2


@pytest.mark.parametrize(
    "reset,advance,rows",
    (
        (True, False, [0, 1, 0, 0, None, 1]),
        (True, True, [0, 1, 0, 0, None, 0]),
        (False, False, [0, 1, 0, 1, None, 0]),
        (False, True, [0, 1, 0, 1, None, 1]),
    ),
)
def test_custom_choices_preserve_author_rules_and_do_not_leak_state(
    reset, advance, rows
):
    layout = SongLayout(
        rows=2,
        position=Vec2(100, 290),
        reset_on_lead=reset,
        advance_solo=advance,
    )
    scene = build(layout=layout)
    main = [plan for plan in scene.plans if plan.track_id == "main"]
    assert [plan.placement.row for plan in main] == rows
    assert main[3].input.lead
    assert "solo" in main[4].input.tags
    assert main[4].placement.position == Vec2(300, 260)
    harmony = [plan for plan in scene.plans if plan.track_id == "harmony"]
    assert len(harmony) == 1 and harmony[0].placement.row == 0
    assert harmony[0].placement.position.y < main[0].placement.position.y
    # Reuse exactly the same allocator instance for a different batch, then again
    # for the original song. Cursor/occupancy must remain call-local variables.
    layout.allocate(
        tuple(plan.input for plan in harmony), LayoutContext(Box(0, 0, 960, 540))
    )
    assert scene.lines == build(layout=layout).lines
    ordinary = build()
    assert [[(clip.animation, clip.duration) for clip in line.animations] for line in scene.lines] == [
        [(clip.animation, clip.duration) for clip in line.animations] for line in ordinary.lines
    ]
    assert [line.layout.lyrics for line in scene.lines] == [
        line.layout.lyrics for line in ordinary.lines
    ]


@pytest.mark.parametrize("rows", (1, 2, 3))
def test_same_song_and_animation_rules_support_any_builtin_row_count(rows):
    scene = build(layout=Layout(rows=rows, position=Vec2(100, 290)))
    main = [plan for plan in scene.plans if plan.track_id == "main"]
    # The fourth lyric opens the second three-line section with a count-in.
    assert [plan.placement.row for plan in main] == [i % rows for i in range(3)] * 2
    assert all(plan.line.animations for plan in main)
    # Layout may trim optional visibility, so exit binding times can change;
    # the authored animation definitions and source singing stay identical.
    assert [
        [(clip.animation, clip.duration) for clip in line.animations]
        for line in scene.lines
    ] == [
        [(clip.animation, clip.duration) for clip in line.animations]
        for line in build().lines
    ]
    assert [line.layout.lyrics for line in scene.lines] == [
        line.layout.lyrics for line in build().lines
    ]


def test_dense_variant_still_checks_real_capacity():
    with pytest.raises(ValueError, match="occupied"):
        build(layout=Layout(rows=1), dense=True)
    assert build(dense=True).lines
    assert build(layout=SongLayout(rows=2), dense=True).lines
