from dataclasses import FrozenInstanceError

import pytest
from effect_values import properties_at
from test_effect_halo import build

from kara_templater import (
    Body,
    Contextual,
    Effect,
    Halo,
    Lyrics,
    OutputCapabilityError,
    Ruby,
    Segment,
    SourceRef,
    compile_layers,
    prepare_sampling,
)


class Base(Effect):
    def compose(self):
        yield Lyrics(Body(), Ruby(follow="syllable"), Halo())


def test_context_is_deferred_and_contains_original_time_progress_and_source():
    seen = []

    class Timed(Base):
        def configure(self):
            self.syllables.on_singing(
                offset_x=Contextual(lambda ctx: seen.append(ctx) or ctx.progress * 20),
                progress="singing",
                keep=True,
            )

    plan, item, _ = build(Timed(), segments=(Segment(1000, 1200), Segment(1800, 2400)))
    assert plan.dynamic is not None and not seen
    layer = next(l for l in plan.layers if l.component != "glow")
    assert properties_at(plan, layer, 1600).offset_x == 5
    context = seen[-1]
    assert context.time_ms == 1600 and context.progress == 0.25
    assert context.interval == (1000, 2400) and context.window == item.window
    assert context.target.text == layer.text and context.target.kind == "body"
    assert context.target.sources == (
        SourceRef(item.id, 0, 0),
        SourceRef(item.id, 0, 1),
    )
    with pytest.raises(FrozenInstanceError):
        context.target.text = "changed"
    assert properties_at(plan, layer, 2800).offset_x == 20
    assert seen[-1].time_ms == 2400 and seen[-1].progress == 1
    seen.clear()
    with pytest.raises(OutputCapabilityError, match="preflight"):
        prepare_sampling(plan.layers, plan.dynamic, max_events=1)
    assert not seen


def test_contextual_followers_share_original_target_noise_and_repeat_output():
    class Noisy(Base):
        def configure(self):
            self.syllables.on_singing(
                offset_y=Contextual(
                    lambda ctx: ctx.noise("phase", animated=False), seed=42
                )
            )

    first, _, _ = build(Noisy())
    for text in {l.text for l in first.layers}:
        layers = [l for l in first.layers if l.text == text]
        offsets = [properties_at(first, l, 1500).offset_y for l in layers]
        assert len(set(offsets)) == 1
        assert offsets[0] == properties_at(first, layers[0], 1700).offset_y
    second, _, _ = build(Noisy())
    a = compile_layers(prepare_sampling(first.layers, first.dynamic).evaluate()).events
    b = compile_layers(
        prepare_sampling(second.layers, second.dynamic).evaluate()
    ).events
    assert [e.serialize() for e in a] == [e.serialize() for e in b]


def test_contextual_halo_uses_own_target_and_validates_result_with_source():
    seen = []

    class HaloValue(Base):
        def configure(self):
            self.query_one("halo").on_singing(
                opacity=Contextual(lambda ctx: seen.append(ctx) or 2)
            )

    plan, item, _ = build(HaloValue())
    assert not seen
    with pytest.raises(OutputCapabilityError, match="opacity must be") as error:
        prepare_sampling(plan.layers, plan.dynamic).evaluate()
    assert seen[-1].target.kind == "halo"
    assert error.value.origin.sources[0].item_id == item.id
    assert error.value.time_ms is not None


@pytest.mark.parametrize("function,seed", [(None, 0), (lambda c: 0, True)])
def test_contextual_input_validation(function, seed):
    with pytest.raises(TypeError):
        Contextual(function, seed=seed)


def test_source_scoped_noise_aligns_independent_halo_and_body_properties():
    expression = Contextual(
        lambda ctx: ctx.noise("shared", animated=False, scope="source"), seed=42
    )

    class Shared(Base):
        def configure(self):
            self.syllables.on_singing(offset_x=expression)
            self.query_one("halo").on_singing(opacity=expression)

    plan, item, _ = build(Shared())
    for layer in plan.layers:
        if layer.component == "glow":
            segment = layer.origin.sources[0].resolve(item)
            state = properties_at(plan, layer, (segment.start_ms + segment.end_ms) / 2)
            assert state.glow_opacity == state.offset_x
