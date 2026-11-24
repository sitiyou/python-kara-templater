"""Check an installed wheel against the fixtures shipped in its source archive.

uv run python -m tools.validate_distribution SDIST WHEEL OUTPUT --python python3.12
No library source directory is copied into the isolated test working directory.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import tomllib
import zipfile
from pathlib import Path
from time import perf_counter


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_without_dll_bootstrap(name: str, content: bytes, windows: bool) -> bytes:
    """Remove only the recognized delvewheel add_dll_directory bootstrap.

    Keep the exact body check: accepting arbitrary text between repair markers
    would hide unintended changes to the installed package.
    """
    if not windows or name != "kara_templater/__init__.py":
        return content
    prefix = re.match(
        rb'"""""" # start delvewheel patch\n'
        rb"def _delvewheel_patch_(\d+_\d+_\d+)\(\):\n",
        content,
    )
    if prefix is None:
        return content
    version = prefix[1]
    expected = (
        prefix[0]
        + b"    import os\n"
        + b"    if os.path.isdir(libs_dir := os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, 'kara_templater.libs'))):\n"
        + b"        os.add_dll_directory(libs_dir)\n\n\n"
        + b"_delvewheel_patch_"
        + version
        + b"()\n"
        + b"del _delvewheel_patch_"
        + version
        + b"\n"
        + b"# end delvewheel patch\n\n"
    )
    return content.removeprefix(expected)


def validate(archive: Path, wheel: Path, output: Path, interpreter: str) -> None:
    archive, wheel, output = archive.resolve(), wheel.resolve(), output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV")
    }
    logs = output / "logs"
    logs.mkdir()

    def run(arguments: list[str], name: str, cwd: Path) -> float:
        started = perf_counter()
        with (logs / f"{name}.log").open("w") as stream:
            subprocess.run(
                arguments,
                cwd=cwd,
                env=environment,
                stdout=stream,
                stderr=subprocess.STDOUT,
                check=True,
            )
        return perf_counter() - started

    with tarfile.open(archive) as source:
        source.extractall(output / "source", filter="data")
    (package,) = (output / "source").iterdir()
    with zipfile.ZipFile(wheel) as source:
        files = set(source.namelist())
        metadata_name = next(
            name for name in files if name.endswith(".dist-info/WHEEL")
        )
        wheel_tags = [
            line.removeprefix("Tag: ")
            for line in source.read(metadata_name).decode().splitlines()
            if line.startswith("Tag: ")
        ]
        if any(
            "manylinux" in tag and tag.rsplit("-", 1)[-1] != "manylinux_2_28_x86_64"
            for tag in wheel_tags
        ):
            raise AssertionError(
                "Linux release wheel must advertise only the configured manylinux_2_28 floor"
            )
    expected = {
        path.relative_to(package).as_posix()
        for path in (package / "kara_templater").rglob("*")
        if path.suffix in (".py", ".pyi") or path.name == "py.typed"
    }
    if missing := expected - files:
        raise AssertionError(f"wheel is missing modules/type data: {sorted(missing)}")
    with zipfile.ZipFile(wheel) as built:
        windows = all(tag.endswith("-win_amd64") for tag in wheel_tags)
        bootstrap_removed = built.read(
            "kara_templater/__init__.py"
        ) != source_without_dll_bootstrap(
            "kara_templater/__init__.py",
            built.read("kara_templater/__init__.py"),
            windows,
        )
        mismatched = [
            name
            for name in sorted(expected)
            if source_without_dll_bootstrap(name, built.read(name), windows)
            != (package / name).read_bytes()
        ]
    if mismatched:
        raise AssertionError(f"wheel modules differ from source archive: {mismatched}")
    extensions = [name for name in files if name.startswith("kara_templater/")
                  and name.endswith((".so", ".pyd"))]
    if len(extensions) != 1 or not extensions[0].startswith("kara_templater/_text_native."):
        raise AssertionError(f"unexpected wheel extensions: {extensions}")
    for relative in (
        "native/metrics.cpp",
        "tests/fonts/KaraTestCJK.ttf",
        "tests/fonts/KaraTestMultiscript.ttf",
        "docs/getting-started.md",
        "docs/reference/README.md",
    ):
        if not (package / relative).is_file():
            raise AssertionError(f"source archive is missing {relative}")
    check = output / "check"
    check.mkdir()
    for name in ("tests", "examples", "tools", "docs", "skills"):
        shutil.copytree(package / name, check / name)
    for name in ("README.md", "LICENSE", "THIRD_PARTY.md", "setup.py", "pyproject.toml"):
        shutil.copy2(package / name, check / name)
    venv = output / "venv"
    run(["uv", "venv", "--python", interpreter, str(venv)], "venv", check)
    python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    pins = tomllib.loads((package / "pyproject.toml").read_text())["dependency-groups"][
        "checks"
    ]
    checker = next(pin for pin in pins if pin.startswith("ty=="))
    run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            str(python),
            str(wheel),
            "pytest>=8",
            "setuptools>=77",
            "Pillow>=10",
            next(pin for pin in pins if pin.lower().startswith("fonttools")),
            checker,
        ],
        "install",
        check,
    )
    environment["VIRTUAL_ENV"] = str(venv)
    environment["PATH"] = str(python.parent) + os.pathsep + environment.get("PATH", "")
    probe = subprocess.check_output(
        [
            str(python),
            "-I",
            "-c",
            "import json,sys,kara_templater; from kara_templater import _text_native; print(json.dumps({'python':sys.version,'package':kara_templater.__file__,'native':_text_native.__file__}))",
        ],
        cwd=check,
        env=environment,
        text=True,
    )
    installed = json.loads(probe)
    if not Path(installed["package"]).is_relative_to(venv):
        raise AssertionError(
            "test import did not come from the isolated wheel installation"
        )
    seconds = run([str(python), "-m", "pytest", "tests", "-q"], "pytest", check)
    print("isolated installed-wheel tests passed", flush=True)
    run(
        [
            str(python.parent / ("ty.exe" if os.name == "nt" else "ty")),
            "check",
            "tests/typing",
        ],
        "public-typing",
        check,
    )
    run([str(python), "-m", "tools.check_scene_types"], "negative-typing", check)
    artifacts = check / "output"
    artifacts.mkdir()
    def export(arguments: list[str], target: Path, name: str) -> dict[str, str | int | float]:
        elapsed = run([str(python), "-m", *arguments], name, check)
        content = target.read_bytes()
        if target.suffix == ".hook":
            if b"//!HOOK MAIN" not in content:
                raise AssertionError(f"{target.name} is missing its Hook program")
        elif not content.decode("utf-8-sig").startswith("[Script Info]"):
            raise AssertionError(f"{target.name} is not an ASS document")
        return {
            "name": name,
            "format": target.suffix[1:],
            "seconds": elapsed,
            "bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }

    examples = []
    author_examples = []
    for suite, name, suffix in (
        (examples, "scene_cues", ".ass"),
        (examples, "scene_native_tween", ".ass"),
        (author_examples, "lyric_pulse_drift", ".hook"),
        (author_examples, "karaoke_catalog", ".hook"),
        (author_examples, "slit_reveal", ".hook"),
        (author_examples, "lyric_no_sweep", ".hook"),
    ):
        target = artifacts / f"{name}{suffix}"
        suite.append(export([f"examples.{name}", str(target)], target, name))

    (check / "tracks_recipe.py").write_text(
        "from kara_templater import Track, LyricRule, FadeIn\n"
        "tracks = (Track(id='lyrics', effects=(LyricRule('line', 'enter', FadeIn(), duration=0.1),)),)\n",
        encoding="utf-8",
    )
    cli_outputs = []
    for name, suffix, flags in (
        ("default-cli", ".hook", ()),
        ("preset-ass-cli", ".ass", ("--ass",)),
        ("builder-cli", ".hook", ("--effect", "examples/gpu_gradient.py")),
        ("tracks-cli", ".ass", ("--ass", "--effect", "tracks_recipe.py")),
    ):
        target = artifacts / f"{name}{suffix}"
        cli_outputs.append(export(
            ["kara_templater", "examples/karaoke.ass", str(target), *flags], target, name
        ))
    report = {
        "scope": "local platform wheel rebuilt from source archive, isolated import, full shipped tests and fixed scene examples; repaired cross-platform release wheels are separate",
        "archive": {
            "name": archive.name,
            "bytes": archive.stat().st_size,
            "sha256": sha256(archive),
        },
        "wheel": {
            "name": wheel.name,
            "bytes": wheel.stat().st_size,
            "sha256": sha256(wheel),
            "tags": wheel_tags,
        },
        "installed": installed,
        "python_modules_and_typing_files": len(expected),
        "wheel_python_sources_match_archive": True,
        "recognized_delvewheel_bootstrap_removed_for_comparison": bootstrap_removed,
        "public_typing_passed": True,
        "negative_typing_summary": (logs / "negative-typing.log").read_text().strip(),
        "pytest_seconds": seconds,
        "pytest_summary": (logs / "pytest.log").read_text().splitlines()[-1],
        "scene_examples": examples,
        "karaoke_author_examples": author_examples,
        "cli_outputs": cli_outputs,
        "builder_and_tracks_cli_passed": True,
        "default_cli_passed": True,
    }
    (output / "distribution-validation.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(f"{len(examples)} installed-wheel scene examples exported", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("wheel", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--python", default="python3.12")
    args = parser.parse_args()
    validate(args.archive, args.wheel, args.output, args.python)


if __name__ == "__main__":
    main()
