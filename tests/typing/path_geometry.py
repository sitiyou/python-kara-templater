"""Advanced geometry stays typed at author callbacks and conversion boundaries."""

from typing import assert_type

from kara_templater import (
    GeometryAnimation,
    MorphPath,
    ObjectGroup,
    PathBooleanOperation,
    PathFunction,
    PathObject,
    Polyline,
    TextObject,
    TextOutline,
    Vec2,
    VectorPath,
    flatten,
    merge_geometry,
    outline_text,
    path_boolean,
    text_to_path,
)


def custom(path: VectorPath, time: float) -> VectorPath | None:
    return None if time < 0 else path.map(lambda point: point + Vec2(time, 0))


def author(text: TextObject) -> PathObject:
    data = outline_text(text)
    assert_type(data, TextOutline)
    assert_type(data.path, VectorPath | None)
    node = text_to_path(text)
    assert_type(node.path_at(1), VectorPath | None)
    assert_type(flatten(node.path.contours[0]), Polyline)
    deformation: GeometryAnimation = MorphPath(node.path)
    assert_type(deformation.sample(node.path, 1), VectorPath)
    callback: GeometryAnimation = PathFunction(custom, max_points=4096)
    assert_type(callback.sample(node.path, 1), VectorPath | None)
    return node


def boolean_contract(
    first: VectorPath, second: VectorPath, operation: PathBooleanOperation
) -> VectorPath | None:
    result = path_boolean(first, second, operation, max_points=512, max_work=100_000)
    assert_type(result, VectorPath | None)
    return result


def merged_contract(group: ObjectGroup) -> PathObject:
    result = merge_geometry(group, tolerance=0.25, max_points=1024)
    assert_type(result, PathObject)
    return result
