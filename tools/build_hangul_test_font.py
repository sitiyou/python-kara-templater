"""Regenerate renamed Hangul and CJK fixtures from Sarasa-Regular.ttc and its license.

Usage: python -m tools.build_hangul_test_font FONT_TTC LICENSE
Requires fontTools only for regeneration.
"""

import argparse
import shutil
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("license", type=Path)
    args = parser.parse_args()
    build_fixture(
        args.source,
        args.license,
        "한글가각 한글가각",
        "Kara Test Hangul",
        "KaraTestHangul",
    )
    build_fixture(args.source, args.license, "時々", "Kara Test CJK", "KaraTestCJK")


def build_fixture(source, license_path, text, family, identifier):
    font = TTFont(source, fontNumber=7, recalcTimestamp=False)
    assert font["name"].getDebugName(1) == "Sarasa UI SC"
    options = subset.Options()
    options.name_IDs = [0, 1, 2, 3, 4, 5, 6, 13, 14, 16, 17]
    options.recalc_timestamp = False
    worker = subset.Subsetter(options=options)
    worker.populate(text=text)
    worker.subset(font)
    names = {
        1: family,
        2: "Regular",
        3: identifier + "-Regular",
        4: family + " Regular",
        6: identifier + "-Regular",
        16: family,
        17: "Regular",
    }
    for record in font["name"].names:
        if record.nameID in names:
            record.string = names[record.nameID].encode(record.getEncoding())
    directory = Path(__file__).resolve().parents[1] / "tests/fonts"
    font.save(directory / (identifier + ".ttf"))
    shutil.copyfile(license_path, directory / "LICENSE-Sarasa")


if __name__ == "__main__":
    main()
