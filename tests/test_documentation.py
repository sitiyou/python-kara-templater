"""Exercise complete author-facing snippets independently of repository examples."""

import re
from pathlib import Path

import pytest

from kara_templater import Document
from tools.check_docs import check


@pytest.mark.parametrize(
    ("page", "filename", "start", "duration"),
    (
        ("README.md", "hello.ass", 0, 3000),
        ("docs/guides/karaoke-effects.md", "karaoke.ass", 0, 5600),
        ("docs/guides/gpu-rendering.md", "song.ass", 0, 3000),
        ("docs/getting-started.md", "first-effect.ass", 0, 3000),
        ("docs/tutorials/custom-animation.md", "sparks.ass", 0, 2300),
        ("docs/tutorials/lyric-highlights.md", "lyric-arc.ass", 500, 4500),
    ),
)
def test_complete_author_script_runs_as_written(
    page, filename, start, duration, tmp_path, monkeypatch
):
    root = Path(__file__).resolve().parents[1]
    guide = (root / page).read_text(encoding="utf-8")
    scripts = re.findall(r"```python\n(.*?)\n```", guide, re.S)
    assert scripts
    monkeypatch.chdir(tmp_path)
    exec(compile(scripts[0], page, "exec"), {"__name__": "__main__"})
    output = Document.load(tmp_path / filename)
    assert (output.meta.res_x, output.meta.res_y) == (640, 360)
    events = [line for line in output.lines if not line.comment]
    assert events
    assert min(line.start_time for line in events) == start
    assert max(line.end_time for line in events) == duration


def test_document_links_and_reference_match_current_public_api():
    _, errors = check()
    assert not errors, "\n".join(errors)
