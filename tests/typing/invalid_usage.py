"""Invalid author declarations must produce a specific typing diagnostic."""

from kara_templater import (
    Body,
    Document,
    HighlightAnimation,
    Overlay,
    Ruby,
    StyleSheet,
    Sweep,
    prepare_tracks,
    rule,
)


def rejected(body: Body, document: Document) -> None:
    body.style.fill = 123  # ty: ignore[invalid-assignment]
    body.style.opacity = "opaque"  # ty: ignore[invalid-assignment]
    body.style.typo = 1  # ty: ignore[missing-attribute]
    Body(font_size="large")  # ty: ignore[invalid-argument-type]
    Ruby(follow="everything")  # ty: ignore[invalid-argument-type]
    StyleSheet(rule("body", fill=123))  # ty: ignore[invalid-argument-type]
    HighlightAnimation(offset_y=lambda p: "large")  # ty: ignore[invalid-argument-type]
    HighlightAnimation(offest_y=1.0)  # ty: ignore[unknown-argument]
    Overlay(overlap="unknown")  # ty: ignore[invalid-argument-type]
    Sweep(curve=lambda p: p)  # ty: ignore[unknown-argument]
    prepare_tracks(document, tracks=(), mode="unknown")  # ty: ignore[invalid-argument-type]
