"""Expected diagnostics: stale ignores fail the strict typing regression check."""

from kara_templater import Body, Effect, Halo, Lyrics, Ruby, StyleSheet, rule


def rejected(effect: Effect) -> None:
    effect.query_one("#light").on_singing(opacity=0.5)  # ty: ignore[missing-attribute]
    effect.query_one(Ruby).on_singing(opacity=0.5)  # ty: ignore[missing-attribute]
    effect.query_one("#light", Halo).hide()  # ty: ignore[missing-attribute]
    effect.query(Body)[0].missing()  # ty: ignore[missing-attribute]
    effect.query(123)  # ty: ignore[no-matching-overload]
    effect.body.style.fill = 123  # ty: ignore[invalid-assignment]
    effect.body.style.opacity = "opaque"  # ty: ignore[invalid-assignment]
    effect.body.style.typo = 1  # ty: ignore[missing-attribute]
    effect.syllables.style.sung.fill = 123  # ty: ignore[invalid-assignment]
    effect.characters.on_singing(scale="large")  # ty: ignore[invalid-argument-type]
    effect.characters.on_singing(sclae=1.2)  # ty: ignore[unknown-argument]
    effect.characters.on_singing(
        scale=lambda p: "large"  # ty: ignore[invalid-argument-type]
    )
    effect.characters.animate(
        during=("start", "end"), scale=1.2  # ty: ignore[invalid-argument-type]
    )
    effect.text.fade(in_ms="slow")  # ty: ignore[invalid-argument-type]
    effect.text.sweep(fill=42)  # ty: ignore[invalid-argument-type]
    effect.text.sweep(overlap="unknown")  # ty: ignore[invalid-argument-type]
    Body(font_size="large")  # ty: ignore[invalid-argument-type]
    Ruby(follow="everything")  # ty: ignore[invalid-argument-type]
    Halo(blur="fuzzy")  # ty: ignore[invalid-argument-type]
    Lyrics("text")  # ty: ignore[invalid-argument-type]
    StyleSheet(rule("body", fill=123))  # ty: ignore[invalid-argument-type]
