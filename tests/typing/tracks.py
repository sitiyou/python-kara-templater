"""User-facing constructors, subclass handlers, and their negative contracts."""

from collections.abc import Callable
from typing import assert_type

from kara_templater import (
    WHITE,
    Animate,
    Animation,
    AnimationContext,
    AnimationTarget,
    Blur,
    Body,
    Color,
    ColorTransition,
    Display,
    Document,
    DoubleLine,
    Envelope,
    FadeInAnimation,
    LineMatch,
    Milliseconds,
    On,
    OutputSettings,
    Overlay,
    PaintBounds,
    PaintStyle,
    Parallel,
    PreparedKaraoke,
    RasterEstimate,
    RasterSettings,
    RenderEstimate,
    RenderResult,
    Ruby,
    RubySpan,
    Scene,
    Sequence,
    SingingPulseAnimation,
    SourceMatch,
    StyleSheet,
    Syllable,
    TextSpan,
    TextStyle,
    Track,
    TrackGroup,
    on,
    prepare_karaoke,
    prepare_track_scene,
    render_karaoke,
)


class Accent(Animation):
    def __init__(self, *, peak: float = 1.1, release: Milliseconds = 160) -> None:
        super().__init__()
        self.peak, self.release = peak, release

    @on(Syllable.Singing)
    def accent(self, event: Syllable.Singing) -> Animate:
        assert_type(event.target, AnimationTarget)
        assert_type(event.index, int)
        assert_type(event.start, int)
        return Animate(
            event.target, scale=Envelope(peak=self.peak, release=self.release)
        )


class Lead(Track):
    def __init__(self, *, source: SourceMatch, peak: float = 1.1) -> None:
        super().__init__(
            source=source,
            body=Body(style=TextStyle(fill=WHITE)),
            animations=(Accent(peak=peak),),
        )


def check(
    document: Document, event: Syllable.Singing, context: AnimationContext
) -> None:
    body = Body(style=TextStyle(blur=Blur(radius=10)), spans=(TextSpan(0, 1),))
    ruby = Ruby(style=TextStyle(font_size=20), follow="syllable")
    overlay = Overlay(style=PaintStyle(fill=WHITE), ruby=None)
    track = Track(
        source=LineMatch(style="K1"),
        body=body,
        ruby=ruby,
        overlay=overlay,
        layout=DoubleLine(),
        animations=(Accent(peak=1.2), FadeInAnimation()),
    )
    Track(source=lambda source: source.style == "K1")
    group = TrackGroup(Lead(source=LineMatch()), layout=DoubleLine(position=(20, 40)))
    assert_type(group.tracks, tuple[Track, ...])
    assert_type(render_karaoke(document, tracks=(group,)), RenderResult)
    TrackGroup(body, layout=DoubleLine())  # ty: ignore[invalid-argument-type]
    assert_type(track.body, Body)
    assert_type(track.ruby, Ruby | None)
    assert_type(track.animations, tuple[Animation, ...])
    assert_type(body.text_style, TextStyle)
    assert_type(body.spans, tuple[TextSpan, ...])
    assert_type(ruby.spans, tuple[RubySpan, ...])
    assert_type(track.styles, StyleSheet)
    assert_type(Accent().accent, Callable[[Syllable.Singing], Animate])
    assert_type(Accent().accent(event), Animate)
    assert_type(render_karaoke(document, tracks=(track,)), RenderResult)
    assert_type(Lead(source=LineMatch()), Lead)
    assert_type(next(context.events(Display.Start)), Display.Start)
    On(Display.Start, Animate(opacity=(0, 1), duration=200))
    SingingPulseAnimation(rise=lambda p: p * p)
    On(Display.Start, Sequence(Parallel(Animate(scale=1.1), Animate(opacity=0.5))))
    Ruby(spans=(RubySpan(0, 0, start=0, end=1, overlay=PaintStyle(fill=WHITE)),))
    Ruby(spans=(TextSpan(0, 1),))  # ty: ignore[invalid-argument-type]

    assert_type(ColorTransition(WHITE, WHITE)(0.5), Color)
    Animate(
        fill=lambda p: WHITE,
        blur_radius=lambda p: p * 10,
        bounds=PaintBounds(blur_radius=10),
    )
    Animate(fill=lambda p: 1.0)  # ty: ignore[invalid-argument-type]
    PaintBounds(blur_radius="large")  # ty: ignore[invalid-argument-type]

    Accent(peak="large")  # ty: ignore[invalid-argument-type]
    Accent(peek=1.2)  # ty: ignore[unknown-argument]
    Body(style="white")  # ty: ignore[invalid-argument-type]
    PaintStyle(font_size=20)  # ty: ignore[unknown-argument]
    Track(source=LineMatch(), animations=(body,))  # ty: ignore[invalid-argument-type]
    Animate(event.target, scale=lambda p: "large")  # ty: ignore[invalid-argument-type]
    SingingPulseAnimation(release="slow")  # ty: ignore[invalid-argument-type]


def raster_types(estimate: RenderEstimate) -> None:
    assert_type(estimate.raster, tuple[RasterEstimate, ...])
    settings = OutputSettings(raster=RasterSettings(max_frames=100))
    assert_type(settings.raster, RasterSettings | None)
    assert_type(estimate.raster[0].max_channel_error, int)
    RasterSettings(max_channel_error="low")  # ty: ignore[invalid-argument-type]
    RasterSettings(max_frames="many")  # ty: ignore[invalid-argument-type]
    OutputSettings(raster=True)  # ty: ignore[invalid-argument-type]


def prepared_track_scene(document: Document, track: Track) -> Scene:
    prepared = prepare_karaoke(document, tracks=(track,))
    assert_type(prepared, PreparedKaraoke)
    assert_type(prepared.diagnostics, tuple[str, ...])
    assert_type(prepared.layer_count, int)
    assert_type(prepared.scene, Scene)
    return prepared.scene


def editable_contract(document: Document, track: Track) -> Scene:
    result = prepare_track_scene(document, tracks=(track,))
    assert_type(result, PreparedKaraoke)
    assert_type(result.scene, Scene)
    return result.scene
