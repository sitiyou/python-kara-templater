from dataclasses import replace

import pytest

from kara_templater import (
    DisplayWindow,
    KaraokeItem,
    KaraokeLine,
    Segment,
    SourceRef,
    TextUnit,
    walk_karaoke,
)


def items():
    # Deliberately not chronological: traversal follows text structure.
    source = KaraokeLine(
        (
            TextUnit("["),
            TextUnit("", (Segment(500, 500),)),
            TextUnit("AB", (Segment(100, 200, "a"), Segment(300, 400, "b"))),
        )
    )
    first = KaraokeItem("line:/一", source, "Default", DisplayWindow(0, 1000))
    return first, replace(first, id="echo")


def test_all_levels_resolve_original_sources_without_filtering_or_retiming():
    first, second = items()
    for level, count in (("line", 2), ("unit", 6), ("segment", 6)):
        visits = list(walk_karaoke(iter((first, second)), level=level))
        assert len(visits) == count
        assert len({ref for ref, _ in visits}) == count
        for ref, source in visits:
            item = first if ref.item_id == first.id else second
            assert ref.resolve(item) is source
    visits = list(walk_karaoke((first,)))
    assert [ref for ref, _ in visits] == [
        SourceRef(first.id, 1, 0),
        SourceRef(first.id, 2, 0),
        SourceRef(first.id, 2, 1),
    ]
    assert [segment.start_ms for _, segment in visits] == [500, 100, 300]


def test_references_survive_item_reordering_and_presentation_changes():
    first, second = items()
    original = dict(walk_karaoke((first, second)))
    changed = replace(first, style="Other", window=DisplayWindow(0, 2000))
    assert dict(walk_karaoke((second, changed))) == original
    for ref, _source in walk_karaoke((changed,)):
        assert ref.resolve(changed) is original[ref]
    with pytest.raises(ValueError, match="belongs to"):
        SourceRef(first.id).resolve(second)
    with pytest.raises(ValueError, match="outside item structure"):
        SourceRef(first.id, 2, 9).resolve(first)


@pytest.mark.parametrize(
    "args", [("",), ("x", -1), ("x", True), ("x", None, 0), ("x", 0, 1.5)]
)
def test_invalid_reference(args):
    with pytest.raises(ValueError):
        SourceRef(*args)


def test_ambiguous_ids_and_unknown_levels_fail_before_visiting():
    first, _ = items()
    with pytest.raises(ValueError, match="duplicate"):
        next(walk_karaoke((first, first)))
    with pytest.raises(ValueError, match="level"):
        # Unsupported traversal levels must also fail at runtime.
        list(walk_karaoke((), level="character"))  # ty: ignore[no-matching-overload]
    assert list(walk_karaoke(())) == []
