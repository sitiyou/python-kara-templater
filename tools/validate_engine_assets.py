"""Inventory bundled engine assets; verify subset coverage and sdist inclusion.

uv run python -m tools.validate_engine_assets build/engine-assets-validation.json
This checks repository assets, not which font a playback application selects.
"""

import argparse
import hashlib
import json
from pathlib import Path

from fontTools.ttLib import TTFont

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
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "scope": "Bundled font bytes, licenses, cmap subsets; no playback or visual acceptance claim",
                "project_license": {
                    "path": "LICENSE",
                    "sha256": digest(ROOT / "LICENSE"),
                },
                "fonts": assets,
                "regeneration": [
                    "tools/build_test_font.py",
                    "tools/build_hangul_test_font.py",
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    print(f"Verified {len(assets)} fonts")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    validate(parser.parse_args().output)


if __name__ == "__main__":
    main()
