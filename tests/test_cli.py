import subprocess
import sys
from pathlib import Path

from kara_templater import Document

EXAMPLE = Path(__file__).resolve().parents[1] / "examples/karaoke.ass"


def cli(*args, ass=True):
    return subprocess.run(
        [sys.executable, "-m", "kara_templater", *(["--ass"] if ass else []), *map(str, args)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_track_configuration_and_scene_builder(tmp_path):
    track_script = tmp_path / "track.py"
    track_script.write_text(
        "from kara_templater import RED\n"
        "from kara_templater import Track\n"
        "from kara_templater import LyricHighlights, StatePatch\n"
        "tracks = (Track(id='lyrics', effects=(LyricHighlights.from_singing(StatePatch(fill=RED)),)),)\n"
    )
    scene_script = tmp_path / "scene.py"
    scene_script.write_text(
        "from kara_templater import Scene, TextObject, Lifetime\n"
        "def build(document):\n"
        "    return Scene(document).add(TextObject(id='caption', text='SCENE', lifetime=Lifetime(0, 1)))\n"
    )
    for script, fragment in ((track_script, r"\1c&H0000FF&"), (scene_script, "SCENE")):
        output = tmp_path / (script.stem + ".ass")
        result = cli(EXAMPLE, output, "--effect", script)
        assert result.returncode == 0, result.stderr
        assert fragment in output.read_text(encoding="utf-8-sig")




def test_cli_sampling_error_keeps_source_and_writes_no_partial_file(tmp_path):
    script = tmp_path / "broken.py"
    script.write_text(
        "from kara_templater import StateFunction\n"
        "from kara_templater import Track\n"
        "from kara_templater import LyricRule\n"
        "def broken(state, progress):\n"
        "    raise RuntimeError('property failed')\n"
        "tracks = (Track(id='lyrics', effects=(LyricRule('syllable', 'singing', StateFunction(broken, frozenset(('position',)))),)),)\n"
    )
    output = tmp_path / "result.ass"
    result = cli(EXAMPLE, output, "--effect", script)
    assert result.returncode == 1
    assert "requires frame sampling" in result.stderr
    assert "SourceRef(item_id=" in result.stderr
    assert not output.exists()


def test_cli_preflight_precedes_dynamic_callbacks(tmp_path):
    script = tmp_path / "sampled.py"
    script.write_text(
        "from kara_templater import StateFunction\n"
        "from kara_templater import Track\n"
        "from kara_templater import LyricRule\n"
        "def sample(state, progress):\n"
        "    print('PROPERTY_STARTED', flush=True)\n"
        "    return state\n"
        "tracks = (Track(id='lyrics', effects=(LyricRule('syllable', 'singing', StateFunction(sample, frozenset(('position',)))),)),)\n"
    )
    output = tmp_path / "output.ass"
    rejected = cli(EXAMPLE, output, "--effect", script, "--max-events", 1)
    assert rejected.returncode == 1 and "requires frame sampling" in rejected.stderr
    assert "PROPERTY_STARTED" not in rejected.stdout
    assert not output.exists()
    result = cli(EXAMPLE, output, "--effect", script)
    assert result.returncode == 1 and "requires frame sampling" in result.stderr
    assert "PROPERTY_STARTED" not in result.stdout
    assert not output.exists()


def test_cli_rejects_ambiguous_builder_and_invalid_scene_result(tmp_path):
    output = tmp_path / "output.ass"
    script = tmp_path / "invalid.py"
    for source, message in (
        ("tracks = ()\ndef build(document): return None\n", "either tracks or build"),
        ("def build(document): return None\n", "must return Scene"),
        ("build = 42\n", "must be callable"),
    ):
        script.write_text(source)
        result = cli(EXAMPLE, output, "--effect", script)
        assert result.returncode == 1 and message in result.stderr
        assert not output.exists()


def test_cli_import_colors_and_repeat(tmp_path):
    first, second = tmp_path / "first.ass", tmp_path / "second.ass"
    run = cli(EXAMPLE, first, "--after", "#33ddff")
    assert run.returncode == 0, run.stderr
    again = cli(first, second, "--after", "#33ddff")
    assert again.returncode == 0, again.stderr
    assert first.read_bytes() == second.read_bytes()
    assert any(
        line.effect.startswith("kara:scene:v1:") for line in Document.load(first).lines
    )


def test_cli_multiple_readings_and_pause(tmp_path):
    output = tmp_path / "multi.ass"
    result = cli(EXAMPLE.with_name("multi_reading.ass"), output)
    assert result.returncode == 0, result.stderr
    document = Document.load(output)
    ruby = [line for line in document.lines if not line.comment]
    assert any(line.text.endswith("a") for line in ruby)
    assert any(line.text.endswith("b") for line in ruby)


def test_cli_before_only_keeps_source_sung_color(tmp_path):
    source = Document.load(EXAMPLE)
    for style in source.styles.values():
        style.fields.update(PrimaryColour="&H00FF0000", SecondaryColour="&H0000FF00")
    input_path, output_path = tmp_path / "source.ass", tmp_path / "output.ass"
    source.save(input_path)
    result = cli(input_path, output_path, "--before", "#112233")
    assert result.returncode == 0, result.stderr
    generated = [line for line in Document.load(output_path).lines if not line.comment]
    assert any(r"\1c&H332211&" in line.text for line in generated)
    assert any(r"\1c&HFF0000&" in line.text for line in generated)


def test_cli_invalid_recipe_and_limit_do_not_write_output(tmp_path):
    output = tmp_path / "output.ass"
    result = cli(EXAMPLE, output, "--max-events", 1)
    assert result.returncode == 1 and "budget exceeded" in result.stderr
    assert not output.exists()
    script = tmp_path / "empty.py"
    script.write_text("x = 1\n")
    result = cli(EXAMPLE, output, "--effect", script)
    assert result.returncode == 1 and "must export" in result.stderr
    assert not output.exists()


def test_cli_hard_space_can_be_laid_out_and_rendered(tmp_path):
    source = Document.load(EXAMPLE)
    lyric = next(line for line in source.lines if not line.comment)
    lyric.text = r"{\k100}A\hB"
    input_path, output_path = tmp_path / "hard-space.ass", tmp_path / "rendered.ass"
    source.save(input_path)
    run = cli(input_path, output_path)
    assert run.returncode == 0, run.stderr
    generated = [line for line in Document.load(output_path).lines if not line.comment]
    assert any(line.text.endswith("A") for line in generated)
    assert any(line.text.endswith("B") for line in generated)


def test_cli_loads_track_with_arbitrary_row_layout(tmp_path):
    script = tmp_path / "group.py"
    script.write_text(
        "from kara_templater import Vec2\n"
        "from kara_templater import Track\n"
        "from kara_templater import Layout\n"
        "tracks = (Track(id='lyrics', layout=Layout(rows=3, position=Vec2(30,60))),)\n"
    )
    output = tmp_path / "group.ass"
    run = cli(EXAMPLE, output, "--effect", script)
    assert run.returncode == 0, run.stderr
    assert output.exists()


def test_cli_rejects_removed_raster_export(tmp_path):
    output = tmp_path / "pixels.ass"
    result = cli(EXAMPLE, output, "--raster")
    assert result.returncode and "unrecognized arguments" in result.stderr
    assert not output.exists()


def test_cli_defaults_to_standalone_hook(tmp_path):
    output = tmp_path / "lyrics.hook"
    result = cli(EXAMPLE, output, ass=False)
    assert result.returncode == 0, result.stderr
    assert b"//!HOOK MAIN" in output.read_bytes()


def test_hook_cli_honors_exact_byte_budget_and_rejects_ass_only_limits(tmp_path):
    output = tmp_path / "lyrics.hook"
    assert cli(EXAMPLE, output, ass=False).returncode == 0
    expected = output.read_bytes()
    accepted = cli(EXAMPLE, output, "--max-bytes", len(expected), ass=False)
    assert accepted.returncode == 0, accepted.stderr
    rejected = cli(EXAMPLE, output, "--max-bytes", len(expected) - 1, ass=False)
    assert rejected.returncode == 1 and "Hook byte budget exceeded" in rejected.stderr
    for option in ("--max-events", "--max-active"):
        rejected = cli(EXAMPLE, output, option, 1, ass=False)
        assert rejected.returncode == 1 and "require --ass" in rejected.stderr
    assert output.read_bytes() == expected
    assert list(tmp_path.iterdir()) == [output]
