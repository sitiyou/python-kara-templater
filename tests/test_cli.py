import subprocess
import sys
from pathlib import Path

from kara_templater import Document

EXAMPLE = Path(__file__).resolve().parents[1] / "examples/karaoke.ass"


def test_cli_reports_sampling_source_without_writing_partial_output(tmp_path):
    script = tmp_path / "broken.py"
    script.write_text(
        "from kara_templater import Effect\n"
        "def broken(context):\n"
        "    raise RuntimeError('property failed')\n"
        "class Broken(Effect):\n"
        "    def configure(self):\n"
        "        self.syllables.on_singing(offset_y=broken)\n"
        "effect = Broken\n"
    )
    output = tmp_path / "result.ass"
    run = cli(EXAMPLE, output, "--effect", script)
    assert run.returncode == 1
    assert "property failed" in run.stderr
    assert "effect=Broken" in run.stderr
    assert "SourceRef(item_id=" in run.stderr
    assert "segment_index=0" in run.stderr
    assert not output.exists()


def cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "kara_templater", *map(str, args)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_import_pulse_and_repeat(tmp_path):
    first, second = tmp_path / "first.ass", tmp_path / "second.ass"
    run = cli(EXAMPLE, first, "--pulse", "char", "--after", "#33ddff")
    assert run.returncode == 0, run.stderr
    again = cli(first, second, "--pulse", "char", "--after", "#33ddff")
    assert again.returncode == 0, again.stderr
    assert first.read_bytes() == second.read_bytes()
    assert any(
        line.effect.startswith("karaoke:v1:") for line in Document.load(first).lines
    )


def test_cli_python_recipe(tmp_path):
    script = tmp_path / "effect.py"
    script.write_text(
        "from kara_templater import Effect, RED\n"
        "class Red(Effect):\n"
        "    def configure(self):\n"
        "        self.text.sweep(fill=RED)\n"
        "effect = Red\n"
    )
    output = tmp_path / "output.ass"
    result = cli(EXAMPLE, output, "--effect", script)
    assert result.returncode == 0, result.stderr
    assert r"\1c&H0000FF&" in output.read_text(encoding="utf-8-sig")


def test_cli_multiple_readings_and_pause(tmp_path):
    output = tmp_path / "multi.ass"
    result = cli(EXAMPLE.with_name("multi_reading.ass"), output)
    assert result.returncode == 0, result.stderr
    document = Document.load(output)
    ruby = [
        line
        for line in document.lines
        if not line.comment and line.style == "Default-ruby"
    ]
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


def test_cli_song_effect_uses_effect_components_and_preserves_owner_repeat(tmp_path):
    from examples.song_effect import SongEffect, effect
    from kara_templater import Effect

    assert effect is SongEffect and issubclass(effect, Effect)
    script = EXAMPLE.parent / "song_effect.py"
    first, second = tmp_path / "first.ass", tmp_path / "second.ass"
    run = cli(EXAMPLE, first, "--effect", script)
    assert run.returncode == 0, run.stderr
    repeat = cli(first, second, "--effect", script)
    assert repeat.returncode == 0, repeat.stderr
    assert first.read_bytes() == second.read_bytes()


def test_cli_contextual_dynamic_blur_script_is_repeatable(tmp_path):
    from examples.dynamic_effect import DynamicGlow, effect
    from kara_templater import Effect

    assert effect is DynamicGlow and issubclass(effect, Effect)
    script = EXAMPLE.parent / "dynamic_effect.py"
    first, second = tmp_path / "first.ass", tmp_path / "second.ass"
    run = cli(EXAMPLE, first, "--effect", script, "--max-events", 100000)
    assert run.returncode == 0, run.stderr
    assert "Preflight:" in run.stdout
    repeat = cli(first, second, "--effect", script, "--max-events", 100000)
    assert repeat.returncode == 0, repeat.stderr
    assert first.read_bytes() == second.read_bytes()


def test_cli_invalid_recipe_and_limit_do_not_write_output(tmp_path):
    output = tmp_path / "output.ass"
    result = cli(EXAMPLE, output, "--max-events", 1)
    assert result.returncode == 1 and "exceeds" in result.stderr
    assert not output.exists()
    script = tmp_path / "empty.py"
    script.write_text("x = 1\n")
    result = cli(EXAMPLE, output, "--effect", script)
    assert result.returncode == 1 and "must export" in result.stderr
    assert not output.exists()


def test_cli_reports_cost_before_property_callbacks(tmp_path):
    script = tmp_path / "dynamic.py"
    script.write_text(
        "from kara_templater import Effect\n"
        "seen = []\n"
        "def sample(ctx):\n"
        "    if not seen: print('PROPERTY_STARTED', flush=True)\n"
        "    seen.append(ctx)\n"
        "    return 0\n"
        "class Sampled(Effect):\n"
        "    def configure(self):\n"
        "        self.syllables.on_singing(offset_y=sample)\n"
        "effect = Sampled\n"
    )
    result = cli(EXAMPLE, tmp_path / "dynamic.ass", "--effect", script)
    assert result.returncode == 0, result.stderr
    assert (
        result.stdout.index("Preflight:")
        < result.stdout.index("PROPERTY_STARTED")
        < result.stdout.index("Generated")
    )


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
    assert not any(line.text.endswith("\u00a0") for line in generated)


def test_cli_declarative_layered_glow_and_owner_repeat(tmp_path):
    root = EXAMPLE.parents[1]
    script = root / "examples/layered_glow.py"
    source = root / "tests/fixtures/layered_glow.ass"
    first, second = tmp_path / "first.ass", tmp_path / "second.ass"
    run = cli(source, first, "--effect", script)
    assert run.returncode == 0, run.stderr
    assert "Generated 389 events" in run.stdout
    again = cli(first, second, "--effect", script)
    assert again.returncode == 0, again.stderr
    assert first.read_bytes() == second.read_bytes()
