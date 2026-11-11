from test_effect_halo import build

from kara_templater import (
    Body,
    Effect,
    Halo,
    Lyrics,
    Segment,
    compile_layers,
    prepare_sampling,
)


class Base(Effect):
    def compose(self):
        yield Lyrics(Body(), Halo(opacity=0.2))


def test_group_and_constant_glow_are_lowered_without_callbacks():
    class Native(Base):
        def configure(self):
            self.syllables.on_singing(opacity=(0.2, 0.8), keep=True)
            self.query_one(Halo).on_singing(opacity=0.5, keep=True)

    plan, _, _ = build(Native())
    assert plan.dynamic is None
    assert all(l.opacity_animations for l in plan.layers)
    assert all(
        len(l.opacity_animations) == 2 for l in plan.layers if l.component == "glow"
    )
    result = compile_layers(plan.layers)
    assert result.events and all(result.origins)


def test_arbitrary_function_remains_sampled_without_early_evaluation():
    calls = []

    class Function(Base):
        def configure(self):
            self.query_one(Halo).on_singing(
                opacity=lambda p: calls.append(p) or 0.2 + p * 0.6
            )

    plan, _, _ = build(Function())
    assert plan.dynamic is not None and calls == []
    assert not any(l.opacity_animations for l in plan.layers)
    prepare_sampling(plan.layers, plan.dynamic).evaluate()
    assert calls


def test_overlapping_fade_ramp_automatically_falls_back_to_sampling():
    class Faded(Base):
        def configure(self):
            self.text.fade(in_ms=1500)
            self.syllables.on_singing(opacity=(0.2, 0.8))

    plan, _, _ = build(Faded(), segments=(Segment(1000, 2000),))
    assert plan.dynamic is not None
    assert not any(l.opacity_animations for l in plan.layers)
    assert compile_layers(prepare_sampling(plan.layers, plan.dynamic).evaluate()).events


def test_product_of_two_changing_ramps_uses_sampling_on_halo_only():
    class Product(Base):
        def configure(self):
            self.syllables.on_singing(opacity=(0.2, 0.8))
            self.query_one(Halo).on_singing(opacity=(0.3, 0.7))

    plan, _, _ = build(Product())
    assert plan.dynamic is not None
    assert all(l.opacity_animations for l in plan.layers if l.component != "glow")
    assert not any(l.opacity_animations for l in plan.layers if l.component == "glow")
    assert compile_layers(prepare_sampling(plan.layers, plan.dynamic).evaluate()).events


def test_sub_centisecond_curve_uses_existing_sampling_path():
    class Short(Base):
        def configure(self):
            self.syllables.on_singing(opacity=(0.2, 0.8))

    plan, _, _ = build(Short(), segments=(Segment(1000, 1004),))
    assert plan.dynamic is not None
    assert not any(l.opacity_animations for l in plan.layers)
    assert compile_layers(prepare_sampling(plan.layers, plan.dynamic).evaluate()).events


def test_native_opacity_combines_with_sampled_position_and_native_scale():
    class Combined(Base):
        def configure(self):
            self.text.sweep()
            self.syllables.on_singing(
                pulse=1.2, opacity=(0.2, 0.8), offset_x=lambda p: 10 * p
            )

    plan, _, _ = build(Combined())
    assert all(l.opacity_animations and l.animations for l in plan.layers)
    sampled = prepare_sampling(plan.layers, plan.dynamic).evaluate()
    assert all(l.opacity_animations for l in sampled)
    assert compile_layers(sampled).events
