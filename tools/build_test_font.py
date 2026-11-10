"""Rebuild the renamed A/space fixture; requires fontTools only for regeneration."""

from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont


def main():
    directory = Path(__file__).resolve().parents[1] / "tests/fonts"
    font = TTFont(directory / "DejaVuSans.ttf", recalcTimestamp=False)
    options = subset.Options()
    options.name_IDs = [0, 1, 2, 3, 4, 5, 6, 13, 14, 16, 17]
    options.recalc_timestamp = False
    subsetter = subset.Subsetter(options=options)
    subsetter.populate(text="A ")
    subsetter.subset(font)
    names = {
        1: "Kara Test Primary",
        2: "Regular",
        3: "KaraTestPrimary-Regular",
        4: "Kara Test Primary Regular",
        6: "KaraTestPrimary-Regular",
        16: "Kara Test Primary",
        17: "Regular",
    }
    for record in font["name"].names:
        if record.nameID in names:
            record.string = names[record.nameID].encode(record.getEncoding())
    font.save(directory / "KaraTestPrimary.ttf")


if __name__ == "__main__":
    main()
