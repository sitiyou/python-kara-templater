"""Execute documented declarations and bind them to real structured lyrics."""

import ast
import re
from dataclasses import replace
from pathlib import Path

import pytest

import kara_templater as kt
from examples.alternating_colors import document


def exercise(
    value: object, source: kt.Document, items: tuple[kt.KaraokeItem, ...]
) -> bool:
    tracks: tuple[kt.Track | kt.TrackGroup, ...]
    if isinstance(value, (kt.Track, kt.TrackGroup)):
        tracks = (value,)
    elif isinstance(value, kt.Body):
        tracks = (kt.Track(source=kt.LineMatch(), body=value),)
    elif isinstance(value, kt.Ruby):
        tracks = (kt.Track(source=kt.LineMatch(), ruby=value),)
    elif isinstance(value, kt.Overlay):
        tracks = (kt.Track(source=kt.LineMatch(), ruby=kt.Ruby(), overlay=value),)
    elif isinstance(value, kt.Animation):
        tracks = (
            kt.Track(
                source=kt.LineMatch(),
                body=kt.Body(style=kt.TextStyle(blur=kt.Blur(radius=2))),
                animations=(value,),
            ),
        )
    elif isinstance(value, kt.RenderResult):
        assert value.event_count > 0
        return True
    elif isinstance(value, kt.CoverageResult):
        assert value.output.event_count > 0
        return True
    elif isinstance(value, tuple):
        results = [exercise(member, source, items) for member in value]
        return any(results)
    else:
        return False
    result = kt.render_karaoke(source, items=items, tracks=tracks)
    assert result.event_count > 0
    return True


@pytest.mark.parametrize(
    "filename",
    (
        "tracks.md",
        "track-effects-plan.md",
        "track-migration.md",
        "animation-timelines.md",
    ),
)
def test_documented_track_declarations_render(filename, tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(tmp_path)
    source = document(fontname="DejaVu Sans", text="ABCABC")
    source.records = [
        record for record in source.records if not isinstance(record, kt.Line)
    ]
    base = source.styles["Default"]
    items = []
    for index, name in enumerate(("K1", "K2", "LEAD")):
        source.records.append(replace(base, name=name))
        source.records.append(
            kt.Line(text=r"{\k200}ABCABC", style=name, start_time=0, end_time=3000)
        )
        items.append(
            kt.KaraokeItem(
                str(index),
                kt.KaraokeLine(
                    (kt.TextUnit("ABCABC", (kt.Segment(1000, 2000, "abc"),)),)
                ),
                name,
                kt.DisplayWindow(0, 3000),
            )
        )
    namespace: dict[str, object] = {name: getattr(kt, name) for name in kt.__all__}
    namespace["document"] = source
    captures: list[object] = []
    namespace["_capture"] = captures.append
    examples = re.findall(
        r"```python\n(.*?)\n```",
        (root / "docs" / filename).read_text(encoding="utf-8"),
        re.S,
    )
    for index, example in enumerate(examples):
        tree = ast.parse(example)
        for node in tree.body:
            # Also retain bare declarations like Body(...) and On(...).
            if isinstance(node, ast.Expr):
                node.value = ast.Call(
                    func=ast.Name(id="_capture", ctx=ast.Load()),
                    args=[node.value],
                    keywords=[],
                )
        exec(
            compile(
                ast.fix_missing_locations(tree), f"{filename}:example-{index}", "exec"
            ),
            namespace,
        )
    candidates = [
        *captures,
        *(
            value
            for name, value in namespace.items()
            if name not in kt.__all__ and not name.startswith("_")
        ),
    ]
    results = [exercise(value, source, tuple(items)) for value in candidates]
    assert any(results)


def test_readme_track_example_runs_as_written(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    input_path = tmp_path / "input.ass"
    original = (root / "tests/fixtures/layered_glow.ass").read_bytes()
    input_path.write_bytes(original)
    monkeypatch.chdir(tmp_path)
    example = re.findall(
        r"```python\n(.*?)\n```",
        (root / "README.md")
        .read_text(encoding="utf-8")
        .split("## Configure tracks", 1)[1]
        .split("\n## ", 1)[0],
        re.S,
    )[0]
    exec(compile(example, "README.md:Track", "exec"), {})
    assert input_path.read_bytes() == original
    result = kt.Document.load(tmp_path / "output.ass")
    assert any(line.effect.startswith("karaoke:v1:") for line in result.lines)
