import pytest
from effect_values import properties_at
from test_effect_halo import build

from kara_templater import (
    Body,
    Effect,
    Halo,
    Keyframe,
    Keyframes,
    Lyrics,
    Segment,
    compile_layers,
    prepare_sampling,
    singing,
)


class Base(Effect):
    def compose(self):
        yield Lyrics(Body(), Halo())


@pytest.mark.parametrize("name", ["scale", "opacity", "offset_x", "offset_y"])
@pytest.mark.parametrize("keyframes", [False, True])
def test_known_singing_curve_matches_function_through_gaps_and_keep(name, keyframes):
    calls = []

    def curve(p):
        return 0.2 + 0.6 * (1 - abs(2 * p - 1)) if keyframes else 0.2 + 0.6 * p

    class Native(Base):
        def configure(self):
            expression = (
                Keyframes(Keyframe(0, 0.2), Keyframe(0.5, 0.8), Keyframe(1, 0.2))
                if keyframes
                else (0.2, 0.8)
            )
            self.syllables.on_singing(
                **{name: expression}, progress="singing", keep=True
            )

    class Function(Base):
        def configure(self):
            self.syllables.on_singing(
                **{name: lambda p: calls.append(p) or curve(p)},
                progress="singing",
                keep=True,
            )

    segments = (Segment(1000, 1200), Segment(1500, 1500), Segment(1800, 2400))
    native, _, _ = build(Native(), segments=segments)
    sampled, _, _ = build(Function(), segments=segments)
    assert native.dynamic is None
    assert sampled.dynamic is not None and not calls
    for a, b in zip(native.layers, sampled.layers, strict=True):
        for time, progress in (
            (1000, 0),
            (1100, 0.125),
            (1200, 0.25),
            (1600, 0.25),
            (2000, 0.5),
            (2100, 0.625),
            (2500, 1),
        ):
            expected = curve(progress)
            assert getattr(properties_at(native, a, time), name) == pytest.approx(
                expected
            )
            assert getattr(properties_at(sampled, b, time), name) == pytest.approx(
                expected
            )
    assert compile_layers(native.layers).events
    assert compile_layers(
        prepare_sampling(sampled.layers, sampled.dynamic).evaluate()
    ).events


def test_absolute_keyframe_maps_to_both_sides_of_pause():
    class Mapped(Base):
        def configure(self):
            self.syllables.on_singing(
                offset_x=Keyframes(
                    Keyframe(0, 0), Keyframe(singing.start + 800, 10), Keyframe(1, 0)
                ),
                progress="singing",
            )

    plan, _, _ = build(Mapped(), segments=(Segment(1000, 1200), Segment(1800, 2400)))
    assert plan.dynamic is None
    points = plan.layers[0].offsets[0].points
    assert points == ((1000, 0), (1200, 10), (1800, 10), (2400, 0))


def test_singing_progress_rejects_an_arbitrary_binding_interval():
    class Early(Base):
        def configure(self):
            self.syllables.animate(
                offset_x=(0, 100),
                during=(singing.start, singing.start + 200),
                progress="singing",
                keep=True,
            )

    with pytest.raises(ValueError, match="requires the source singing interval"):
        build(Early(), segments=(Segment(1000, 1200), Segment(1800, 2400)))


def test_zero_duration_singing_progress_remains_sampled():
    class Instant(Base):
        def configure(self):
            self.syllables.on_singing(offset_x=(0, 10), progress="singing", keep=True)

    plan, _, _ = build(Instant(), segments=(Segment(1000, 1000),))
    assert plan.dynamic is not None
    assert properties_at(plan, plan.layers[0], 1000).offset_x == 10
    assert compile_layers(prepare_sampling(plan.layers, plan.dynamic).evaluate()).events
