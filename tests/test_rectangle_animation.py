
import pytest

from kara_templater import (
    Document,
    Lifetime,
    PathObject,
    RectangleClip,
    RectangleFunction,
    Scene,
    Vec2,
    VectorPath,
    VisualState,
)


def shape(clip):
    return PathObject(
        id="box",
        lifetime=Lifetime(1, 3),
        path=VectorPath.rectangle(100, 50),
        state=VisualState(position=Vec2(30, 30)),
        clip=clip,
    )


def test_rectangle_callback_validation_and_preflight():
    calls = []

    def sample(time):
        calls.append(time)
        return (0, 0, 10, 10)

    node = shape(RectangleClip(0, 0, 1, 1, deform=RectangleFunction(sample)))
    with pytest.raises(ValueError, match="frame sampling"):
        Scene(Document.create()).add(node).compile()
    assert not calls
    with pytest.raises(ValueError, match="breakpoint"):
        shape(RectangleClip(0, 0, 1, 1, deform=RectangleFunction(sample, (3,))))
