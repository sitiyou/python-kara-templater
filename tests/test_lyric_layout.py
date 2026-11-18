"""Batch allocation contracts; expected handoffs are independent of rendering."""

from dataclasses import replace

import pytest

from kara_templater import Layout, LayoutContext, LayoutLine, Placement
from kara_templater.geometry import Vec2
from kara_templater.lyric_layout import validate_placements
from kara_templater.model import Box
from kara_templater.scene import Lifetime
from kara_templater.scene_animation import TimeSpan

CONTEXT = LayoutContext(Box(80, 400, 500, 240))


def line(name: str, start: float, end: float, *, fade: float = 0.2) -> LayoutLine:
    return LayoutLine(
        id=name,
        singing=TimeSpan(start, end),
        display=Lifetime(max(0, start - 0.6), end + 0.3),
        bounds=Box(0, -10, 100, 50),
        entrance=fade,
        exit=fade,
    )


def test_two_rows_trim_optional_windows_without_moving_singing():
    lines = (line("a", 1, 2), line("b", 2, 3), line("c", 2.5, 3.5))
    placements = Layout(rows=2, gap=90).allocate(lines, CONTEXT)
    assert [p.row for p in placements] == [0, 1, 0]
    assert [p.display for p in placements] == [
        Lifetime(0.4, 2.2),
        Lifetime(1.4, 3.3),
        Lifetime(2.2, 3.8),
    ]
    assert placements[0].adjustments == ("tail shortened for c",)
    assert placements[2].adjustments == ("preview shortened after a",)
    assert placements[0].position == Vec2(80, 410)
    assert placements[1].position == Vec2(80, 500)
    assert lines[2].singing == TimeSpan(2.5, 3.5)
    three = Layout(rows=3).allocate(lines, CONTEXT)
    assert [p.row for p in three] == [0, 1, 2]
    assert [p.display for p in three] == [item.display for item in lines]


def test_capacity_policy_and_pause_reset_are_explicit():
    lines = (line("long", 1, 5), line("short", 2, 3), line("next", 3.5, 4.5))
    with pytest.raises(ValueError, match="next: row 0 occupied by long"):
        Layout(rows=2).allocate(lines, CONTEXT)
    available = Layout(rows=2, policy="available").allocate(lines, CONTEXT)
    assert [p.row for p in available] == [0, 1, 1]
    spaced = (line("first", 1, 2), line("after-gap", 10, 11))
    assert [p.row for p in Layout(rows=2).allocate(spaced, CONTEXT)] == [0, 1]
    reset = Layout(rows=2, reset_after=5)
    assert [p.row for p in reset.allocate(spaced, CONTEXT)] == [0, 0]
    assert reset.allocate(spaced, CONTEXT) == reset.allocate(spaced, CONTEXT)


def test_zero_equal_starts_short_lines_and_empty_input():
    with pytest.raises(ValueError, match="before zero"):
        line("zero", 0, 0.1)
    zero = line("zero", 0, 0.1, fade=0)
    assert Layout().allocate((zero,), CONTEXT)[0].display.start == 0
    same = (line("first", 1, 1.05), line("second", 1, 1.05))
    assert [p.row for p in Layout(rows=2).allocate(same, CONTEXT)] == [0, 1]
    with pytest.raises(ValueError, match="occupied"):
        Layout().allocate(same, CONTEXT)
    assert Layout().allocate((), CONTEXT) == ()


@pytest.mark.parametrize(
    "reset_lead,advance_solo,expected",
    [
        (True, False, [0, 1, 0, 0, None, 1]),
        (True, True, [0, 1, 0, 0, None, 0]),
        (False, False, [0, 1, 0, 1, None, 0]),
        (False, True, [0, 1, 0, 1, None, 1]),
    ],
)
def test_override_uses_lead_tags_and_full_batch_without_extra_protocols(
    reset_lead: bool, advance_solo: bool, expected: list[int | None]
):
    class Custom(Layout):
        def allocate(
            self, lines: tuple[LayoutLine, ...], context: LayoutContext
        ) -> tuple[Placement, ...]:
            result: list[Placement] = []
            cursor = 0
            for item in lines:
                if item.lead and reset_lead:
                    cursor = 0
                if "solo" in item.tags:
                    result.append(Placement(item.id, Vec2(300, 200), item.display))
                    cursor += int(advance_solo)
                    continue
                row = cursor % 2
                result.append(
                    Placement(item.id, Vec2(80, 400 + row * 90), item.display, row)
                )
                cursor += 1
            return tuple(result)

    lines = tuple(line(str(i), 1 + i * 3, 2 + i * 3) for i in range(6))
    lines = (
        *lines[:3],
        replace(lines[3], lead=True),
        replace(lines[4], tags=frozenset(("solo",))),
        lines[5],
    )
    custom = Custom(rows=2)
    placements = custom.allocate(lines, CONTEXT)
    validate_placements(lines, placements)
    assert [p.row for p in placements] == expected
    assert placements[4].position == Vec2(300, 200)
    # The same allocator has no persistent rotation, including between tracks.
    assert custom.allocate(lines, CONTEXT) == placements
    upper = Layout(position=Vec2(80, 40)).allocate((lines[0],), CONTEXT)
    assert upper[0].position == Vec2(80, 50)


def test_result_validation_enforces_identity_and_time_but_not_collision():
    lines = (line("a", 1, 2), line("b", 1, 2))
    overlap = tuple(Placement(item.id, Vec2(), item.display) for item in lines)
    validate_placements(lines, overlap)
    with pytest.raises(ValueError, match="missing placements: b"):
        validate_placements(lines, overlap[:1])
    with pytest.raises(ValueError, match="duplicate placement"):
        validate_placements(lines, (overlap[0], overlap[0]))
    with pytest.raises(ValueError, match="no source"):
        validate_placements(lines, (replace(overlap[0], id="unknown"), overlap[1]))
    with pytest.raises(ValueError, match="truncates"):
        validate_placements(
            lines, (replace(overlap[0], display=Lifetime(1, 2)), overlap[1])
        )
    with pytest.raises(ValueError, match="duplicate layout input"):
        Layout().allocate((lines[0], lines[0]), CONTEXT)
    with pytest.raises(ValueError, match="singing order"):
        Layout().allocate((line("late", 3, 4), lines[0]), CONTEXT)


def test_studio_three_rows_and_per_row_offsets():
    from kara_templater import KaraokeRows

    lines = tuple(line(str(i), i + 1, i + 2) for i in range(3))
    context = LayoutContext(Box(0, 0, 1920, 1080), script_height=1080)
    auto = KaraokeRows(rows=3, anchor="top").allocate(lines, context)
    assert [p.position for p in auto] == [Vec2(50, 90), Vec2(910, 200), Vec2(1770, 310)]
    custom = Layout(
        rows=3,
        alignment=("right", "left", "center"),
        offsets=(Vec2(0, 2), Vec2(3, 0), Vec2(1, 1)),
    ).allocate(lines, context)
    assert [p.position for p in custom] == [
        Vec2(1820, 12),
        Vec2(3, 130),
        Vec2(911, 251),
    ]
