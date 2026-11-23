"""E05 moving fragments vs dense native contours and independent polygon cuts.

uv run python -m tools.validate_fragments OUTPUT
"""

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import quote

from PIL import Image, ImageChops

from examples.scene_fragments import build
from kara_templater import Document, Line, Style, _ass_preview, _metrics, load_font
from tools.validate_case_geometry import compare
from tools.validate_engine_backgrounds import ROOT, SIZE

Point = tuple[float, float]


def contours() -> tuple[tuple[Point, ...], ...]:
    _, _, _, baseline, glyphs = _metrics.text_shape(
        "DejaVu Sans", 150, 0, 0, 100, 100, 0, 1, "KARA"
    )
    result = []
    for points, orders, _, _ in glyphs:
        cursor = first = 0
        polygon: list[Point] = []
        for code in orders:
            degree, close = code & 3, bool(code & 4)
            assert degree in (1, 2), "fixed font must use lines and quadratics"
            a = points[cursor]
            b = points[first if close else cursor + degree]
            for step in range(1 if degree == 1 else 64):
                t = step / (1 if degree == 1 else 64)
                if degree == 1:
                    x, y = a
                else:
                    c = points[cursor + 1]
                    x, y = (
                        (1 - t) ** 2 * a[axis]
                        + 2 * (1 - t) * t * c[axis]
                        + t**2 * b[axis]
                        for axis in (0, 1)
                    )
                polygon.append((x, y + baseline))
            cursor += degree
            if close:
                result.append(tuple(polygon))
                polygon = []
                first = cursor
        assert cursor == len(points) and not polygon
    return tuple(result)


def cut(
    polygon: tuple[Point, ...], box: tuple[float, float, float, float]
) -> tuple[Point, ...]:
    for axis, edge, direction in (
        (0, box[0], 1),
        (0, box[2], -1),
        (1, box[1], 1),
        (1, box[3], -1),
    ):
        output: list[Point] = []
        if not polygon:
            break
        previous = polygon[-1]
        for current in polygon:
            inside = (current[axis] - edge) * direction >= 0
            was_inside = (previous[axis] - edge) * direction >= 0
            if inside != was_inside:
                t = (edge - previous[axis]) / (current[axis] - previous[axis])
                output.append(
                    (
                        previous[0] + t * (current[0] - previous[0]),
                        previous[1] + t * (current[1] - previous[1]),
                    )
                )
            if inside:
                output.append(current)
            previous = current
        polygon = tuple(output)
    return polygon


def offset(identifier: str, axis: str, extent: float) -> float:
    payload = b"".join(
        len(p.encode()).to_bytes(8, "big") + p.encode()
        for p in ("37", identifier, axis)
    )
    fraction = (
        int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") >> 11
    ) / 2**53
    return (2 * fraction - 1) * extent


def clock(index: int) -> tuple[int, ...]:
    birth = index * 0.025
    # Independent construction of the declared 50Hz local grid and fade endpoint.
    values = [birth, birth + 0.2, 1.6]
    values.extend(birth + step / 50 for step in range(1, 81) if birth + step / 50 < 1.6)
    return tuple(sorted({round(round(value * 100, 8)) * 10 for value in values}))


def reference(
    index: int, ms: int, shapes: tuple[tuple[Point, ...], ...], *, drift: float = 0
) -> str:
    document = Document.create(styles=(Style(align=7, outline=0, shadow=0),))
    points = [p for contour in shapes for p in contour]
    left, right = min(p[0] for p in points), max(p[0] for p in points)
    top, bottom = min(p[1] for p in points), max(p[1] for p in points)
    row, col = divmod(index, 4)
    box = (
        left + (right - left) * col / 4,
        top + (bottom - top) * row / 3,
        left + (right - left) * (col + 1) / 4,
        top + (bottom - top) * (row + 1) / 3,
    )
    boundaries = clock(index)
    interval = next(
        (
            (a, b)
            for a, b in zip(boundaries, boundaries[1:], strict=False)
            if a <= ms < b
        ),
        None,
    )
    if interval is None:
        return document.dumps()
    time = sum(interval) / 2000
    birth = index * 0.025
    p = max(0, min(1, (time - birth) / (1.6 - birth)))
    ease = p * p * (3 - 2 * p)
    identifier = f"word/cell:{row}:{col}"
    x = 640 - (left + right) / 2 + offset(identifier, "x", 240) * (1 - ease) + drift
    y = 360 - (top + bottom) / 2 + offset(identifier, "y", 180) * (1 - ease)
    alpha = round((1 - max(0, min(1, (time - birth) / 0.2))) * 255)
    commands = []
    for contour in shapes:
        polygon = cut(contour, box)
        if len(polygon) >= 3:
            commands.append(
                "m "
                + " l ".join(f"{(u + x) * 8:.6f} {(v + y) * 8:.6f}" for u, v in polygon)
                + " c"
            )
    document.records.append(
        Line(
            start_time=0,
            end_time=5000,
            text=rf"{{\an7\pos(0,0)\p4\bord0\1c&HFFFF00&\alpha&H{alpha:02X}&}}"
            + " ".join(commands),
        )
    )
    return document.dumps()


def coverage(script: str, ms: int) -> tuple[Image.Image, set[int]]:
    result = Image.new("L", SIZE)
    alphas: set[int] = set()
    for x, y, width, height, kind, color, data in _ass_preview.rasterize(
        script, ms, *SIZE, 4_000_000, 10000
    ):
        if kind != 0 or not width or not height:
            continue
        tile = Image.new("L", SIZE)
        tile.paste(Image.frombytes("L", (width, height), data), (x, y))
        result = ImageChops.lighter(result, tile)
        alphas.add(color & 255)
    return result, alphas


def validate(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    face = load_font(ROOT / "tests/fonts/DejaVuSans.ttf")
    scene = build()
    compiled = scene.compile()
    (output / "scene.ass").write_text(compiled.document.dumps())
    shapes = contours()
    checks = []
    for index, node in enumerate(scene.objects[:-1]):
        isolated = Document.parse(compiled.document.dumps())
        isolated.records[:] = [
            record
            for record in isolated.records
            if not isinstance(record, Line)
            or record.effect == f"kara:scene:v1:scene:{quote(node.id, safe='')}"
        ]
        # Assert the owner selection so an empty oracle cannot silently pass.
        assert isolated.lines, f"missing owner {node.id}"
        script = isolated.dumps()
        (output / f"piece-{index}.ass").write_text(script)
        for ms in sorted({*clock(index), *(t + 1 for t in clock(index)), 1599, 1600}):
            actual, alpha = coverage(script, ms)
            expected_script = reference(index, ms, shapes)
            expected, reference_alpha = coverage(expected_script, ms)
            assert alpha == reference_alpha, (index, ms, alpha, reference_alpha)
            if expected.getbbox() is None:
                assert actual.getbbox() is None
                quality = None
            else:
                quality = compare(actual, expected)
            checks.append(
                {
                    "piece": index,
                    "time_ms": ms,
                    "alpha": sorted(alpha),
                    "geometry": quality,
                }
            )
        actual, _ = coverage(script, 800)
        shifted, _ = coverage(reference(index, 800, shapes, drift=5), 800)
        try:
            compare(actual, shifted)
        except AssertionError:
            pass
        else:
            raise AssertionError(f"piece {index} drift undetected")
        print(f"piece {index}: passed", flush=True)
    report = {
        "scope": "E05 isolated moving fragments; independent dense quadratic contours, polygon rectangle clipping, keyed random and scalar smoothstep/fade; unweighted silhouette and exact alpha",
        "font_sha256": face.sha256,
        "ass_sha256": hashlib.sha256(compiled.document.dumps().encode()).hexdigest(),
        "max_time_quantization_seconds": compiled.max_time_quantization,
        "checks": checks,
        "five_pixel_drift_detected_each_piece": True,
        "remaining": [
            "overlap composite",
            "continuous ideal time error",
            "other renderers",
        ],
    }
    (output / "fragments-validation.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    validate(parser.parse_args().output)


if __name__ == "__main__":
    main()
