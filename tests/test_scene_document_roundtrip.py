"""Lyric import preserves semantic cues while normalizing authored appearance."""

from pathlib import Path

from kara_templater import (
    BarsCue,
    CueMarker,
    CuePreset,
    Document,
    Lifetime,
    Line,
    Scene,
    Style,
    bind_lyric_cues,
    layout_document_lyrics,
)


def test_parse_preserves_cues_and_ruby_and_uses_template_appearance(tmp_path: Path):
    document = Document.create(
        styles=(Style(fontname="DejaVu Sans", fontsize=64, shadow=0),)
    )
    document.records.append(
        Line(
            start_time=1000,
            end_time=3000,
            text=CueMarker("intro", "bars").markup()
            + r"{\k100\1c&H0000FF&}AB|!ab{\k100\r}CD|!cd",
        )
    )
    path = tmp_path / "source.ass"
    document.save(path)

    def compile_source(source: Document) -> str:
        index = len(source.records) - 1
        lyrics = layout_document_lyrics(source, index, display=Lifetime(0, 4))
        bound = bind_lyric_cues(
            lyrics, {"bars": CuePreset(factory=BarsCue())}
        )
        scene = Scene(source).add(bound.group(), *bound.independent)
        scene.replace_source(index)
        return scene.ass.compile().document.dumps()

    loaded = Document.load(path)
    lyrics = loaded.lyrics_at(len(loaded.records) - 1)
    assert lyrics.body.text == "ABCD"
    assert len(lyrics.body.cues) == 1
    assert all(not run.appearance.inline_colors for run in lyrics.body.runs)
    compiled = compile_source(loaded)
    assert compiled == compile_source(Document.parse(loaded.dumps()))
