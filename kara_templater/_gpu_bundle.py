"""Versioned data-only GPU payload carried by ordinary ASS Comment records.

Version 1 stores shared masks and frame-indexed draws. Callback evaluation happens
only during export; reading never imports effect scripts or accepts shader code.
The explicit fallback is the whole ordinary-player presentation.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import zlib
from collections.abc import Iterator
from copy import deepcopy
from dataclasses import dataclass
from math import ceil, isfinite
from typing import cast

from ._gpu import GpuClip
from ._gpu_scene import DrawCommand, SceneFrames
from ._native_types import RasterImage
from .ass import Document, Line
from .composition import Color
from .geometry import Affine2D
from .paint_fields import ColorRamp, ColorStop, LinearGradient
from .scene import Scene

_EFFECT = "kara-gpu"
_PART = 32_768
_MAX_PACKED = 64 * 1024 * 1024
_MAX_RAW = 512 * 1024 * 1024
_MAX_MASKS = 64 * 1024 * 1024


def _json(value: object) -> bytes:
    return json.dumps(
        value, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def _ramp(ramp: ColorRamp | None) -> object:
    return (
        None
        if ramp is None
        else [
            [s.position, s.color.red, s.color.green, s.color.blue] for s in ramp.stops
        ]
    )


def _material(gradient: LinearGradient | None) -> object:
    return (
        None
        if gradient is None
        else [
            gradient.axis,
            gradient.space,
            _ramp(gradient.fill),
            _ramp(gradient.outline),
        ]
    )


def encode_scene(scene: Scene, fallback: Document, *, fps: int = 60) -> Document:
    """Create a new ASS document with bounded, portable sampled enhancement data."""
    if type(fps) is not int or not 1 <= fps <= 240:
        raise ValueError("GPU export fps must be an integer in 1..240")
    frames = SceneFrames(scene)
    if frames.resolution != (fallback.meta.res_x, fallback.meta.res_y):
        raise ValueError("GPU scene and fallback resolutions must match")
    if any(line.effect == _EFFECT for line in fallback.lines):
        raise ValueError("fallback already contains GPU enhancement data")
    count = ceil(frames.end * fps)
    if not 1 <= count <= 250_000:
        raise ValueError("GPU export requires 1..250000 frames")
    compressor = zlib.compressobj(level=6)
    packed = bytearray()
    raw_size = 0

    def emit(value: object) -> None:
        nonlocal raw_size
        data = _json(value) + b"\n"
        raw_size += len(data)
        if raw_size > _MAX_RAW:
            raise ValueError("GPU payload uncompressed byte budget exceeded")
        packed.extend(compressor.compress(data))
        if len(packed) > _MAX_PACKED:
            raise ValueError("GPU payload compressed byte budget exceeded")

    emit([1, *frames.resolution, fps, count])
    masks: dict[tuple[int, int, bytes], int] = {}
    mask_bytes = 0
    for index in range(count):
        commands = []
        for command in frames.at(index / fps):
            images = []
            for x, y, width, height, kind, color, data in command.images:
                key = width, height, data
                identity = masks.get(key)
                if identity is None:
                    identity = len(masks)
                    mask_bytes += len(data)
                    if mask_bytes > _MAX_MASKS:
                        raise ValueError("GPU shared mask byte budget exceeded")
                    masks[key] = identity
                    emit(
                        [
                            "mask",
                            identity,
                            width,
                            height,
                            base64.b64encode(data).decode("ascii"),
                        ]
                    )
                images.append([identity, x, y, kind, color])
            transform = command.transform
            commands.append(
                [
                    command.object_id,
                    images,
                    [
                        transform.a,
                        transform.b,
                        transform.c,
                        transform.d,
                        transform.tx,
                        transform.ty,
                    ],
                    command.opacity,
                    _material(command.gradient),
                    None
                    if command.clip is None
                    else [command.clip.local, *command.clip.bounds],
                ]
            )
        emit(["frame", index, commands])
    packed.extend(compressor.flush())
    if len(packed) > _MAX_PACKED:
        raise ValueError("GPU payload compressed byte budget exceeded")
    encoded = base64.b64encode(packed).decode("ascii")
    parts = [encoded[i : i + _PART] for i in range(0, len(encoded), _PART)]
    result = deepcopy(fallback)
    header = [
        1,
        len(parts),
        hashlib.sha256(packed).hexdigest(),
        hashlib.sha256(result.dumps().encode("utf-8")).hexdigest(),
    ]
    result.records.append(
        Line(
            comment=True,
            effect=_EFFECT,
            actor="header",
            text=_json(header).decode("ascii"),
        )
    )
    result.records.extend(
        Line(comment=True, effect=_EFFECT, actor=str(i), text=part)
        for i, part in enumerate(parts)
    )
    return result


def _list(value: object, length: int | None = None) -> list[object]:
    if not isinstance(value, list) or (length is not None and len(value) != length):
        raise ValueError("invalid GPU payload record")
    return cast(list[object], value)


def _int(value: object, low: int, high: int) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or not low <= value <= high
    ):
        raise ValueError("invalid GPU payload integer")
    return value


def _number(value: object) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not isfinite(value)
    ):
        raise ValueError("invalid GPU payload number")
    return float(value)


def _text(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("invalid GPU payload string")
    return value


def _read_json(data: str | bytes) -> object:
    try:
        value: object = json.loads(data)
    except (ValueError, RecursionError) as error:
        raise ValueError("invalid GPU payload JSON") from error
    return value


def _read_ramp(value: object) -> ColorRamp | None:
    if value is None:
        return None
    stops = _list(value)
    if not 2 <= len(stops) <= 16:
        raise ValueError("GPU gradients require 2..16 stops")
    result = []
    for stop in stops:
        p, red, green, blue = _list(stop, 4)
        result.append(
            ColorStop(
                _number(p),
                Color(_int(red, 0, 255), _int(green, 0, 255), _int(blue, 0, 255)),
            )
        )
    return ColorRamp(tuple(result))


def _read_material(value: object) -> LinearGradient | None:
    if value is None:
        return None
    axis, space, fill, outline = _list(value, 4)
    if axis not in ("x", "y") or space not in ("local", "screen"):
        raise ValueError("invalid GPU gradient coordinates")
    return LinearGradient(
        axis="x" if axis == "x" else "y",
        space="local" if space == "local" else "screen",
        fill=_read_ramp(fill),
        outline=_read_ramp(outline),
    )


def _read_clip(value: object) -> GpuClip | None:
    if value is None:
        return None
    local, left, top, right, bottom = _list(value, 5)
    if type(local) is not bool:
        raise ValueError("invalid GPU clip coordinates")
    return GpuClip(
        (_number(left), _number(top), _number(right), _number(bottom)), local=local
    )


def _payload_lines(packed: bytes) -> Iterator[bytes]:
    """Bounded incremental inflation; never retain the complete command stream."""
    decompressor = zlib.decompressobj()
    pending = bytearray()
    scanned = total = 0
    try:
        for offset in range(0, len(packed), 65_536):
            chunk = packed[offset : offset + 65_536]
            while True:
                data = decompressor.decompress(chunk, 65_536)
                chunk = decompressor.unconsumed_tail
                total += len(data)
                if total > _MAX_RAW:
                    raise ValueError("GPU decoded payload byte budget exceeded")
                pending.extend(data)
                start = 0
                while (end := pending.find(b"\n", scanned)) >= 0:
                    yield bytes(pending[start:end])
                    start = scanned = end + 1
                if start:
                    del pending[:start]
                scanned = len(pending)
                if len(pending) > 90 * 1024 * 1024:
                    raise ValueError("GPU record byte budget exceeded")
                if not chunk and len(data) < 65_536:
                    break
        if not decompressor.eof or decompressor.unused_data or pending:
            raise ValueError("invalid or truncated compressed GPU payload")
    except zlib.error as error:
        raise ValueError("invalid compressed GPU payload") from error


@dataclass(frozen=True)
class EnhancedFrames:
    width: int
    height: int
    fps: int
    count: int
    _payload: bytes

    @classmethod
    def read(cls, document: Document) -> EnhancedFrames:
        metadata = [line for line in document.lines if line.effect == _EFFECT]
        if not metadata or any(not line.comment for line in metadata):
            raise ValueError("GPU data must be carried by Comment records")
        headers = [line for line in metadata if line.actor == "header"]
        if len(headers) != 1:
            raise ValueError("GPU payload requires exactly one header")
        version, part_count, digest, fallback_digest = _list(
            _read_json(headers[0].text), 4
        )
        if type(version) is not int or version != 1:
            raise ValueError("unsupported GPU payload version")
        count = _int(part_count, 1, ceil(_MAX_PACKED * 4 / 3 / _PART) + 1)
        parts = {line.actor: line.text for line in metadata if line.actor != "header"}
        if len(metadata) != count + 1 or set(parts) != {str(i) for i in range(count)}:
            raise ValueError("missing or duplicate GPU payload parts")
        if any(len(text) > _PART for text in parts.values()):
            raise ValueError("GPU payload part exceeds byte budget")
        try:
            packed = base64.b64decode(
                "".join(parts[str(i)] for i in range(count)), validate=True
            )
        except (ValueError, binascii.Error) as error:
            raise ValueError("invalid GPU payload encoding") from error
        if len(packed) > _MAX_PACKED or hashlib.sha256(packed).hexdigest() != digest:
            raise ValueError("GPU payload size or digest mismatch")
        fallback = Document(
            [
                r
                for r in document.records
                if not isinstance(r, Line) or r.effect != _EFFECT
            ],
            document.meta,
        )
        if (
            hashlib.sha256(fallback.dumps().encode("utf-8")).hexdigest()
            != fallback_digest
        ):
            raise ValueError("ASS fallback changed after GPU export; export it again")
        try:
            header = next(_payload_lines(packed))
        except StopIteration as error:
            raise ValueError("empty GPU payload") from error
        version, width, height, fps, count = _list(_read_json(header), 5)
        if type(version) is not int or version != 1:
            raise ValueError("unsupported GPU stream version")
        w, h = _int(width, 1, 16_384), _int(height, 1, 16_384)
        if w * h > 16_777_216 or (w, h) != (document.meta.res_x, document.meta.res_y):
            raise ValueError("GPU payload resolution mismatch or pixel budget exceeded")
        return cls(w, h, _int(fps, 1, 240), _int(count, 1, 250_000), packed)

    def frames(self) -> Iterator[tuple[DrawCommand, ...]]:
        """Decode sequentially, retaining shared masks rather than rendered frames."""
        stream = _payload_lines(self._payload)
        next(stream)
        masks: list[tuple[int, int, bytes]] = []
        mask_bytes = 0
        expected = 0
        for line in stream:
            record = _list(_read_json(line))
            if record and record[0] == "mask":
                _, identity, width, height, encoded = _list(record, 5)
                if _int(identity, 0, 1_000_000) != len(masks):
                    raise ValueError("GPU mask identities must be sequential")
                w, h = _int(width, 1, 16_384), _int(height, 1, 16_384)
                if w * h + mask_bytes > _MAX_MASKS:
                    raise ValueError("GPU mask byte budget exceeded")
                try:
                    data = base64.b64decode(_text(encoded), validate=True)
                except (ValueError, binascii.Error) as error:
                    raise ValueError("invalid GPU mask encoding") from error
                if len(data) != w * h:
                    raise ValueError("GPU mask dimensions mismatch")
                masks.append((w, h, data))
                mask_bytes += len(data)
                continue
            kind, index, values = _list(record, 3)
            if kind != "frame" or _int(index, 0, self.count - 1) != expected:
                raise ValueError("GPU frames must be sequential")
            draws = _list(values)
            if len(draws) > 10_000:
                raise ValueError("GPU frame draw budget exceeded")
            commands = []
            for value in draws:
                identity, entries, matrix, opacity, material, clip = _list(value, 6)
                images: list[RasterImage] = []
                entries = _list(entries)
                if len(entries) > 10_000:
                    raise ValueError("GPU object image budget exceeded")
                for entry in entries:
                    resource, x, y, role, color = _list(entry, 5)
                    w, h, data = masks[_int(resource, 0, len(masks) - 1)]
                    images.append(
                        (
                            _int(x, -1_000_000, 1_000_000),
                            _int(y, -1_000_000, 1_000_000),
                            w,
                            h,
                            _int(role, 0, 2),
                            _int(color, 0, 0xFFFFFFFF),
                            data,
                        )
                    )
                transform = Affine2D(*(_number(v) for v in _list(matrix, 6)))
                alpha = _number(opacity)
                if not 0 <= alpha <= 1:
                    raise ValueError("GPU opacity must be in 0..1")
                commands.append(
                    DrawCommand(
                        _text(identity),
                        tuple(images),
                        transform,
                        alpha,
                        _read_material(material),
                        _read_clip(clip),
                    )
                )
            expected += 1
            yield tuple(commands)
        if expected != self.count:
            raise ValueError("GPU stream ended before its declared frame count")
