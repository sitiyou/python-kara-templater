import importlib

import pytest
from test_effect_halo import build
from test_effect_selection import prepare

from examples.alternating_colors import document
from kara_templater import (
    WHITE,
    Body,
    Effect,
    Halo,
    Line,
    Lyrics,
    Ruby,
    compile_layers,
    render_karaoke,
)
from kara_templater.effect import Component


def test_each_line_binds_then_composes_configures_and_measures(monkeypatch):
    trace = []
    render_module = importlib.import_module("kara_templater.render")
    original_layout = render_module.layout_line

    def measure(source, **kwargs):
        trace.append(("layout", source.units[0].text))
        assert kwargs["style"].fontsize == 60
        return original_layout(source, **kwargs)

    monkeypatch.setattr(render_module, "layout_line", measure)

    class Ordered(Effect):
        def __init__(self):
            self.local = []

        def compose(self):
            assert self.source.source is self.syllables.source
            assert not self.local
            self.local.append("composed")
            trace.append(("compose", self.syllables.text))
            yield Lyrics(Body(id="body"), Halo(id="first"), Halo(id="second"))

        def configure(self):
            assert self.local == ["composed"]
            self.local.append("configured")
            assert [node.id for node in self.query("halo")] == ["first", "second"]
            assert self.query_one("#body") is self.body
            trace.append(("configure", self.syllables.text))
            self.body.style.font_size = 60

    source = document(fontname="DejaVu Sans", text="ABC")
    source.records.append(Line(text=r"{\k300}DEF", start_time=4000, end_time=8000))
    effect = Ordered()
    assert render_karaoke(source, effect=effect).event_count
    assert trace == [
        (phase, text)
        for text in ("ABC", "DEF")
        for phase in ("compose", "configure", "layout")
    ]
    assert effect.local == []
    assert source.styles["Default"].fontsize == 56


@pytest.mark.parametrize(
    "roots, message",
    [
        (lambda: (), "one Lyrics"),
        (lambda: (Body(),), "one Lyrics"),
        (lambda: (Lyrics(Body()), Lyrics(Body())), "one Lyrics"),
        (lambda: (Lyrics(),), "one Body"),
        (lambda: (Lyrics(Body(), Body()),), "one Body"),
        (lambda: (Lyrics(Body(), Ruby(), Ruby()),), "at most one Ruby"),
        (lambda: (Lyrics(Body(), Component()),), "unsupported component"),
    ],
)
def test_invalid_component_structure_fails_before_configure(roots, message):
    class Invalid(Effect):
        def compose(self):
            yield from roots()

        def configure(self):
            pytest.fail("configure must not run on an invalid component structure")

    with pytest.raises(ValueError, match=message):
        prepare(Invalid())


def test_default_ruby_and_halo_follow_and_appearance_contract():
    class Defaults(Effect):
        def compose(self):
            yield Lyrics(Body(), Ruby(), Halo())

        def configure(self):
            self.text.fade(in_ms=100, out_ms=100)
            self.syllables.on_singing(scale=(1, 1.2), offset_x=(0, 10))

    plan, _, _ = build(Defaults())
    for layer in plan.layers:
        assert layer.fade.in_ms == layer.fade.out_ms == 100
        ruby = layer.style.name == "ruby"
        assert bool(layer.animations) is not ruby
        assert bool(layer.offsets) is not ruby
        if layer.component == "glow":
            assert layer.paint.glow.color == WHITE
            assert layer.paint.glow.opacity == 1
            assert layer.paint.glow.border == layer.paint.glow.blur == 0


def test_author_pipeline_does_not_construct_legacy_recipe(monkeypatch):
    import kara_templater
    from kara_templater import recipe

    assert not hasattr(kara_templater, "KaraokeEffect")
    assert not hasattr(recipe, "KaraokeEffect")

    def forbidden(*args, **kwargs):
        pytest.fail("new author pipeline invoked the legacy author class")

    monkeypatch.setattr(recipe, "KaraokeEffect", forbidden, raising=False)

    class Independent(Effect):
        def compose(self):
            yield Lyrics(Body(), Ruby(follow="syllable"), Halo(clip="sung"))

        def configure(self):
            self.text.sweep()
            self.text.fade(in_ms=100, out_ms=100)
            self.syllables.on_singing(pulse=1.1, offset_x=(0, 10))

    plan, _, _ = build(Independent())
    assert plan.layers and any(layer.component == "glow" for layer in plan.layers)
    assert all(layer.origin.effect == "Independent" for layer in plan.layers)
    assert compile_layers(plan.layers).events


def test_typed_queries_preserve_subclasses_and_require_exactly_one_match():
    class AccentBody(Body):
        pass

    class AccentHalo(Halo):
        pass

    class Typed(Effect):
        def compose(self):
            yield Lyrics(
                AccentBody(id="body"),
                Ruby(id="ruby"),
                Halo(id="first", classes="accent"),
                AccentHalo(id="second", classes="accent"),
            )

    effect, _ = prepare(Typed())
    assert effect.query(Body) == (effect.body,)
    assert isinstance(effect.query_one(AccentBody), AccentBody)
    assert effect.query_one("#body", AccentBody) is effect.body
    assert effect.query_one(Ruby) is effect.ruby
    assert [node.id for node in effect.query(Halo)] == ["first", "second"]
    assert effect.query_one(AccentHalo).id == "second"
    assert effect.query(".accent") == effect.query(Halo)
    with pytest.raises(TypeError, match="expected Ruby, found AccentBody"):
        effect.query_one("#body", Ruby)
    with pytest.raises(ValueError, match="found 2"):
        effect.query_one(Halo)
    with pytest.raises(ValueError, match="found 2"):
        effect.query_one(".accent", Halo)
    with pytest.raises(ValueError, match="found 0"):
        effect.query_one("#absent", Body)
