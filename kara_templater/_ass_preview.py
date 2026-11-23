"""CPU mask evaluation for the ASS subset emitted by the scene compiler."""

import re
from functools import lru_cache
from math import ceil, cos, isfinite, log, radians, sin, sqrt

from PIL import Image, ImageChops, ImageFilter

from ._gpu_scene import path_coverage
from ._native_types import RasterImage
from .ass import Document, Style
from .document_text import _overrides
from .geometry import Contour, CubicSegment, LineSegment, Segment2D, Vec2, VectorPath
from .scene import Lifetime, TextObject
from .scene_animation import VisualState
from .text_geometry import outline_text

_NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)"
_TAG = re.compile(
    r"\\(alpha|[1-4][ac]|iclip|clip|move|pos|fad|org|fscx|fscy|fsp|frz|frx|fry|fax|fay|xbord|ybord|bord|xshad|yshad|shad|blur|pbo|fs|fn|fe|an|be|[bitrpucqsk])(.*)",
    re.S,
)


def blur_padding(radius: float) -> int:
    if not isfinite(radius) or not 0 <= radius <= 100:
        raise ValueError("blur radius must be finite and in 0..100")
    return ceil(4 * radius * 2 / sqrt(log(256)))


def blur_mask(
    data: bytes, width: int, height: int, radius: float, max_pixels: int
) -> tuple[int, int, int, int, bytes]:
    pad = blur_padding(radius)
    if min(width, height) <= 0 or len(data) != width * height:
        raise ValueError("invalid mask dimensions")
    w, h = width + 2 * pad, height + 2 * pad
    if w * h > max_pixels:
        raise ValueError("blur workspace exceeds budget")
    if not pad:
        return 0, 0, w, h, data
    image = Image.new("L", (w, h))
    image.paste(Image.frombytes("L", (width, height), data), (pad, pad))
    return (
        -pad,
        -pad,
        w,
        h,
        image.filter(ImageFilter.GaussianBlur(radius * 2 / sqrt(log(256)))).tobytes(),
    )


@lru_cache(maxsize=256)
def _drawing(text: str, scale: int) -> VectorPath | None:
    tokens = re.findall(r"[a-zA-Z]|" + _NUMBER, text)
    contours: list[Contour] = []
    segments: list[Segment2D] = []
    start = Vec2()
    i = 0
    command = ""
    unit = 2.0 ** (1 - scale)

    def point(index: int) -> Vec2:
        return Vec2(float(tokens[index]) * unit, float(tokens[index + 1]) * unit)

    while i < len(tokens):
        if tokens[i].isalpha():
            command = tokens[i].lower()
            i += 1
            if command == "c":
                continue
        if command in ("m", "n"):
            if segments:
                contours.append(Contour(start, tuple(segments)))
            start = point(i)
            segments = []
            command = "l"
            i += 2
        elif command == "l":
            segments.append(LineSegment(point(i)))
            i += 2
        elif command == "b":
            segments.append(CubicSegment(point(i), point(i + 2), point(i + 4)))
            i += 6
        else:
            raise ValueError(f"unsupported preview path command {command!r}")
    if segments:
        contours.append(Contour(start, tuple(segments)))
    return VectorPath(tuple(contours)) if contours else None


def _color(value: str) -> int:
    return int(value.strip("&Hh") or "0", 16)


def _defaults(style: Style) -> dict[str, str]:
    state = {
        "fn": style.fontname,
        "fs": str(style.fontsize),
        "an": str(style.align),
        "b": str(int(style.bold)),
        "i": str(int(style.italic)),
        "fscx": str(style.scale_x),
        "fscy": str(style.scale_y),
        "fsp": str(style.spacing),
        "bord": str(style.outline),
        "xshad": str(style.shadow),
        "yshad": str(style.shadow),
    }
    for role, key in enumerate(
        ("PrimaryColour", "SecondaryColour", "OutlineColour", "BackColour"), 1
    ):
        value = _color(
            style.fields.get(key, "&H00FFFFFF" if role == 1 else "&H00000000")
        )
        state[f"{role}c"] = f"&H{value & 0xFFFFFF:06x}&"
        state[f"{role}a"] = f"&H{value >> 24:02x}&"
    return state


def _apply(
    state: dict[str, str],
    block: str,
    elapsed: float,
    duration: float,
    progress: float = 1.0,
) -> None:
    for tag in _overrides(block):
        match = _TAG.fullmatch(tag)
        if match is None:
            continue
        key, value = match.groups()
        if key == "t":
            params, _, nested = value.strip()[1:-1].partition("\\")
            numbers = [float(x) for x in params.strip(",").split(",") if x]
            start, end = numbers[:2] if len(numbers) >= 2 else (0, duration)
            acceleration = numbers[-1] if len(numbers) in (1, 3) else 1
            weight = (
                min(1.0, max(0.0, (elapsed - start) / max(1.0, end - start)))
                ** acceleration
            )
            _apply(state, "\\" + nested, elapsed, duration, weight)
        elif key == "alpha":
            _apply(
                state,
                "".join(f"\\{n}a{value}" for n in range(1, 5)),
                elapsed,
                duration,
                progress,
            )
        elif key == "shad":
            _apply(state, f"\\xshad{value}\\yshad{value}", elapsed, duration, progress)
        elif key == "c":
            _apply(state, "\\1c" + value, elapsed, duration, progress)
        elif key in ("r", "q", "be", "u", "s", "k"):
            continue
        elif progress == 1:
            state[key] = value
        elif progress and key[-1] in "ac" and key[0].isdigit():
            a, b = _color(state[key]), _color(value)
            channels = [
                round(((a >> i) & 255) * (1 - progress) + ((b >> i) & 255) * progress)
                for i in (0, 8, 16)
            ]
            state[key] = (
                f"&H{sum(v << i for v, i in zip(channels, (0, 8, 16), strict=True)):x}&"
            )
        elif progress and re.fullmatch(_NUMBER, value):
            old = float(state.get(key, 0))
            state[key] = str(old + (float(value) - old) * progress)
        elif progress and key in ("clip", "iclip") and key in state:
            old_rect, vector = _clip_geometry(state[key])
            new_rect = _rectangle(value)
            if old_rect and new_rect:
                state[key] = (
                    "("
                    + ",".join(
                        str(int(a + (b - a) * progress))
                        for a, b in zip(old_rect, new_rect, strict=True)
                    )
                    + ")"
                )


def _rectangle(value: str) -> tuple[float, ...] | None:
    parts = value.strip("()").split(",")
    return (
        tuple(map(float, parts))
        if len(parts) == 4 and all(re.fullmatch(_NUMBER, p.strip()) for p in parts)
        else None
    )


def _clip_geometry(value: str) -> tuple[tuple[float, ...] | None, VectorPath | None]:
    rectangle = _rectangle(value)
    if rectangle is not None:
        return rectangle, None
    scale, separator, body = value.strip("()").partition(",")
    vector = _drawing(body if separator else scale, int(scale) if separator else 1)
    if vector and len(vector.contours) == 1:
        contour = vector.contours[0]
        if all(isinstance(s, LineSegment) for s in contour.segments):
            vertices = [contour.start, *(s.end for s in contour.segments)]
            if vertices[-1] == vertices[0]:
                vertices.pop()
            if len(vertices) == 4 and all(
                (p.x == q.x) != (p.y == q.y)
                for p, q in zip(vertices, vertices[1:] + vertices[:1], strict=True)
            ):
                xs = [p.x for p in vertices]
                ys = [p.y for p in vertices]
                if len(set(vertices)) == 4:
                    return (min(xs), min(ys), max(xs), max(ys)), None
    return None, vector


@lru_cache(maxsize=64)
def _document(script: str) -> Document:
    return Document.parse(script)


def rasterize(
    script: str, time_ms: int, width: int, height: int, max_pixels: int, max_images: int
) -> list[RasterImage]:
    if min(width, height, max_images) <= 0 or width * height > max_pixels:
        raise ValueError("frame dimensions exceed pixel budget")
    doc = _document(script)
    styles = doc.styles
    images: list[RasterImage] = []
    total = 0
    rx = re.search(r"(?im)^PlayResX:\s*(\d+)", script)
    ry = re.search(r"(?im)^PlayResY:\s*(\d+)", script)
    zoom_x = width / int(rx[1]) if rx else 1.0
    zoom_y = height / int(ry[1]) if ry else 1.0
    for line in sorted(doc.lines, key=lambda line: line.layer):
        if line.comment or not line.start_time <= time_ms < line.end_time:
            continue
        style = styles.get(line.style, Style())
        state = _defaults(style)
        elapsed = time_ms - line.start_time
        duration = line.end_time - line.start_time
        blocks = re.findall(r"(?<!\\)\{([^}]*)\}", line.text)
        for block in blocks:
            _apply(state, block, elapsed, duration)
        content = re.sub(r"(?<!\\)\{[^}]*\}", "", line.text)
        if not content:
            continue

        def num(key: str, default: float = 0, state=state) -> float:
            return float(state.get(key, default))

        if num("p"):
            path = _drawing(content, int(num("p")))
        else:
            text = (
                content.replace(r"\N", "\n")
                .replace(r"\h", " ")
                .replace(r"\{", "{")
                .replace(r"\}", "}")
            )
            path = outline_text(
                TextObject(
                    id="preview",
                    lifetime=Lifetime(0, 1),
                    text=text,
                    font=state["fn"],
                    font_size=num("fs"),
                    bold=bool(num("b")),
                    italic=bool(num("i")),
                    spacing=num("fsp"),
                    alignment=int(num("an")),
                ),
                max_points=200_000,
            ).path
        if path is None:
            continue
        alignment = int(num("an")) - 1
        margin_y = line.margin_v or style.margin_v
        xy = (
            (
                line.margin_l or style.margin_l,
                doc.meta.res_x / 2,
                doc.meta.res_x - (line.margin_r or style.margin_r),
            )[alignment % 3],
            (doc.meta.res_y - margin_y, doc.meta.res_y / 2, margin_y)[alignment // 3],
        )
        if "pos" in state:
            px, py = map(float, state["pos"].strip("()").split(","))
            xy = (px, py)
        if "move" in state:
            v = list(map(float, state["move"].strip("()").split(",")))
            a, b = v[4:] if len(v) == 6 else (0, duration)
            t = max(0.0, min(1.0, (elapsed - a) / max(1.0, b - a)))
            xy = (v[0] + (v[2] - v[0]) * t, v[1] + (v[3] - v[1]) * t)
        angle = radians(-num("frz"))

        def transform(pt: Vec2, xy=xy, angle=angle, num=num) -> Vec2:
            x = pt.x * num("fscx") / 100
            y = pt.y * num("fscy") / 100
            x, y = x + y * num("fax"), y + x * num("fay")
            return Vec2(
                (xy[0] + x * cos(angle) - y * sin(angle)) * zoom_x,
                (xy[1] + x * sin(angle) + y * cos(angle)) * zoom_y,
            )

        path = path.map(transform)
        alpha = _color(state["1a"])
        border = num("xbord", num("bord"))
        appearance = VisualState(
            border=border,
            blur=num("blur"),
            opacity=1 - alpha / 255,
            shadow=Vec2(num("xshad"), num("yshad")),
        )
        # The frame budget counts cropped output. Allow antialias padding in scratch masks.
        planes = path_coverage(
            path,
            appearance,
            alpha < 255,
            max_pixels + 8 * (width + height) + 256,
            "preview",
        )
        for x, y, w, h, role, _, data in planes:
            channel = (1, 3, 4)[role]
            a = _color(state[f"{channel}a"])
            if a == 255:
                continue
            bgr = _color(state[f"{channel}c"])
            color = (bgr & 255) << 24 | (bgr & 0xFF00) << 8 | (bgr >> 16) << 8 | a
            mask = Image.frombytes("L", (w, h), data)
            for key in ("clip", "iclip"):
                if key not in state:
                    continue
                clip = Image.new("L", (w, h))
                rect, vector = _clip_geometry(state[key])
                if rect:
                    l, t, r, b = rect
                    coords = (
                        round(l * zoom_x) - x,
                        round(t * zoom_y) - y,
                        round(r * zoom_x) - x,
                        round(b * zoom_y) - y,
                    )
                    if coords[2] > coords[0] and coords[3] > coords[1]:
                        clip.paste(255, coords)
                else:
                    if vector:
                        for cx, cy, cw, ch, _, _, bitmap in path_coverage(
                            vector.map(lambda pt: Vec2(pt.x * zoom_x, pt.y * zoom_y)),
                            VisualState(border=0),
                            True,
                            max_pixels,
                            "clip",
                        ):
                            clip.paste(
                                Image.frombytes("L", (cw, ch), bitmap), (cx - x, cy - y)
                            )
                mask = ImageChops.multiply(
                    mask, clip if key == "clip" else ImageChops.invert(clip)
                )
            box = mask.getbbox()
            if box is None:
                continue
            l, t, r, b = box
            l, t, r, b = max(l, -x), max(t, -y), min(r, width - x), min(b, height - y)
            if r <= l or b <= t:
                continue
            total += (r - l) * (b - t)
            if total > max_pixels or len(images) >= max_images:
                raise ValueError("raster coverage exceeds budget")
            images.append(
                (
                    x + l,
                    y + t,
                    r - l,
                    b - t,
                    role,
                    color,
                    mask.crop((l, t, r, b)).tobytes(),
                )
            )
    return images
