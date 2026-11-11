import pytest
from effect_values import sampled_layers
from source_assertions import require_origin
from test_effect_halo import build

from kara_templater import (
    Body,
    Contextual,
    Effect,
    Halo,
    Lyrics,
    OutputCapabilityError,
    Segment,
    compile_layers,
    prepare_sampling,
)


class Base(Effect):
    def compose(self):
        yield Lyrics(Body(), Halo(blur=10, max_blur=30))


@pytest.mark.parametrize("keep", [False, True])
def test_blur_and_native_opacity_coexist_and_restore_or_keep(keep):
    class Animated(Base):
        def configure(self):
            halo = self.query_one(Halo)
            halo.on_singing(opacity=(0.2, 0.8))
            halo.on_singing(blur=(10, 30), keep=keep)

    plan, _, _ = build(Animated(), segments=(Segment(1000, 2000),))
    assert plan.dynamic.max_glow_blur == 30
    assert any(layer.opacity_animations for layer in plan.layers)
    layers = sampled_layers(plan)
    for time, expected in ((500, 10), (1480, 19.6), (2480, 30 if keep else 10)):
        active = [
            l
            for l in layers
            if l.component == "glow"
            and l.active_window.start_ms <= time < l.active_window.end_ms
        ]
        assert active and all(
            l.paint.glow.blur == pytest.approx(expected) for l in active
        )
    assert compile_layers(layers).events


def test_blur_upper_bound_is_per_halo_and_errors_retain_origin():
    class Limited(Effect):
        def compose(self):
            yield Lyrics(
                Body(), Halo(id="small", max_blur=5), Halo(id="large", max_blur=100)
            )

        def configure(self):
            self.query_one("#small", Halo).on_singing(blur=lambda p: 6)
            self.query_one("#large", Halo).on_singing(blur=lambda p: 50)

    plan, item, _ = build(Limited())
    assert plan.dynamic.max_glow_blur == 100
    with pytest.raises(OutputCapabilityError, match="declared max_blur") as error:
        prepare_sampling(plan.layers, plan.dynamic).evaluate()
    assert require_origin(error.value).sources[0].item_id == item.id
    assert error.value.time_ms is not None
    assert error.value.time_ms >= 1000


def test_contextual_blur_is_not_evaluated_before_budget_check():
    calls = []

    class Context(Base):
        def configure(self):
            self.query_one(Halo).on_singing(
                blur=Contextual(lambda ctx: calls.append(ctx) or 10 + ctx.progress * 20)
            )

    plan, _, _ = build(Context())
    assert not calls
    with pytest.raises(OutputCapabilityError, match="preflight"):
        prepare_sampling(plan.layers, plan.dynamic, max_events=1)
    assert not calls
    prepare_sampling(plan.layers, plan.dynamic).evaluate()
    assert calls and all(ctx.target.kind == "halo" for ctx in calls)


def test_clipped_dynamic_blur_reserves_declared_extent_before_sampling():
    class Dynamic(Effect):
        def compose(self):
            yield Lyrics(Body(), Halo(blur=10, max_blur=30, clip="sung"))

        def configure(self):
            self.text.sweep()
            self.query_one(Halo).on_singing(blur=lambda p: 30, keep=True)

    class Static(Dynamic):
        def compose(self):
            yield Lyrics(Body(), Halo(blur=30, clip="sung"))

        def configure(self):
            self.text.sweep()

    dynamic, _, _ = build(Dynamic(), segments=(Segment(1000, 2000),))
    static, _, _ = build(Static(), segments=(Segment(1000, 2000),))
    # Blur does not alter geometry; the larger working bounds must already be
    # reserved on the unsampled plan, including sung/unsung partition clocks.
    assert [l.clips for l in dynamic.layers] == [l.clips for l in static.layers]
    assert compile_layers(sampled_layers(dynamic)).events


def test_blur_requires_a_valid_bound_and_is_not_a_body_property():
    with pytest.raises(ValueError, match="requires max_blur"):
        Halo().on_singing(blur=(0, 10))
    with pytest.raises(ValueError, match="cover its base blur"):
        Halo(blur=10, max_blur=5)
    with pytest.raises(ValueError):
        Halo(max_blur=float("inf"))

    class Invalid(Base):
        def configure(self):
            self.syllables.on_singing(glow_blur=10)  # ty: ignore[unknown-argument]

    with pytest.raises(TypeError, match="glow_blur"):
        build(Invalid())
