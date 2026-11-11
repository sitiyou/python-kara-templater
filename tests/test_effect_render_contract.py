from dataclasses import replace

import pytest
from source_assertions import require_origin

from examples.alternating_colors import document
from kara_templater import (
    Body,
    DisplayWindow,
    Effect,
    Halo,
    KaraokeItem,
    KaraokeLine,
    Lyrics,
    OutputCapabilityError,
    OutputSettings,
    SamplingSettings,
    Segment,
    TextUnit,
    render_karaoke,
)

ITEM = KaraokeItem(
    "first",
    KaraokeLine((TextUnit("AB", (Segment(1000, 2000),)),)),
    "Default",
    DisplayWindow(500, 2500),
)


def effect_with_callback(callback, *, max_samples=100000):
    class Sampled(Effect):
        def compose(self):
            yield Lyrics(Body(), Halo(clip="sung"))

        def configure(self):
            self.sampling = SamplingSettings(max_samples=max_samples)
            self.text.sweep()
            self.syllables.on_singing(offset_y=callback)

    return Sampled


def test_document_preflight_rejects_later_lyric_before_any_property_callback():
    source = document(fontname="DejaVu Sans")
    calls, estimates = [], []
    effect = effect_with_callback(lambda p: calls.append(p) or -5 * p)
    render_karaoke(source, (ITEM,), effect=effect, on_estimate=estimates.append)
    assert calls and len(estimates) == 1
    calls.clear()
    snapshot = source.dumps()
    with pytest.raises(OutputCapabilityError, match="preflight") as error:
        render_karaoke(
            source,
            (ITEM, replace(ITEM, id="second")),
            effect=effect,
            settings=OutputSettings(
                resolution=(640, 480), max_events=estimates[0].estimated_events
            ),
        )
    assert not calls
    assert require_origin(error.value).sources[0].item_id == "second"
    assert error.value.time_ms is not None
    assert source.dumps() == snapshot


def test_sample_count_budget_rejects_before_evaluation():
    calls = []
    with pytest.raises(OutputCapabilityError, match="preflight") as error:
        render_karaoke(
            document(fontname="DejaVu Sans"),
            (ITEM,),
            effect=effect_with_callback(lambda p: calls.append(p) or p, max_samples=1),
        )
    assert not calls
    assert (
        require_origin(error.value).sources[0].resolve(ITEM)
        is ITEM.source.units[0].segments[0]
    )


def test_estimate_callback_can_cancel_before_sampling_without_mutating_input():
    calls = []
    source = document(fontname="DejaVu Sans")
    snapshot = source.dumps()

    def cancel(estimate):
        assert estimate.target_samples > 0 and estimate.estimated_events > 0
        assert not calls
        raise RuntimeError("cancel at estimate")

    with pytest.raises(RuntimeError, match="cancel at estimate"):
        render_karaoke(
            source,
            (ITEM,),
            effect=effect_with_callback(lambda p: calls.append(p) or p),
            on_estimate=cancel,
        )
    assert not calls and source.dumps() == snapshot


def test_property_failure_keeps_cause_source_target_and_absolute_time():
    cause = RuntimeError("property failed")

    def fail(progress):
        raise cause

    with pytest.raises(OutputCapabilityError) as caught:
        render_karaoke(
            document(fontname="DejaVu Sans"), (ITEM,), effect=effect_with_callback(fail)
        )
    error = caught.value
    assert error.__cause__ is cause
    assert "first/" in str(error)
    assert error.time_ms is not None
    assert 1000 <= error.time_ms < 2000
    assert (
        require_origin(error).sources[0].resolve(ITEM)
        is ITEM.source.units[0].segments[0]
    )


def test_author_native_clip_precision_failure_retains_source_and_time():
    class Precise(Effect):
        def configure(self):
            self.text.sweep()
            self.syllables.on_singing(scale=(1, 2))

    with pytest.raises(OutputCapabilityError, match="ASS time resolution") as caught:
        render_karaoke(
            document(fontname="DejaVu Sans"),
            (ITEM,),
            effect=Precise,
            settings=OutputSettings(resolution=(640, 480), clip_error_px=1e-10),
        )
    assert (
        require_origin(caught.value).sources[0].resolve(ITEM)
        is ITEM.source.units[0].segments[0]
    )
    assert caught.value.time_ms is not None
    assert 1000 <= caught.value.time_ms < 2000
