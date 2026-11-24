"""Invalid author declarations must produce a specific typing diagnostic."""

from kara_templater import Document, LyricHighlights, StatePatch, prepare_tracks


def rejected(document: Document) -> None:
    StatePatch(fill=123)  # ty: ignore[invalid-argument-type]
    StatePatch(opacity="opaque")  # ty: ignore[invalid-argument-type]
    StatePatch(typo=1)  # ty: ignore[unknown-argument]
    LyricHighlights.from_singing(StatePatch(), curve=lambda p: p)  # ty: ignore[unknown-argument]
    prepare_tracks(document, tracks=("invalid",))  # ty: ignore[invalid-argument-type]
