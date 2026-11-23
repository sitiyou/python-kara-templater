"""File input and authored Document must feed the same Scene compiler."""

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


def test_parse_before_binding_preserves_cues_colors_ruby_and_output(tmp_path: Path):
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

    assert compile_source(Document.load(path)) == compile_source(document)
