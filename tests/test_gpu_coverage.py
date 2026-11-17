"""Actual optional GPU output compared against independent pixel expectations."""

from importlib.util import find_spec

import pytest

from kara_templater import Color, ColorRamp, ColorStop, LinearGradient
from kara_templater._gpu import CoverageRenderer, GpuClip
from kara_templater.geometry import Affine2D

pytestmark = pytest.mark.skipif(
    find_spec("moderngl") is None, reason="optional GPU dependency"
)


def ramp():
    return LinearGradient(
        fill=ColorRamp(
            (
                ColorStop(0, Color(255, 0, 0)),
                ColorStop(4, Color(0, 255, 0)),
                ColorStop(8, Color(0, 0, 255)),
            )
        ),
        axis="x",
        space="local",
    )


def pixel(data, x, y, width=16):
    i = (y * width + x) * 4
    return tuple(data[i : i + 4])


def test_gpu_local_ramp_clips_transforms_and_alpha():
    with CoverageRenderer(16, 8) as gpu:
        gpu.clear()
        # Native bitmap alpha and ASS color alpha both contribute.
        image = (0, 0, 8, 4, 0, 0xFFFFFF7F, bytes([128]) * 32)
        gpu.draw(
            image,
            transform=Affine2D(tx=3, ty=2),
            opacity=0.5,
            gradient=ramp(),
            clip=GpuClip((0, 0, 5, 4), local=True),
        )
        data = gpu.read()
        assert pixel(data, 2, 2) == (0, 0, 0, 0)
        assert pixel(data, 8, 2) == (0, 0, 0, 0)
        for x in range(5):
            t = (x + 0.5) / 4
            rgb = (1 - t, t, 0) if t <= 1 else (0, 2 - t, t - 1)
            expected = tuple(round(c * 128 / 255 * 128 * 0.5) for c in rgb) + (32,)
            assert all(
                abs(a - b) <= 1
                for a, b in zip(pixel(data, x + 3, 2), expected, strict=True)
            )
        gpu.clear()
        # Change only the clip: retained pixels must be byte-identical.
        gpu.draw(image, transform=Affine2D(tx=3, ty=2), opacity=0.5, gradient=ramp())
        unclipped = gpu.read()
        assert all(
            pixel(data, x, y) == pixel(unclipped, x, y)
            for y in range(8)
            for x in range(8)
        )


def test_gpu_material_ownership_compositing_and_bounded_cache():
    with CoverageRenderer(16, 8, cache_bytes=32) as gpu:
        gpu.clear()
        solid = bytes([255]) * 16
        # Outline remains its native green when only fill has a gradient.
        gpu.draw((0, 0, 4, 4, 1, 0x00FF0000, solid), gradient=ramp())
        assert pixel(gpu.read(), 1, 1) == (0, 255, 0, 255)
        gpu.draw((0, 0, 4, 4, 0, 0xFF00007F, solid))
        assert all(
            abs(a - b) <= 1
            for a, b in zip(pixel(gpu.read(), 1, 1), (128, 127, 0, 255), strict=True)
        )
        assert gpu.cached_bytes == 16  # Same coverage, different color/role.
        for value in range(20):
            gpu.draw((0, 0, 4, 4, 0, 0xFFFFFF00, bytes([value]) * 16))
            assert gpu.cached_bytes <= 32
        with pytest.raises(ValueError, match="budget"):
            gpu.draw((0, 0, 6, 6, 0, 0, bytes(36)))
    assert gpu.cached_bytes == 0
    gpu.close()
    with pytest.raises(RuntimeError, match="closed"):
        gpu.read()


def test_gpu_screen_space_gradient_and_half_open_clip():
    with CoverageRenderer(16, 8) as gpu:
        gpu.clear()
        gradient = LinearGradient(fill=ramp().fill)
        gpu.draw(
            (0, 0, 8, 4, 0, 0xFFFFFF00, bytes([255]) * 32),
            transform=Affine2D(tx=3),
            gradient=gradient,
            clip=GpuClip((4, 0, 6, 4)),
        )
        data = gpu.read()
        assert pixel(data, 3, 1) == (0, 0, 0, 0)
        assert pixel(data, 6, 1) == (0, 0, 0, 0)
        assert all(
            abs(a - b) <= 1
            for a, b in zip(pixel(data, 4, 1), (0, 223, 32, 255), strict=True)
        )
