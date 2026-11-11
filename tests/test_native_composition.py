import pytest
from effect_values import properties_at
from test_effect_halo import build

from kara_templater import (
    Body,
    Effect,
    Halo,
    Lyrics,
    Segment,
    compile_layers,
    prepare_sampling,
    singing,
)


class Base(Effect):
    def compose(self):
        yield Lyrics(Body(), Halo())


@pytest.mark.parametrize("name", ["scale", "opacity"])
def test_linear_product_with_constant_is_native_and_keeps_final_value(name):
    class Product(Base):
        def configure(self):
            self.syllables.on_singing(
                **{name: (0.2, 0.8)}, compose="multiply", keep=True
            )
            self.syllables.on_singing(**{name: 0.5}, compose="multiply", keep=True)

    plan, _, _ = build(Product(), segments=(Segment(1000, 2000),))
    assert plan.dynamic is None
    for layer in plan.layers:
        for time, expected in ((900, 1), (1000, 0.1), (1500, 0.25), (2500, 0.4)):
            assert getattr(properties_at(plan, layer, time), name) == pytest.approx(
                expected
            )
    assert compile_layers(plan.layers).events


@pytest.mark.parametrize("name", ["scale", "opacity"])
def test_product_of_two_varying_factors_remains_sampled(name):
    class Product(Base):
        def configure(self):
            for _ in range(2):
                self.syllables.on_singing(**{name: (0.2, 0.8)}, compose="multiply")

    plan, _, _ = build(Product(), segments=(Segment(1000, 2000),))
    assert plan.dynamic is not None
    for layer in plan.layers:
        assert getattr(properties_at(plan, layer, 1500), name) == pytest.approx(0.25)
    assert compile_layers(prepare_sampling(plan.layers, plan.dynamic).evaluate()).events


@pytest.mark.parametrize("name", ["scale", "opacity"])
def test_override_releases_to_underlying_curve_without_restarting_it(name):
    class Override(Base):
        def configure(self):
            self.syllables.on_singing(**{name: (0.2, 0.8)}, compose="override")
            self.syllables.animate(
                **{name: 0.9},
                during=(singing.start + 200, singing.start + 400),
                compose="override",
            )

    plan, _, _ = build(Override(), segments=(Segment(1000, 2000),))
    assert plan.dynamic is None
    for layer in plan.layers:
        for time, expected in ((1100, 0.26), (1200, 0.9), (1400, 0.44), (2000, 1)):
            assert getattr(properties_at(plan, layer, time), name) == pytest.approx(
                expected
            )
    assert compile_layers(plan.layers).events


def test_zero_opacity_factor_makes_varying_product_native():
    class Invisible(Base):
        def configure(self):
            for value in ((0.2, 0.8), (0.4, 1), 0):
                self.syllables.on_singing(opacity=value, compose="multiply")

    plan, _, _ = build(Invisible())
    assert plan.dynamic is None
    assert all(properties_at(plan, layer, 1500).opacity == 0 for layer in plan.layers)


def test_short_native_scale_falls_back_before_ass_quantization():
    class Short(Base):
        def configure(self):
            self.syllables.on_singing(scale=(1, 1.2))

    plan, _, _ = build(Short(), segments=(Segment(1000, 1004),))
    assert plan.dynamic is not None
    assert not any(layer.animations for layer in plan.layers)
    assert compile_layers(prepare_sampling(plan.layers, plan.dynamic).evaluate()).events
