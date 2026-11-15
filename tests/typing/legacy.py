from typing import assert_type

from kara_templater import (
    Document,
    Engine,
    LegacyLine,
    LegacySyllable,
    Scene,
    apply_templates,
    preprocess,
    split_karaoke,
)


def legacy(document: Document) -> Scene:
    assert_type(apply_templates(document), Document)
    assert_type(Engine().to_scene(document), Scene)
    assert_type(
        split_karaoke("text"), tuple[list[LegacySyllable], list[LegacySyllable]]
    )
    assert_type(
        preprocess(document.lines[0], document.styles, document.meta), LegacyLine
    )
    return Engine().to_scene(document)
