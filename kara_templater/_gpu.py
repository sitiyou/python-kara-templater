"""GPU coverage compositor. Scene evaluation and ASS lowering stay outside it.

Input coverage is immutable, already shaped by libass in local coordinates.
Output bytes are top-down premultiplied RGBA, unlike RasterFrame's straight RGBA.
No shader source is loaded from documents. This adapter is not yet a public API.
"""

from array import array
from collections import OrderedDict
from dataclasses import dataclass
from importlib import import_module
from typing import Self, cast

from ._gpu_driver import Driver, Resource, Texture
from ._native_types import RasterImage
from .geometry import Affine2D, finite
from .paint_fields import ColorRamp, LinearGradient

_IDENTITY = Affine2D()

_VERTEX = """#version 330
in vec2 corner;
uniform vec4 bounds;
uniform vec2 resolution;
uniform vec4 basis;
uniform vec2 translation;
out vec2 uv;
out vec2 local_position;
out vec2 screen_position;
void main() {
    uv = corner;
    local_position = bounds.xy + corner * bounds.zw;
    screen_position = mat2(basis.xy, basis.zw) * local_position + translation;
    gl_Position = vec4(screen_position.x / resolution.x * 2. - 1.,
                       1. - screen_position.y / resolution.y * 2., 0., 1.);
}
"""
_FRAGMENT = """#version 330
uniform sampler2D coverage;
uniform vec4 color;
uniform int stop_count;
uniform vec4 stops[16];
uniform bool local_gradient;
uniform bool vertical_gradient;
uniform bool clipped;
uniform bool local_clip;
uniform vec4 clip_bounds;
in vec2 uv;
in vec2 local_position;
in vec2 screen_position;
out vec4 result;
void main() {
    vec2 clip_position = local_clip ? local_position : screen_position;
    if (clipped && (any(lessThan(clip_position, clip_bounds.xy)) ||
                    any(greaterThanEqual(clip_position, clip_bounds.zw)))) discard;
    vec3 rgb = color.rgb;
    if (stop_count > 0) {
        vec2 position = local_gradient ? local_position : screen_position;
        float p = vertical_gradient ? position.y : position.x;
        rgb = stops[stop_count - 1].yzw;
        for (int i = 1; i < stop_count; ++i) {
            if (p <= stops[i].x) {
                float t = clamp((p - stops[i - 1].x) /
                                (stops[i].x - stops[i - 1].x), 0., 1.);
                rgb = mix(stops[i - 1].yzw, stops[i].yzw, t);
                break;
            }
        }
    }
    float alpha = texture(coverage, uv).r * color.a;
    result = vec4(rgb * alpha, alpha);
}
"""


@dataclass(frozen=True)
class GpuClip:
    bounds: tuple[float, float, float, float]
    local: bool = False

    def __post_init__(self) -> None:
        finite(*self.bounds)
        left, top, right, bottom = self.bounds
        if left > right or top > bottom:
            raise ValueError("GPU clip bounds cannot be inverted")


class CoverageRenderer:
    """Own one GL context and a byte-bounded LRU coverage texture cache.

    Call clear/draw/read per frame. Draw order is painter order. A caller binds
    the material of exactly one object at a time; no color-based owner guessing.
    Use only on the thread where constructed. Closing releases all GL resources.
    """

    def __init__(
        self,
        width: int,
        height: int,
        *,
        backend: str = "egl",
        cache_bytes: int = 64 * 1024 * 1024,
        max_pixels: int = 16_777_216,
    ) -> None:
        if any(
            type(n) is not int or n < 1
            for n in (width, height, cache_bytes, max_pixels)
        ):
            raise ValueError("GPU dimensions and budgets must be positive integers")
        if width * height > max_pixels:
            raise ValueError("GPU framebuffer pixel budget exceeded")
        try:
            self._driver = cast(Driver, import_module("moderngl"))
        except ImportError as error:
            raise RuntimeError(
                "GPU rendering requires the optional moderngl package"
            ) from error
        self.width, self.height = width, height
        self._limit = cache_bytes
        self._bytes = 0
        self._cache: OrderedDict[tuple[int, int, bytes], Texture] = OrderedDict()
        self._resources: list[Resource] = []
        self._closed = False
        self._ctx = self._driver.create_standalone_context(require=330, backend=backend)
        self._resources.append(self._ctx)
        try:
            self._program = self._ctx.program(
                vertex_shader=_VERTEX, fragment_shader=_FRAGMENT
            )
            self._resources.append(self._program)
            buffer = self._ctx.buffer(array("f", (0, 0, 1, 0, 0, 1, 1, 1)).tobytes())
            self._resources.append(buffer)
            self._quad = self._ctx.vertex_array(
                self._program, [(buffer, "2f", "corner")]
            )
            self._resources.append(self._quad)
            self._frame = self._ctx.simple_framebuffer((width, height), components=4)
            self._resources.append(self._frame)
            self._program["resolution"].value = (width, height)
            self._program["coverage"].value = 0
            self._ctx.enable(self._driver.BLEND)
            self._ctx.blend_func = (self._driver.ONE, self._driver.ONE_MINUS_SRC_ALPHA)
        except Exception:
            self.close()
            raise

    @property
    def device(self) -> str:
        return str(self._ctx.info["GL_RENDERER"])

    @property
    def cached_bytes(self) -> int:
        return self._bytes

    def _check_open(self) -> None:
        if self._closed:
            raise RuntimeError("GPU renderer is closed")

    def clear(self) -> None:
        self._check_open()
        self._frame.use()
        self._frame.clear(0, 0, 0, 0)

    def draw(
        self,
        image: RasterImage,
        *,
        transform: Affine2D = _IDENTITY,
        opacity: float = 1,
        gradient: LinearGradient | None = None,
        clip: GpuClip | None = None,
    ) -> None:
        self._check_open()
        x, y, width, height, kind, color, coverage = image
        finite(opacity)
        if not 0 <= opacity <= 1:
            raise ValueError("GPU opacity must be in 0..1")
        if (
            width < 1
            or height < 1
            or len(coverage) != width * height
            or not 0 <= color <= 0xFFFFFFFF
        ):
            raise ValueError("invalid GPU coverage image")
        if len(coverage) > self._limit:
            raise ValueError("GPU coverage image exceeds texture cache budget")
        ramp: ColorRamp | None = None
        if gradient is not None:
            ramp = (
                gradient.fill if kind == 0 else gradient.outline if kind == 1 else None
            )
        if ramp is not None and len(ramp.stops) > 16:
            raise ValueError("GPU gradients support at most 16 color stops")
        key = width, height, coverage
        texture = self._cache.get(key)
        if texture is None:
            while self._bytes + len(coverage) > self._limit:
                old_key, old_texture = self._cache.popitem(last=False)
                old_texture.release()
                self._bytes -= len(old_key[2])
            texture = self._ctx.texture((width, height), 1, coverage, alignment=1)
            texture.filter = self._driver.LINEAR, self._driver.LINEAR
            texture.repeat_x = texture.repeat_y = False
            self._cache[key] = texture
            self._bytes += len(coverage)
        self._cache.move_to_end(key)
        texture.use(0)
        p = self._program
        p["bounds"].value = x, y, width, height
        p["basis"].value = transform.a, transform.b, transform.c, transform.d
        p["translation"].value = transform.tx, transform.ty
        p["color"].value = tuple((color >> s & 255) / 255 for s in (24, 16, 8)) + (
            (1 - (color & 255) / 255) * opacity,
        )
        p["stop_count"].value = len(ramp.stops) if ramp is not None else 0
        if ramp is not None:
            values = array("f")
            for stop in ramp.stops:
                values.extend(
                    (
                        stop.position,
                        stop.color.red / 255,
                        stop.color.green / 255,
                        stop.color.blue / 255,
                    )
                )
            values.extend([0.0] * (64 - len(values)))
            p["stops"].write(values.tobytes())
        p["local_gradient"].value = gradient is not None and gradient.space == "local"
        p["vertical_gradient"].value = gradient is not None and gradient.axis == "y"
        p["clipped"].value = clip is not None
        p["local_clip"].value = clip is not None and clip.local
        p["clip_bounds"].value = clip.bounds if clip is not None else (0, 0, 0, 0)
        self._frame.use()
        self._quad.render(self._driver.TRIANGLE_STRIP)

    def read(self) -> bytes:
        """Top-down premultiplied RGBA8, ready for an explicitly matching consumer."""
        self._check_open()
        data = self._frame.read(components=4, alignment=1)
        stride = self.width * 4
        return b"".join(
            data[row * stride : (row + 1) * stride]
            for row in reversed(range(self.height))
        )

    def close(self) -> None:
        if self._closed:
            return
        for texture in self._cache.values():
            texture.release()
        self._cache.clear()
        self._bytes = 0
        for resource in reversed(self._resources):
            resource.release()
        self._resources.clear()
        self._closed = True

    def __enter__(self) -> Self:
        self._check_open()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
