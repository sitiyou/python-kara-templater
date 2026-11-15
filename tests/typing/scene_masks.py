from typing import assert_type

from kara_templater import (
    ObjectGroup,
    PathFunction,
    PathObject,
    RectangleClip,
    VectorClip,
    VectorPath,
)


def mask(path: VectorPath, time: float) -> VectorPath | None:
    return path if time > 0.5 else None


local = RectangleClip(0, 0, 100, 100, space="local")
animated = VectorClip(VectorPath.circle(50), deform=PathFunction(mask, max_points=13))
assert_type(local, RectangleClip)
assert_type(animated, VectorClip)


def shared_mask(child: PathObject) -> ObjectGroup:
    return ObjectGroup(
        id="group",
        lifetime=child.lifetime,
        children=(child,),
        clip=RectangleClip(0, 0, 100, 100, space="local"),
    )


def rectangle_callback_contract() -> None:
    from kara_templater import RectangleClip, RectangleFunction

    clip = RectangleClip(
        0,
        0,
        1,
        1,
        deform=RectangleFunction(
            lambda time: (0, 0, 100 * time, 50) if time > 0 else None, (0.5,)
        ),
    )
    assert_type(clip.deform, RectangleFunction | None)
