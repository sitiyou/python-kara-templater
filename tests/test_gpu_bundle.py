import zlib
from copy import deepcopy

import pytest

from kara_templater import (
    Document,
    Lifetime,
    Line,
    Scene,
    TextObject,
    Vec2,
    VisualState,
)
from kara_templater._gpu_bundle import EnhancedFrames, encode_scene
from kara_templater._gpu_scene import SceneFrames


def fixture():
    fallback = Document.create(width=160, height=100)
    fallback.records.append(Line(text=r"{\k50}Hi", end_time=500))
    scene = Scene(fallback).add(
        TextObject(
            id="word",
            text="Hi",
            lifetime=Lifetime(0, 0.5),
            state=VisualState(position=Vec2(20, 20)),
        )
    )
    return scene, fallback


def test_gpu_bundle_round_trip_matches_scene_and_keeps_fallback():
    scene, fallback = fixture()
    original = fallback.dumps()
    encoded = encode_scene(scene, fallback, fps=10)
    assert fallback.dumps() == original
    assert [line for line in encoded.lines if not line.comment] == fallback.lines
    # Ordinary parse never imports a GPU driver or runs callback/shader code.
    decoded = EnhancedFrames.read(Document.parse(encoded.dumps()))
    assert (decoded.width, decoded.height, decoded.fps, decoded.count) == (
        160,
        100,
        10,
        5,
    )
    expected = SceneFrames(scene)
    assert list(decoded.frames()) == [expected.at(i / 10) for i in range(5)]


def test_gpu_bundle_rejects_changed_fallback_missing_parts_and_version():
    scene, fallback = fixture()
    encoded = encode_scene(scene, fallback, fps=10)
    changed = deepcopy(encoded)
    changed.lines[0].text += "edited"
    with pytest.raises(ValueError, match="fallback changed"):
        EnhancedFrames.read(changed)
    changed = deepcopy(encoded)
    changed.records.pop()
    with pytest.raises(ValueError, match="missing or duplicate"):
        EnhancedFrames.read(changed)
    changed = deepcopy(encoded)
    next(
        line for line in changed.lines if line.actor == "header"
    ).text = '[2,1,"hash","hash"]'
    with pytest.raises(ValueError, match="version"):
        EnhancedFrames.read(changed)
    with pytest.raises(ValueError, match="already contains"):
        encode_scene(scene, encoded)


def test_gpu_bundle_rejects_truncated_frame_stream():
    scene, fallback = fixture()
    decoded = EnhancedFrames.read(encode_scene(scene, fallback, fps=10))
    from dataclasses import replace

    truncated = replace(
        decoded,
        _payload=zlib.compress(
            zlib.decompress(decoded._payload).rsplit(b"\n", 2)[0] + b"\n"
        ),
    )
    with pytest.raises(ValueError, match="ended"):
        list(truncated.frames())


def test_gpu_streaming_decoder_matches_large_records_and_rejects_truncation(
    monkeypatch,
):
    from kara_templater import _gpu_bundle

    lines = [b"header", b"mask" * 40_000, b"frame" * 25_000, b"end"]
    packed = zlib.compress(b"\n".join(lines) + b"\n")
    assert list(_gpu_bundle._payload_lines(packed)) == lines
    with pytest.raises(ValueError, match="truncated"):
        list(_gpu_bundle._payload_lines(packed[:-2]))
    monkeypatch.setattr(_gpu_bundle, "_MAX_RAW", 100_000)
    with pytest.raises(ValueError, match="budget"):
        list(_gpu_bundle._payload_lines(packed))
