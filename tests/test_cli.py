import subprocess
import sys
from pathlib import Path

from kara_templater import Document

EXAMPLE = Path(__file__).resolve().parents[1] / "examples/karaoke.ass"


def cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "kara_templater", *map(str, args)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_track_configuration_and_scene_builder(tmp_path):
    track_script = tmp_path / "track.py"
    track_script.write_text(
        "from kara_templater import RED\n"
        "from kara_templater import Track\n"
        "from kara_templater import LyricSweep\n"
        "tracks = (Track(id='lyrics', factory=LyricSweep(fill=RED, width=0).apply),)\n"
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


def test_cli_common_lyric_builder_colors_and_owner_repeat(tmp_path):
    from examples._lyrics import document
    from examples.track_colors import build

    source = document(fontname="DejaVu Sans", text="ABCABC")
    input_path = tmp_path / "source.ass"
    source.save(input_path)
    script = EXAMPLE.parents[1] / "examples/track_colors.py"
    first, second = tmp_path / "first.ass", tmp_path / "second.ass"
    for input_file, output_file in ((input_path, first), (first, second)):
        run = cli(input_file, output_file, "--effect", script)
        assert run.returncode == 0, run.stderr
    assert first.read_bytes() == second.read_bytes()
    actual = first.read_text(encoding="utf-8-sig")
    for color in (r"\1c&H0000FF&", r"\1c&H00FF00&", r"\1c&HFF0000&"):
        assert color in actual
    result = build(Document.load(input_path)).compile()
    assert all(report.strategy != "native-event" for report in result.objects)
    direct = tmp_path / "direct.ass"
    result.document.save(direct)
    assert first.read_bytes() == direct.read_bytes()


def test_cli_sampling_error_keeps_source_and_writes_no_partial_file(tmp_path):
    script = tmp_path / "broken.py"
    script.write_text(
        "from kara_templater import StateFunction\n"
        "from kara_templater import Track\n"
        "from kara_templater import LyricRule\n"
        "def broken(state, progress):\n"
        "    raise RuntimeError('property failed')\n"
        "tracks = (Track(id='lyrics', animations=(LyricRule('syllable', 'singing', StateFunction(broken, frozenset(('position',)))),)),)\n"
    )
    output = tmp_path / "result.ass"
    result = cli(EXAMPLE, output, "--effect", script)
    assert result.returncode == 1
    assert "property failed" in result.stderr
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
        "tracks = (Track(id='lyrics', animations=(LyricRule('syllable', 'singing', StateFunction(sample, frozenset(('position',)))),)),)\n"
    )
    output = tmp_path / "output.ass"
    rejected = cli(EXAMPLE, output, "--effect", script, "--max-events", 1)
    assert rejected.returncode == 1 and "budget" in rejected.stderr
    assert "PROPERTY_STARTED" not in rejected.stdout
    assert not output.exists()
    result = cli(EXAMPLE, output, "--effect", script)
    assert result.returncode == 0, result.stderr
    assert result.stdout.index("PROPERTY_STARTED") < result.stdout.index("Generated")


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


def test_cli_import_pulse_and_repeat(tmp_path):
    first, second = tmp_path / "first.ass", tmp_path / "second.ass"
    run = cli(EXAMPLE, first, "--pulse", "char", "--after", "#33ddff")
    assert run.returncode == 0, run.stderr
    again = cli(first, second, "--pulse", "char", "--after", "#33ddff")
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
    run = cli(input_path, output_path, "--pulse", "char")
    assert run.returncode == 0, run.stderr
    generated = [line for line in Document.load(output_path).lines if not line.comment]
    assert any(line.text.endswith("A") for line in generated)
    assert any(line.text.endswith("B") for line in generated)


def test_cli_declarative_layered_glow_and_owner_repeat(tmp_path):
    root = EXAMPLE.parents[1]
    script = root / "examples/layered_glow.py"
    source = root / "tests/fixtures/layered_glow.ass"
    first, second = tmp_path / "first.ass", tmp_path / "second.ass"
    run = cli(source, first, "--effect", script, "--max-events", 30_000)
    assert run.returncode == 0, run.stderr
    assert "Generated" in run.stdout
    again = cli(first, second, "--effect", script, "--max-events", 30_000)
    assert again.returncode == 0, again.stderr
    assert first.read_bytes() == second.read_bytes()


def test_layered_glow_direct_and_subclass_examples_are_equivalent(tmp_path):
    root = EXAMPLE.parents[1]
    source = root / "tests/fixtures/layered_glow.ass"
    direct, classes = tmp_path / "direct.ass", tmp_path / "classes.ass"
    for script, destination in (
        ("layered_glow.py", direct),
        ("layered_glow_classes.py", classes),
    ):
        result = cli(
            source,
            destination,
            "--effect",
            root / "examples" / script,
            "--max-events",
            30_000,
        )
        assert result.returncode == 0, result.stderr
    assert direct.read_bytes() == classes.read_bytes()


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


def test_cli_raster_color_budget_is_explicit_and_validated(tmp_path):
    from examples._lyrics import document
    from kara_templater import Line

    source = document(fontname="DejaVu Sans", text="A")
    source.styles["Default"].fontsize = 20
    source.records = [
        record for record in source.records if not isinstance(record, Line)
    ]
    source.records.append(Line(text=r"{\k10}A", start_time=0, end_time=200))
    input_path = tmp_path / "source.ass"
    source.save(input_path)
    output = tmp_path / "pixels.ass"
    for flags, message in (
        (("--raster-color-error", "4"), "requires --raster"),
        (("--raster", "--raster-color-error", "-1"), "0..255"),
    ):
        rejected = cli(input_path, output, *flags)
        assert rejected.returncode == 1
        assert message in rejected.stderr
        assert not output.exists()
    accepted = cli(input_path, output, "--raster", "--raster-color-error", "4")
    assert accepted.returncode == 0, accepted.stderr
    assert "4/255" in accepted.stdout and "YUV420" in accepted.stdout
    assert output.exists()
