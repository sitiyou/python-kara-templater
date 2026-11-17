"""Source-bound particle emission uses measured layout and finite schedules."""

import pytest

from kara_templater import (
    Document,
    Lifetime,
    Line,
    LyricLine,
    LyricParticles,
    ParticleContext,
    Petal,
    Ribbon,
    Scene,
    Sparkle,
    Style,
    Vec2,
    layout_document_lyrics,
)


def subject(text=r"{\k50}AB{\kt75\k50}#"):
    doc = Document.create(width=320, height=180, styles=(Style(fontname="DejaVu Sans", fontsize=32),))
    doc.records.append(Line(text=text, start_time=1000, end_time=2250))
    layout = layout_document_lyrics(doc, len(doc.records) - 1, id="line", display=Lifetime(0, 2.25))
    return doc, LyricLine.from_layout(layout)


def test_front_positions_follow_each_repeated_interval_and_copy_delay():
    doc, original = subject()
    line = original.copy(id="shifted", offset=Vec2(30, 20), delay=0.2)
    captured = []

    def factory(context):
        captured.append(context)
        return Sparkle()(context)

    result = LyricParticles(factory=factory, rate=4)(line)
    assert [c.birth for c in captured] == pytest.approx([1.2, 1.45, 1.95, 2.2])
    box = line.layout.body.range_bounds(0, 2)
    assert [c.position.x for c in captured] == pytest.approx([
        box.left, box.center, box.left, box.center,
    ])
    assert all(c.position.y == box.middle for c in captured)
    assert result.lifetime.end >= 2.65
    assert result.layout.lyrics == line.layout.lyrics
    output = Scene(doc).add(result).compile(native_tweens=True)
    reports = [r for r in output.objects if "/particles:" in r.id]
    assert len(reports) == 4
    assert all(r.events == 1 for r in reports)


def test_budget_is_global_and_checked_before_custom_factory_executes():
    _, line = subject()
    calls = []

    def factory(context):
        calls.append(context)
        return Sparkle()(context)

    with pytest.raises(ValueError, match="budget exceeded before factory"):
        LyricParticles(factory=factory, rate=10, max_particles=9)(line)
    assert not calls


def test_zero_spans_and_whitespace_do_not_emit():
    _, line = subject(r"{\k0}A{\k50} ")
    assert LyricParticles()(line) is line


@pytest.mark.parametrize("factory", (Sparkle(), Petal(), Ribbon()))
def test_builtin_factories_are_seekable_and_keyed(factory):
    context = ParticleContext("sample", 1, 42, Vec2(30, 40), None)
    first, second = factory(context), factory(context)
    assert first.path == second.path
    for time in (1.2, 1.1, 1.3, 1.2):
        assert first.at(time) == second.at(time)
    other = factory(ParticleContext("sample", 1, 43, Vec2(30, 40), None))
    assert first.path != other.path


def test_duplicate_emitter_identity_is_rejected():
    _, line = subject()
    effect = LyricParticles(rate=4)
    with pytest.raises(ValueError, match="duplicate lyric particle"):
        effect(effect(line))


def test_line_placement_covers_unsung_text_from_preview_without_following_front():
    _, original = subject(r"{\k50}A{\k100}BCDE")
    line = original.copy(id="delayed", delay=0.2)
    captured = []

    def factory(context):
        captured.append(context)
        return Sparkle()(context)

    result = LyricParticles(factory=factory, placement="line", rate=8, seed=42)(line)
    assert captured[0].birth == pytest.approx(0.2)
    assert captured[-1].birth < 2.7
    assert len(captured) == 20  # preview + singing, one schedule for the entire row
    box = line.layout.body.bounds
    early = [c for c in captured if c.birth < 1.2]
    assert any(c.position.x > box.center for c in early)
    assert all(box.left <= c.position.x <= box.right for c in captured)
    assert all(box.top <= c.position.y <= box.top + box.height for c in captured)
    assert all(c.position_at(1) == c.position for c in captured)
    assert result.layout.lyrics == original.layout.lyrics
    assert result.lifetime.end >= captured[-1].birth + 0.45
    positions = [c.position for c in captured]
    captured.clear()
    # A prior effect's reserved tail must not change this emitter's schedule.
    LyricParticles(factory=factory, placement="line", rate=8, seed=42)(
        line.with_display(Lifetime(0.1, 10)),
    )
    assert positions == [c.position for c in captured]
    assert captured[0].birth == pytest.approx(0.2)


def test_line_placement_budget_is_preflighted_and_silent_lines_are_skipped():
    _, line = subject()
    calls = []

    def factory(context):
        calls.append(context)
        return Sparkle()(context)

    with pytest.raises(ValueError, match="budget exceeded before factory"):
        LyricParticles(factory=factory, placement="line", rate=20, max_particles=2)(line)
    assert not calls
    for text in (r"{\k0}A", r"{\k50} "):
        _, silent = subject(text)
        assert LyricParticles(placement="line")(silent) is silent
