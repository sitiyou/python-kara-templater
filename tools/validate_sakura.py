"""E04 authored emission schedule, birth capture, native drift and cursor history.

uv run python -m tools.validate_sakura OUTPUT
"""

import argparse
import hashlib
import json
from collections import Counter
from math import hypot
from pathlib import Path

from examples.scene_sakura import build
from kara_templater import (
    Document,
    MoveAlong,
    PathObject,
    Scene,
    _ass_preview,
    _metrics,
    load_font,
)
from tools.validate_engine_backgrounds import ROOT


def centroid(script: str, ms: int) -> tuple[float, float, int] | None:
    mass = xsum = ysum = 0.0
    alphas: set[int] = set()
    for left, top, width, height, kind, color, data in _ass_preview.rasterize(
        script, ms, 1280, 720, 4_000_000, 10_000
    ):
        if kind != 0:
            continue
        alphas.add(color & 255)
        for y in range(height):
            for x in range(width):
                weight = data[y * width + x]
                mass += weight
                xsum += weight * (left + x + 0.5)
                ysum += weight * (top + y + 0.5)
    if not mass:
        return None
    if len(alphas) != 1:
        raise AssertionError("isolated particle has inconsistent alpha")
    return xsum / mass, ysum / mass, alphas.pop()


def validate(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    font = load_font(ROOT / "tests/fonts/DejaVuSans.ttf")
    scene = build()
    paths = {node.id: node for node in scene.objects if isinstance(node, PathObject)}
    cursor = paths["cursor"]
    cursor_motion = cursor.animations[0].animation
    if not isinstance(cursor_motion, MoveAlong):
        raise AssertionError("cursor must retain its editable motion path")
    # Derive the lyric span independently from native whole-run/isolated outlines.
    glyphs = _metrics.text_shape("DejaVu Sans", 72, 0, 0, 100, 100, 0, 1, "SAKURA")[4]
    extents = []
    for letter, glyph in zip("SAKURA", glyphs, strict=True):
        solo = _metrics.text_shape("DejaVu Sans", 72, 0, 0, 100, 100, 0, 1, letter)[4][
            0
        ]
        x = glyph[0][0][0] - solo[0][0][0]
        y = glyph[0][0][1] - solo[0][0][1]
        advance, height, _, _ = _metrics.text_extents(
            "DejaVu Sans", 72, 0, 0, 100, 100, 0, 1, letter
        )
        extents.append((x, y, advance, height))
    lyric_width = max(x + w for x, _, w, _ in extents)
    lyric_height = max(y + h for _, y, _, h in extents) - min(
        y for _, y, _, _ in extents
    )
    width = lyric_width + 32
    left, middle = (1280 - lyric_width) / 2 - 16, 300 + lyric_height / 2
    if (
        abs(cursor_motion.path.point(1).x - width) > 1e-7
        or hypot(cursor.state.position.x - left, cursor.state.position.y - middle)
        > 1e-7
    ):
        raise AssertionError(
            "cursor differs from independent lyric metrics and sweep padding"
        )
    schedules = {
        "ambient": tuple(2 * i / 17 for i in range(18)),
        "straight": tuple(i / 4 for i in range(6)),
        "sung": tuple(1 + i / 12 for i in range(12)),
    }
    for name, births in schedules.items():
        actual = {key for key in paths if key.startswith(name + "/")}
        if actual != {f"{name}/{i}" for i in range(len(births))}:
            raise AssertionError(f"unexpected {name} particle identities")
        for i, birth in enumerate(births):
            node = paths[f"{name}/{i}"]
            if (
                abs(node.lifetime.start - birth) > 1e-12
                or abs(node.lifetime.end - birth - 3) > 1e-12
            ):
                raise AssertionError(f"wrong lifetime for {node.id}")
            if name == "sung" and (
                hypot(
                    node.state.position.x - left - width * i / 12,
                    node.state.position.y - middle,
                )
                > 1e-7
            ):
                raise AssertionError(f"incorrect emitter birth capture for {node.id}")
    echo_checks = []
    for index in range(5):
        name = "cursor" if index == 0 else f"cursor/echo:{index}"
        node = paths[name]
        start, end = 1000 + index * 60, 2000 + index * 60
        if (
            abs(node.lifetime.start * 1000 - start) > 1e-9
            or abs(node.lifetime.end * 1000 - end) > 1e-9
        ):
            raise AssertionError(f"incorrect echo lifetime: {name}")
        script = Scene(Document.create()).add(node).compile().document.dumps()
        (output / f"cursor-{index}.ass").write_text(script)
        opacity = 1 if index == 0 else 0.4 * 0.7 ** (index - 1)
        for ms in (
            start - 1,
            start,
            start + 1,
            start + 250,
            start + 500,
            start + 750,
            end - 1,
            end,
            end + 1,
        ):
            actual = centroid(script, ms)
            if not start <= ms < end:
                if actual is not None:
                    raise AssertionError(f"{name} outside lifetime at {ms}ms")
                continue
            if actual is None:
                raise AssertionError(f"missing {name} at {ms}ms")
            sample = ms if index == 0 else ms // 20 * 20 + 10
            x = left + width * (sample - start) / 1000
            error = hypot(actual[0] - x, actual[1] - middle)
            if error > 1 or actual[2] != round((1 - opacity) * 255):
                raise AssertionError(
                    f"{name} historical position/opacity differs at {ms}ms"
                )
            echo_checks.append(
                {
                    "id": name,
                    "time_ms": ms,
                    "position_error_px": error,
                    "ass_alpha": actual[2],
                }
            )
    straight_checks = []
    for i in range(6):
        node = paths[f"straight/{i}"]
        motion = node.animations[0].animation
        if not isinstance(motion, MoveAlong):
            raise AssertionError("straight petal lost editable MoveAlong")
        velocity = motion.path.point(1)
        result = Scene(Document.create()).add(node).compile()
        if result.event_count != 1 or result.objects[0].strategy != "native-move":
            raise AssertionError("straight petal unnecessarily sampled")
        script = result.document.dumps()
        (output / f"straight-{i}.ass").write_text(script)
        start = round(node.lifetime.start * 1000)
        first = centroid(script, start + 500)
        if first is None:
            raise AssertionError("missing straight particle")
        for age in (1000, 1500, 2000):
            actual = centroid(script, start + age)
            if actual is None:
                raise AssertionError("missing straight particle")
            error = hypot(
                actual[0] - first[0] - velocity.x * (age - 500) / 3000,
                actual[1] - first[1] - 900 * (age - 500) / 3000,
            )
            if error > 1:
                raise AssertionError(f"straight drift mismatch: {i}/{age}")
            straight_checks.append(
                {"id": node.id, "age_ms": age, "displacement_error_px": error}
            )
    group_costs: dict[str, dict[str, object]] = {}
    for name in schedules:
        result = (
            Scene(Document.create())
            .add(
                *(
                    node
                    for identity, node in paths.items()
                    if identity.startswith(name + "/")
                )
            )
            .compile()
        )
        group_costs[name] = {
            "event_count": result.event_count,
            "peak_active": result.peak_active,
            "byte_count": result.byte_count,
            "strategies": dict(Counter(item.strategy for item in result.objects)),
        }
    report = {
        "scope": "E04 36 authored particles and birth capture; actual isolated ASS cursor/echo history and six native linear petals",
        "font_sha256": font.sha256,
        "reference_inputs": {
            "cursor_start": [left, middle],
            "cursor_distance": width,
            "note": "independent native glyph displacement/advance bounds, centering and 16px sweep padding",
        },
        "isolated_ass_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(output.glob("*.ass"))
        },
        "schedules_seconds": schedules,
        "particle_lifetime_seconds": 3,
        "birth_capture_checks": 12,
        "cursor_and_echo_checks": echo_checks,
        "straight_checks": straight_checks,
        "particle_group_costs": group_costs,
        "related_reports": [
            "sakura-flutter-validation.json",
            "particle-composite-validation.json",
        ],
        "remaining": [
            "continuous-time error for sampled echoes",
            "other renderers",
        ],
    }
    (output / "sakura-validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "particles": 36,
                "birth_captures": 12,
                "cursor_echo_positions": len(echo_checks),
                "straight_displacements": len(straight_checks),
            }
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    validate(parser.parse_args().output)


if __name__ == "__main__":
    main()
