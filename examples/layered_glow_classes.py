"""The layered_glow builder using an ordinary typed Track subclass.

Load with CLI --effect examples/layered_glow_classes.py.
"""

from examples.layered_glow import Paint, configuration
from kara_templater import Document, LyricScene, Style, Track, prepare_tracks


class LayeredGlow(Track):
    def __init__(self, style: Style, *, paint: Paint | None = None) -> None:
        config = configuration(style, paint=paint)
        super().__init__(
            id=config.id,
            source=config.source,
            layout=config.layout,
            preview=config.preview,
            tail=config.tail,
            tags=config.tags,
            styles=config.styles,
            factory=config.factory,
            animations=config.animations,
        )


def build(document: Document) -> LyricScene:
    return prepare_tracks(
        document,
        tracks=tuple(
            LayeredGlow(document.styles[name]) for name in ("K1", "K2", "LEAD")
        ),
        owner="layered-glow",
    )
