"""E04 isolated curved petals vs scalar cubic/flutter formulas and handwritten ASS.

uv run python -m tools.validate_sakura_flutter OUTPUT
"""

import argparse
import hashlib
import json
from math import cos, radians, sin, tau
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

from examples.scene_sakura import build
from kara_templater import (
    Document,
    Line,
    PathObject,
    Scene,
    Style,
    _ass_preview,
    load_font,
)
from tools.validate_case_geometry import compare
from tools.validate_engine_backgrounds import ROOT
from tools.validate_sakura import centroid
from tools.validate_staggered import fill


def random_value(identity: str, key: str, low: float, high: float) -> float:
    payload = bytearray()
    for value in ("17", identity, key):
        encoded = value.encode()
        payload.extend(len(encoded).to_bytes(8, "big"))
        payload.extend(encoded)
    integer = int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") >> 11
    return low + (high - low) * integer / 2**53


def outline_envelope(script: str, time_ms: int) -> Image.Image:
    """Outer geometry, excluding opacity and the thin ring's interior hole."""
    mask = Image.new("L", (1280, 720))
    for left, top, width, height, kind, _, data in _ass_preview.rasterize(
        script, time_ms, 1280, 720, 4_000_000, 10_000
    ):
        if kind not in (0, 1) or not width or not height:
            continue
        tile = Image.new("L", mask.size)
        tile.paste(Image.frombytes("L", (width, height), data), (left, top))
        mask = ImageChops.lighter(mask, tile)
    return mask


def reference(
    identity: str,
    time_ms: int,
    birth_seconds: float,
    origin: tuple[float, float],
    *,
    rotate: bool = True,
    linear: bool = False,
) -> tuple[str, int]:
    # Quantize the birth-relative 20ms grid and the authored fade breakpoint
    # to ASS centiseconds; do not call the engine sampler.
    edges = sorted(
        {
            round((birth_seconds * 1000 + age) / 10) * 10
            for age in (*range(0, 3001, 20), 2250)
        }
    )
    first, last = next(
        (a, b) for a, b in zip(edges, edges[1:], strict=False) if a <= time_ms < b
    )
    p = ((first + last) / 2 - birth_seconds * 1000) / 3000
    q = p * p * (3 - 2 * p)
    wind = random_value(identity, "wind", -170, 170)
    x = (
        origin[0]
        + 3 * (1 - q) ** 2 * q * (wind + 140)
        + 3 * (1 - q) * q * q * (wind - 120)
        + q**3 * wind
    )
    y = origin[1] + 3 * (1 - q) ** 2 * q * 90 + 3 * (1 - q) * q * q * 250 + q**3 * 340
    size = random_value(identity, "size", 0.45, 0.9)
    phase = random_value(identity, "phase", 0, tau)
    angle = (
        radians(
            random_value(identity, "angle", 0, 360)
            + p * 180
            + sin(p * tau * 2 + phase) * 30
        )
        if rotate
        else 0
    )
    sx = size * (0.25 + 0.75 * abs(cos(p * tau * 2 + phase)))
    alpha = round((1 - min(1, (1 - p) / 0.25)) * 255)
    if linear:
        p = (time_ms - birth_seconds * 1000) / 3000
        x = origin[0] + random_value(identity, "wind", -100, 100) * p
        y = origin[1] + 900 * p
        angle = radians(random_value(identity, "angle", 0, 360))
        sx, alpha = size, 0
    commands = (
        ("m", ((0, -8),)),
        ("b", ((-6, -19), (-20, -7), (-3, 14))),
        ("b", ((-1, 18), (2, 17), (5, 12))),
        ("b", ((20, -7), (8, -19), (2, -12))),
        ("l", ((0, -8),)),
    )
    drawing = " ".join(
        command
        + " "
        + " ".join(
            f"{8 * (x + u * sx * cos(angle) - v * size * sin(angle)):.6f} {8 * (y + u * sx * sin(angle) + v * size * cos(angle)):.6f}"
            for u, v in points
        )
        for command, points in commands
    )
    doc = Document.create(styles=(Style(align=7, outline=0.5, shadow=0),))
    doc.records.append(
        Line(
            start_time=0,
            end_time=6000,
            text=rf"{{\an7\pos(0,0)\p4\1c&HCBC0FF&\3c&HFFFFFF&\alpha&H{alpha:02X}&}}"
            + drawing,
        )
    )
    return doc.dumps(), alpha


def validate(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    load_font(ROOT / "tests/fonts/DejaVuSans.ttf")
    scene = build()
    nodes = {node.id: node for node in scene.objects if isinstance(node, PathObject)}
    ages = (
        0,
        1,
        250,
        500,
        750,
        1000,
        1250,
        1500,
        1750,
        2000,
        2249,
        2250,
        2251,
        2500,
        2750,
        2900,
    )
    checks: list[dict[str, str | int | float]] = []
    outline_checks: list[dict[str, str | int | float]] = []
    sheet = Image.new("RGB", (900, 450), "#141824")
    previews = ("ambient/0", "ambient/17", "sung/0")
    identities = [f"ambient/{i}" for i in range(18)] + [f"sung/{i}" for i in range(12)]
    for identity in identities:
        node = nodes[identity]
        birth = round(node.lifetime.start * 100) * 10
        origin = (node.state.position.x, node.state.position.y)
        if identity.startswith("ambient/"):
            expected_x = 140 + random_value(identity, "spread", 0, 1000)
            if abs(origin[0] - expected_x) > 1e-7 or origin[1] != 90:
                raise AssertionError("ambient birth origin differs")
        script = Scene(Document.create()).add(node).compile().document.dumps()
        (output / (identity.replace("/", "-") + ".ass")).write_text(script)
        for age in ages:
            expected, alpha = reference(
                identity, birth + age, node.lifetime.start, origin
            )
            actual_mask = fill(script, birth + age, rgb=0xFFC0CB)
            expected_mask = fill(expected, 0, rgb=0xFFC0CB)
            metrics = compare(actual_mask, expected_mask)
            outline_metrics = compare(
                outline_envelope(script, birth + age),
                outline_envelope(expected, 0),
            )
            ring_difference = ImageChops.difference(
                fill(script, birth + age, rgb=0xFFFFFF, role=1),
                fill(expected, 0, rgb=0xFFFFFF, role=1),
            ).getextrema()[1]
            assert isinstance(ring_difference, int)
            outline_checks.append(
                {
                    "id": identity,
                    "age_ms": age,
                    "max_ring_coverage_difference": ring_difference,
                    **outline_metrics,
                }
            )
            actual_center = centroid(script, birth + age)
            if actual_center is None or abs(actual_center[2] - alpha) > 1:
                raise AssertionError(f"opacity mismatch {identity}/{age}")
            checks.append(
                {
                    "id": identity,
                    "age_ms": age,
                    "expected_alpha": alpha,
                    "actual_alpha": actual_center[2],
                    "alpha_error": abs(actual_center[2] - alpha),
                    **metrics,
                }
            )
            if age == 1250 and identity in previews:
                row = previews.index(identity)
                wrong, _ = reference(
                    identity, birth + age, node.lifetime.start, origin, rotate=False
                )
                try:
                    compare(actual_mask, fill(wrong, 0, rgb=0xFFC0CB))
                except AssertionError:
                    pass
                else:
                    raise AssertionError("missing rotation was not detected")
                thick = expected.replace("\\alpha", "\\bord8\\alpha")
                try:
                    compare(
                        outline_envelope(script, birth + age),
                        outline_envelope(thick, 0),
                    )
                except AssertionError:
                    pass
                else:
                    raise AssertionError("excess outline width was not detected")
                box = expected_mask.getbbox()
                assert box is not None
                crop = (box[0] - 8, box[1] - 8, box[2] + 8, box[3] + 8)
                for column, picture in enumerate(
                    (
                        actual_mask,
                        expected_mask,
                        ImageChops.difference(actual_mask, expected_mask),
                    )
                ):
                    sheet.paste(
                        picture.crop(crop).resize((120, 120)),
                        (column * 300, row * 150 + 25),
                    )
                    ImageDraw.Draw(sheet).text(
                        (column * 300, row * 150),
                        f"{identity} " + ("actual", "reference", "difference")[column],
                        fill="white",
                    )
        for time in (birth - 1, birth + 3000, birth + 3001):
            if time >= 0 and centroid(script, time) is not None:
                raise AssertionError(f"petal outside lifetime {identity}/{time}")
    straight_checks = []
    for index in range(6):
        identity = f"straight/{index}"
        node = nodes[identity]
        origin = (140 + random_value(identity, "spread", 0, 1000), -30.0)
        assert (
            abs(node.state.position.x - origin[0]) < 1e-7
            and node.state.position.y == -30
        )
        script = Scene(Document.create()).add(node).compile().document.dumps()
        for age in (0, 1, 250, 500, 1000, 1500, 2000, 2400, 2499, 2500, 2750, 2900):
            ms = round(node.lifetime.start * 1000) + age
            target, _ = reference(
                identity, ms, node.lifetime.start, origin, linear=True
            )
            actual = fill(script, ms, rgb=0xFFC0CB)
            expected = fill(target, 0, rgb=0xFFC0CB)
            if expected.getbbox() is None:
                assert actual.getbbox() is None
                geometry = None
            else:
                geometry = compare(actual, expected)
                compare(outline_envelope(script, ms), outline_envelope(target, 0))
                center = centroid(script, ms)
                assert center is not None and center[2] == 0
            straight_checks.append(
                {"id": identity, "age_ms": age, "geometry": geometry}
            )
    sheet.save(output / "sakura-flutter-reference.png")
    report = {
        "scope": "E04 all 30 isolated curved petals including fractional-centisecond births; independent keyed parameters, cubic trajectory, flutter fill/outline geometry and alpha; half-coverage silhouette tolerance 1px",
        "reference_inputs": "sung birth origin captured from author object; birth capture separately tested by validate_sakura",
        "alpha_tolerance": "1/255: fractional birth clocks can land on alpha half-integers with differing floating-point rounding; alpha errors are reported separately from geometry",
        "checks": checks,
        "straight_geometry_checks": straight_checks,
        "outline_checks": outline_checks,
        "outline_method": "Half-coverage outer envelope of unweighted fill/outline; thin ring alpha-weighted coverage differences separately reported, not thresholded into disconnected dots",
        "remaining": [
            "overlapping compositing",
            "continuous-time error bounds",
            "other renderers",
        ],
        "isolated_ass_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(output.glob("*.ass"))
        },
    }
    (output / "sakura-flutter-validation.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                "checks": len(checks),
                "max_coverage_difference": max(
                    int(c["max_coverage_difference"]) for c in checks
                ),
            }
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    validate(parser.parse_args().output)


if __name__ == "__main__":
    main()
