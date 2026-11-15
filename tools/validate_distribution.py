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
        f"kara_templater/{path.name}"
        for path in (package / "kara_templater").iterdir()
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
    if not any(
        name.startswith("kara_templater/_metrics.") and name.endswith((".so", ".pyd"))
        for name in files
    ):
        raise AssertionError("wheel is missing the native metrics extension")
    for relative in (
        "vendor/006-libass-coverage-blur.patch",
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
    for name in ("tests", "examples", "tools", "docs"):
        shutil.copytree(package / name, check / name)
    for name in ("README.md", "THIRD_PARTY.md", "setup.py", "pyproject.toml"):
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
            "import json,sys,kara_templater; from kara_templater import _metrics; print(json.dumps({'python':sys.version,'package':kara_templater.__file__,'native':_metrics.__file__}))",
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
    examples = []
    for path in sorted((check / "examples").glob("scene_*.py")):
        target = artifacts / f"{path.stem}.ass"
        duration = run(
            [str(python), "-m", f"examples.{path.stem}", str(target)], path.stem, check
        )
        examples.append(
            {
                "module": f"examples.{path.stem}",
                "seconds": duration,
                "bytes": target.stat().st_size,
                "sha256": sha256(target),
            }
        )
    run(
        [
            str(python),
            "-m",
            "kara_templater",
            "examples/karaoke.ass",
            "output/default.ass",
        ],
        "default-cli",
        check,
    )
    run(
        [
            str(python),
            "-m",
            "kara_templater",
            "tests/fixtures/v010-karaoke.ass",
            "output/templates.ass",
            "--templates",
        ],
        "template-cli",
        check,
    )
    strategy_examples = []
    for strategy in ("layers", "raster", "diffused"):
        target = artifacts / f"sweep-{strategy}.ass"
        duration = run(
            [
                str(python),
                "-m",
                "examples.scene_sweep_strategies",
                str(target),
                "--strategy",
                strategy,
            ],
            f"sweep-{strategy}",
            check,
        )
        strategy_examples.append(
            {
                "strategy": strategy,
                "seconds": duration,
                "bytes": target.stat().st_size,
                "sha256": sha256(target),
            }
        )
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
        "default_cli_passed": True,
        "explicit_v010_template_cli_passed": True,
        "sweep_strategy_examples": strategy_examples,
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
