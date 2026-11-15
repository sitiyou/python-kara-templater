"""Inventory bundled engine assets; verify subset coverage and sdist inclusion.

uv run python -m tools.validate_engine_assets docs/engine-assets-validation.json
This checks repository assets, not which font a playback application selects.
"""

import argparse
import hashlib
import json
from pathlib import Path

from fontTools.ttLib import TTFont

from examples.scene_whole_song import CASES

ROOT = Path(__file__).resolve().parents[1]
SUBSETS = {
    "KaraTestPrimary.ttf": " A",
    "KaraTestCJK.ttf": "時々",
    "KaraTestHangul.ttf": "한글가각 한글가각",
    "KaraTestMultiscript.ttf": "今天かな한글",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(output: Path) -> None:
    manifest = (ROOT / "MANIFEST.in").read_text()
    assets: list[dict[str, object]] = []
    for path in sorted((ROOT / "tests/fonts").glob("*.ttf")):
        license_path = path.with_name(
            "LICENSE-Sarasa"
            if path.name in SUBSETS and path.name != "KaraTestPrimary.ttf"
            else "LICENSE"
        )
        for required in (path, license_path):
            if required.relative_to(ROOT).as_posix() not in manifest.split():
                raise AssertionError(
                    f"asset lacks explicit sdist inclusion: {required.name}"
                )
        with TTFont(path) as font:
            coverage = font.getBestCmap()
            if not coverage:
                raise AssertionError(f"font has no Unicode cmap: {path.name}")
            if path.name in SUBSETS and set(coverage) != set(
                map(ord, SUBSETS[path.name])
            ):
                raise AssertionError(f"unexpected subset coverage: {path.name}")
            assets.append(
                {
                    "path": path.relative_to(ROOT).as_posix(),
                    "sha256": digest(path),
                    "bytes": path.stat().st_size,
                    "family": font["name"].getDebugName(1),
                    "style": font["name"].getDebugName(2),
                    "copyright": font["name"].getDebugName(0),
                    "codepoint_count": len(coverage),
                    "subset_codepoints": [
                        f"U+{point:04X}" for point in sorted(coverage)
                    ]
                    if path.name in SUBSETS
                    else None,
                    "license_path": license_path.relative_to(ROOT).as_posix(),
                    "license_sha256": digest(license_path),
                }
            )
    if len(assets) != 6:
        raise AssertionError("review inventory when bundled fonts are added or removed")
    cases: list[dict[str, str]] = []
    for case in CASES:
        path = ROOT / (case.factory.__module__.replace(".", "/") + ".py")
        cases.append(
            {
                "id": case.id,
                "name": case.name,
                "source": path.relative_to(ROOT).as_posix(),
                "sha256": digest(path),
            }
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "scope": "Bundled font bytes, licenses, cmap subsets and authored E01-E12 source snapshot; no playback or visual acceptance claim",
                "project_license": {
                    "path": "LICENSE",
                    "sha256": digest(ROOT / "LICENSE"),
                },
                "fonts": assets,
                "cases": cases,
                "regeneration": [
                    "tools/build_test_font.py",
                    "tools/build_hangul_test_font.py",
                ],
                "baseline_reports": [
                    "docs/engine-backgrounds-validation.json",
                    "docs/engine-backgrounds-writing-validation.json",
                    "docs/engine-backgrounds-writing-final-validation.json",
                    "docs/engine-backgrounds-sakura-validation.json",
                    "docs/engine-backgrounds-sakura-final-validation.json",
                    "docs/engine-backgrounds-cues-validation.json",
                    "docs/engine-backgrounds-words-validation.json",
                    "docs/engine-backgrounds-staggered-validation.json",
                    "docs/engine-backgrounds-lyrics-validation.json",
                    "docs/engine-backgrounds-fragments-validation.json",
                    "docs/engine-backgrounds-round-validation.json",
                    "docs/engine-backgrounds-outlines-validation.json",
                    "docs/engine-backgrounds-morph-validation.json",
                    "docs/engine-backgrounds-gradient-validation.json",
                    "docs/engine-backgrounds-sweep-validation.json",
                    "docs/whole-song-validation.json",
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    print(f"Verified {len(assets)} fonts and {len(cases)} case source files")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    validate(parser.parse_args().output)


if __name__ == "__main__":
    main()
