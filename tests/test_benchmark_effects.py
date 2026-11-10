from kara_templater import Document, Line, render_karaoke
from tools.benchmark_effects import ass_workload, effect, workload


def test_benchmark_reads_only_selected_original_comments_without_mutation(tmp_path):
    document, _ = workload(1)
    document.records.extend(
        (
            Line(
                start_time=1000,
                end_time=2000,
                text=r"{\k100}AB",
                comment=True,
                effect="karaoke",
            ),
            Line(
                start_time=1000,
                end_time=2000,
                text=r"{\k100}ignored",
                comment=True,
                effect="template syl",
            ),
            Line(start_time=1000, end_time=2000, text=r"{\k100}generated", effect="fx"),
        )
    )
    path = tmp_path / "source.ass"
    document.save(path)
    original = path.read_bytes()
    clean, items = ass_workload(
        path, styles=("Default",), karaoke_comments=True, font_family="DejaVu Sans"
    )
    assert path.read_bytes() == original
    assert len(items) == 1
    assert items[0].source.units[0].text == "AB"
    assert not any(isinstance(r, Line) for r in clean.records)
    assert isinstance(Document.load(path), Document)
    for kind in ("plain", "colors", "union4", "priority4"):
        assert render_karaoke(clean, items, effect=effect(kind)).event_count > 0
