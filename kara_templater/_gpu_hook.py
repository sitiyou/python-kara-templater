"""Serialize shared Scene draws as textures in a standalone libplacebo user shader."""

import hashlib
import json
from array import array
from collections import defaultdict
from collections.abc import Iterator
from heapq import merge
from itertools import groupby
from math import ceil, floor, hypot, isfinite
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Protocol

from ._gpu_scene import DrawCommand, SceneFrames
from ._hook_motion import ShaderInstance, Span, spans
from ._hook_wipe import SingingWipe, singing_wipe
from ._karaoke_motion import _SPIN_FLIP, _TILT_POP, ZoomScale
from ._native_types import RasterImage
from .geometry import Affine2D, Vec2
from .lyric_highlights import _FeatheredSingingClip
from .paint_fields import LinearGradient
from .scene import RectangleKeyframes
from .timeline import ProgressCurve

_WIDTH = 2048
_TILE = 64


class _Writer(Protocol):
    def write(self, data: bytes, /) -> int: ...


class _BoundedWriter:
    def __init__(self, target: _Writer, limit: int) -> None:
        self.target = target
        self.limit = limit
        self.written = 0

    def write(self, data: bytes, /) -> int:
        if self.written + len(data) > self.limit:
            raise ValueError(f"Hook byte budget exceeded (limit {self.limit} bytes)")
        size = self.target.write(data)
        self.written += size
        return size


class _Atlas:
    """Shelf-pack coverage. Clamp sampling inside each rectangle in the shader."""

    def __init__(self) -> None:
        self.data = bytearray()
        self.locations: dict[tuple[int, int, bytes], tuple[int, int]] = {}
        self.x = self.y = self.row = 0

    def add(self, width: int, height: int, pixels: bytes) -> tuple[int, int]:
        key = width, height, pixels
        if key in self.locations:
            return self.locations[key]
        if width > _WIDTH:
            raise ValueError("hook mask exceeds 2048 pixels in width")
        if self.x + width > _WIDTH:
            self.x, self.y, self.row = 0, self.y + self.row, 0
        if self.y + height > 8192:
            raise ValueError("hook mask atlas is full; export a shorter interval")
        size = (self.y + height) * _WIDTH
        if size > len(self.data):
            self.data.extend(bytes(size - len(self.data)))
        for row in range(height):
            dest = (self.y + row) * _WIDTH + self.x
            self.data[dest : dest + width] = pixels[row * width : (row + 1) * width]
        point = self.locations[key] = self.x, self.y
        self.x += width
        self.row = max(self.row, height)
        return point


class _Table:
    """Intern repeated frame, tile, material and draw records in one float texture."""

    def __init__(self) -> None:
        self.functions: dict[str, None] = {}
        self.paints: dict[str, int] = {}
        self.programs: dict[str, int] = {}
        self.animated_colors = False
        self.values = array("f")
        self.records: dict[bytes, int] = {}

    def add(self, *record: float) -> int:
        packed = array("f", record).tobytes()
        existing = self.records.get(packed)
        if existing is not None:
            return existing
        offset = len(self.values)
        # Above 2**24, float32 cannot encode every scalar address. Texel-aligned
        # record starts and curve tags (+/-4) stay exact up to the texture limit.
        padding = (-offset) % 4 if offset >= 2**24 - 4 else 0
        offset += padding
        if offset + len(record) > _WIDTH * 8192 * 4:
            raise ValueError("hook data texture is full; export a shorter interval")
        if padding:
            self.values.extend([0.0] * padding)
        self.values.frombytes(packed)
        self.records[packed] = offset
        return offset


def _ramp_record(table: _Table, mat: LinearGradient | None, kind: int) -> int:
    ramp = (
        None
        if mat is None
        else mat.fill
        if kind == 0
        else mat.outline
        if kind == 1
        else None
    )
    if ramp is None:
        return -1
    return table.add(
        len(ramp.stops),
        *(
            n
            for s in ramp.stops
            for n in (
                s.position,
                s.color.red / 255,
                s.color.green / 255,
                s.color.blue / 255,
            )
        ),
    )


def _draw_record(
    table: _Table,
    atlas: _Atlas,
    draw: DrawCommand,
    image: RasterImage,
    motion: int,
    clip_motion: int,
    edge: _FeatheredSingingClip | None,
    wipe: SingingWipe | None,
    inherited: int,
) -> int:
    x, y, w, h, kind, color, pixels = image
    u, v = atlas.add(w, h, pixels) if pixels else (-1, -1)
    mat = draw.gradient
    stops = _ramp_record(table, mat, kind)
    if kind == 3 and draw.side_shading is not None:
        depth_pixels, back = draw.side_shading
        stops = table.add(*atlas.add(w, h, depth_pixels), back.red / 255, back.green / 255, back.blue / 255)
    feather = -1
    if (edge is not None or wipe is not None) and kind in (0, 1):
        if edge is not None:
            before = edge.unsung_fill if kind == 0 else edge.unsung_outline
            base = edge.unsung_gradient
        else:
            assert wipe is not None
            before = wipe.before.fill if kind == 0 else wipe.before.outline
            base = wipe.gradient
        core = edge.front_color if edge else None
        core_id = (
            -1
            if core is None
            else table.add(core.red / 255, core.green / 255, core.blue / 255)
        )
        feather = table.add(
            before.red / 255,
            before.green / 255,
            before.blue / 255,
            edge.width if edge else 0,
            core_id,
            _ramp_record(table, base, kind),
            int(base is not None and base.space == "screen"),
            int(base is not None and base.axis == "y"),
        )
    fixed = -1
    if draw.fixed_stroke is not None and kind in (1, 2):
        stroke = draw.fixed_stroke
        fx, fy, fw, fh, _, _, face = stroke.face
        mask = table.add(fx, fy, fw, fh, *atlas.add(fw, fh, face))
        fixed = table.add(
            table.add(*stroke.grid), mask, draw.border, stroke.sigma, int(stroke.filled),
            stroke.shadow.x, stroke.shadow.y,
        )
    geom = table.add(x, y, w, h, u, v, fixed)
    custom = -1
    if draw.shader_paint is not None:
        shader = draw.shader_paint
        table.functions[shader.functions] = None
        program = table.paints.setdefault(shader.source, len(table.paints))
        data = table.add(*shader.parameters) if shader.parameters else -1
        custom = table.add(program, data, draw.time_origin, kind, draw.border)
    paint = table.add(
        *(float(color >> s & 255) / 255 for s in (24, 16, 8)),
        1 - (color & 255) / 255,
        stops,
        int(mat is not None and mat.space == "screen"),
        int(mat is not None and mat.axis == "y"),
        feather,
        custom,
        kind,
        draw.face_opacity,
    )
    m = draw.transform
    transform = table.add(m.a, m.b, m.c, m.d, m.tx, m.ty)
    clip = -1
    if wipe is not None:
        # Tags below -1 select which rectangle side supplies the shader wipe.
        clip = -2 - wipe.edge
    elif draw.clip is not None:
        clip = table.add(*draw.clip.bounds, int(draw.clip.local))
    return table.add(
        geom, paint, transform, clip, draw.opacity, motion, clip_motion, inherited
    )


def _texture(
    out: _Writer, name: str, fmt: str, data: bytes | bytearray, stride: int
) -> None:
    rows = max(1, ceil(len(data) / stride))
    out.write(f"//!TEXTURE {name}\n//!SIZE {_WIDTH} {rows}\n//!FORMAT {fmt}\n".encode())
    out.write(b"//!FILTER LINEAR\n" if fmt == "r8" else b"//!FILTER NEAREST\n")
    for start in range(0, len(data), 32768):
        out.write(data[start : start + 32768].hex().encode())
    out.write(b"00" * (rows * stride - len(data)) + b"\n\n")


def _motion_record(
    table: _Table, span: Span, fps: int, origin: int, opacity_mode: int
) -> int:
    instance = span.shader
    if instance is not None:
        program = instance.program
        table.functions[program.functions] = None
        kind = table.programs.setdefault(program.source, len(table.programs))
        base = instance.base
        matrices = []
        for state in (instance.outer, instance.inner):
            m = state.transform
            matrices.extend((m.a, m.b, m.c, m.d, m.tx, m.ty))
        args = table.add(*program.parameters) if program.parameters else -1
        colors = 0
        if instance.local:
            colors = int("fill" in program.channels) + 2 * int("outline" in program.channels)
        if colors:
            table.animated_colors = True
        binding = table.add(
            kind,
            args,
            base.position.x,
            base.position.y,
            base.scale.x,
            base.scale.y,
            base.skew.x,
            base.skew.y,
            base.rotation,
            base.opacity,
            instance.outer.opacity * instance.inner.opacity,
            *matrices,
            program.progress_scale,
            program.progress_offset,
            base.border,
            colors,
            *((base.fill.red/255, base.fill.green/255, base.fill.blue/255,
               base.outline.red/255, base.outline.green/255, base.outline.blue/255) if colors else ()),
        )
        return table.add(
            instance.start * fps - origin,
            instance.duration * fps,
            0,
            -1,
            binding,
            0,
            opacity_mode,
        )
    motion = span.motion
    if motion is None:
        return -1
    curve = motion.curve
    if isinstance(curve, ZoomScale):
        curve = 8 + table.add(curve.note, curve.duration, curve.exponent)
    elif isinstance(curve, ProgressCurve):
        curve = table.add(len(curve.knots), *(v for knot in curve.knots for v in knot))
        # Negative indices distinguish shared knot tables from the built-in rates.
        curve = -4 - curve
    m = motion.end.transform
    end = table.add(m.a, m.b, m.c, m.d, m.tx, m.ty, motion.end.opacity)
    return table.add(
        motion.start * fps - origin,
        motion.duration * fps,
        motion.peak,
        curve,
        end,
        int(motion.fast_reveal),
        opacity_mode,
    )


def _tiles(
    image: RasterImage, transforms: tuple[Affine2D, ...], cols: int, rows: int,
    padding: float = 0,
) -> Iterator[int]:
    x, y, w, h, *_ = image
    corners = [
        (m.a * s + m.c * t + m.tx, m.b * s + m.d * t + m.ty)
        for m in transforms
        for s in (x, x + w)
        for t in (y, y + h)
    ]
    xs, ys = zip(*corners, strict=True)
    for ty in range(max(0, floor((min(ys) - padding) / _TILE)), min(rows, ceil((max(ys) + padding) / _TILE))):
        for tx in range(
            max(0, floor((min(xs) - padding) / _TILE)), min(cols, ceil((max(xs) + padding) / _TILE))
        ):
            yield ty * cols + tx


def _program_tiles(
    instance: ShaderInstance, image: RasterImage, cols: int, rows: int, padding: float = 0,
) -> Iterator[int]:
    program = instance.program
    if program.source not in (_TILT_POP, _SPIN_FLIP):
        yield from range(cols * rows)
        return
    params = program.parameters
    center = Vec2(params[0], params[1])
    pivot = Vec2(params[2], params[3]) if program.source == _TILT_POP else center
    outer, base, inner = (
        instance.outer.transform,
        instance.base.transform,
        instance.inner.transform,
    )
    fixed = outer.apply(base.apply(pivot))
    x, y, w, h, *_ = image
    radius = 0.0
    shift = center - pivot
    shift_radius = hypot(
        base.a * shift.x + base.c * shift.y, base.b * shift.x + base.d * shift.y
    )
    for dx in (x, x + w):
        for dy in (y, y + h):
            px = inner.a * dx + inner.c * dy + inner.tx - center.x
            py = inner.b * dx + inner.d * dy + inner.ty - center.y
            rx = base.a * px + base.c * py
            ry = base.b * px + base.d * py
            if program.source == _TILT_POP:
                bound = 1.3 * (hypot(rx, ry) + shift_radius)
            else:
                # v*tan((1-v)*pi/2) <= 2/pi for 0 <= v <= 1.
                bound = hypot(rx, ry) + abs(instance.base.scale.y * px)
            radius = max(radius, bound)
    width = radius * hypot(outer.a, outer.c) + padding
    height = radius * hypot(outer.b, outer.d) + padding
    for row in range(
        max(0, floor((fixed.y - height) / _TILE)),
        min(rows, ceil((fixed.y + height) / _TILE)),
    ):
        for col in range(
            max(0, floor((fixed.x - width) / _TILE)),
            min(cols, ceil((fixed.x + width) / _TILE)),
        ):
            yield row * cols + col


def _timeline(
    frames: SceneFrames,
    atlas: _Atlas,
    table: _Table,
    fps: int,
    origin: int,
    count: int,
    cols: int,
    rows: int,
) -> int:
    def events(
        order: int, stream: Iterator[Span]
    ) -> Iterator[tuple[int, int, Span | None]]:
        for span in stream:
            yield span.first - origin, order, span
            yield span.stop - origin, order, None

    def clip_track(
        keys: RectangleKeyframes, start: float, edge: int | None = None
    ) -> int:
        return table.add(
            len(keys.keyframes),
            *(
                value
                for time, bounds in keys.keyframes
                for value in (
                    (start + time) * fps - origin,
                    table.add(*bounds) if edge is None else bounds[edge],
                )
            ),
        )

    start, end = origin / fps, (origin + count) / fps
    streams = []
    wipes: dict[int, SingingWipe] = {}
    i = 0
    while i < len(frames.leaves):
        leaf = frames.leaves[i]
        if leaf.end > start - 1e-9 and leaf.start < end + 1e-9:
            if i + 1 < len(frames.leaves):
                wipe = singing_wipe(leaf, frames.leaves[i + 1])
                if wipe is not None:
                    i += 1
                    wipes[i] = wipe
                    leaf = frames.leaves[i]
            streams.append(events(i, spans(frames, leaf, fps, origin, origin + count)))
        i += 1
    stream = merge(*streams, key=lambda event: event[:2])
    active_tiles: dict[int, dict[int, list[int]]] = {}
    tile_draws: list[dict[int, list[int]]] = [{} for _ in range(cols * rows)]
    clip_records: dict[int, int] = {}
    inherited_records: dict[str, int] = {}
    group_masks: dict[str, int] = {}
    timelines = [[0, -1] for _ in tile_draws]
    for i, changes in groupby(stream, key=lambda event: event[0]):
        if i == count:
            break
        dirty: set[int] = set()
        for _, order, span in changes:
            for tile in active_tiles.pop(order, ()):
                del tile_draws[tile][order]
                dirty.add(tile)
            if span is None:
                continue
            draw = span.draw
            transforms = (
                (draw.transform,)
                if span.motion is None
                else (draw.transform, span.motion.end.transform)
            )
            wipe = wipes.get(order)
            node = frames.leaves[order].node
            clip_motion = clip_records.get(order, -1)
            if span.clip_keys and clip_motion < 0:
                clip_motion = clip_track(
                    span.clip_keys, node.time_origin, wipe.edge if wipe else None
                )
                clip_records[order] = clip_motion
            inherited = inherited_records.get(node.id, -1)
            inherited_clips = frames.group_clips.get(node.id, ())
            if inherited < 0 and inherited_clips:
                masks = []
                for group, rect in inherited_clips:
                    if group.id not in group_masks:
                        base = table.add(rect.left, rect.top, rect.right, rect.bottom)
                        track = (
                            clip_track(rect.deform, group.time_origin)
                            if isinstance(rect.deform, RectangleKeyframes)
                            else -1
                        )
                        group_masks[group.id] = table.add(base, track)
                    masks.append(group_masks[group.id])
                inherited = inherited_records[node.id] = table.add(len(masks), *masks)
            batch: dict[int, list[int]] = defaultdict(list)
            clip = node.clip
            edge = clip if isinstance(clip, _FeatheredSingingClip) else None
            variants = [(draw.images, 0)]
            if span.alternate_masks is not None:
                # Select the native border bitmap at playback opacity without
                # sampling an entire fade or exporting a per-frame command list.
                mode = 1 if round((1 - draw.opacity * draw.face_opacity) * 255) == 0 else -1
                variants = [(draw.images, mode), (span.alternate_masks, -mode)]
            for images, mode in variants:
                motion = _motion_record(table, span, fps, origin, mode)
                for image in images:
                    record = _draw_record(
                        table,
                        atlas,
                        draw,
                        image,
                        motion,
                        clip_motion,
                        edge,
                        wipe,
                        inherited,
                    )
                    stroke = draw.fixed_stroke
                    padding = draw.border + 4 * stroke.sigma + 1 if stroke and image[4] in (1, 2) else 0
                    for tile in (
                        _program_tiles(span.shader, image, cols, rows, padding)
                        if span.shader and span.shader.program.channels - {"opacity", "border"}
                        else _tiles(image, transforms, cols, rows, padding)
                    ):
                        batch[tile].append(record)
            active_tiles[order] = batch
            for tile, commands in batch.items():
                tile_draws[tile][order] = commands
                dirty.add(tile)
        for tile in dirty:
            draws = tile_draws[tile]
            commands = [cmd for order in sorted(draws) for cmd in draws[order]]
            record = table.add(len(commands), *commands) if commands else -1
            timeline = timelines[tile]
            if i == 0:
                timeline[1] = record
            elif record != timeline[-1]:
                timeline.extend((i, record))
    return table.add(
        *(
            table.add(len(t) // 2, *t) if len(t) > 2 or t[1] >= 0 else -1
            for t in timelines
        )
    )


def export_hook(
    frames: SceneFrames,
    path: Path,
    fps: int,
    start: float,
    duration: float | None,
    *,
    resources: bool = False,
    max_bytes: int | None = None,
) -> None:
    if max_bytes is not None and (type(max_bytes) is not int or max_bytes < 1):
        raise ValueError("Hook byte budget must be a positive integer")
    if type(fps) is not int or not 1 <= fps <= 240:
        raise ValueError("hook fps must be an integer in 1..240")
    if not isfinite(start) or start < 0 or abs(start * fps - round(start * fps)) > 1e-7:
        raise ValueError("hook start must be nonnegative and frame aligned")
    length = frames.end - start if duration is None else duration
    if not isfinite(length) or not 0 < length * fps <= 250000:
        raise ValueError("hook interval must cover 1..250000 frames")
    count = ceil(length * fps)
    atlas, table = _Atlas(), _Table()
    w, h = frames.resolution
    cols, rows = ceil(w / _TILE), ceil(h / _TILE)
    # The header is uniform across fragments. Per-song constants in this
    # texture let preview sessions reuse a linked program across edits.
    table.values.extend([fps, round(start * fps), count, w, h, cols, 0])
    timeline = _timeline(
        frames, atlas, table, fps, round(start * fps), count, cols, rows
    )
    table.values[6] = timeline
    cases = "\n".join(
        f"case {kind}: {{ {body} }} break;" for body, kind in table.programs.items()
    )
    source = (
        _SHADER.replace("HAS_ANIMATED_COLORS", str(int(table.animated_colors)))
        .replace("MOTION_FUNCTIONS", "\n".join(table.functions))
        .replace("MOTION_CASES", cases)
        .replace("PAINT_CASES", "\n".join(f"case {index}: {{ {body} }} break;"
                                        for body,index in table.paints.items()))
        .replace("APPLY_PAINT", """
            int paint=refAt(p+8);
            if(paint>=0) {
                float opacity=alpha*item(p+3);
                applyPaint(paint,screen,local,coverage,(float(index)+item(1))/item(0),ink,opacity,pen);
                a=coverage*clamp(opacity,0.,1.);
            }
        """ if table.paints else "")
        .replace("TILESIZE", str(_TILE))
        .replace("TEXWIDTH", str(_WIDTH))
    )
    if resources:
        textures = (
            ("KARAMASK", atlas.data, _WIDTH),
            ("KARADATA", table.values.tobytes(), _WIDTH * 16),
        )
        with TemporaryDirectory(dir=path.parent) as tmp:
            staging = Path(tmp) / "resources"
            staging.mkdir()
            sizes = {}
            hashes = {}
            for name, raw, stride in textures:
                rows = max(1, ceil(len(raw) / stride))
                sizes[name] = [_WIDTH, rows]
                padding = bytes(rows * stride - len(raw))
                with (staging / (name + ".bin")).open("wb") as out:
                    out.write(raw)
                    out.write(padding)
                digest = hashlib.sha256(raw)
                digest.update(padding)
                hashes[name] = digest.hexdigest()
            metadata = dict(sizes, clock=[fps, round(start * fps), count], hashes=hashes)
            (staging / "textures.json").write_text(
                json.dumps(metadata), encoding="ascii"
            )
            (staging / "scene.frag").write_text(
                source.split("//!BIND KARADATA\n", 1)[1], encoding="utf-8"
            )
            staging.rename(path)
        return
    with NamedTemporaryFile(dir=path.parent, delete=False) as out:
        temp = Path(out.name)
        try:
            writer = out if max_bytes is None else _BoundedWriter(out, max_bytes)
            _texture(writer, "KARAMASK", "r8", atlas.data, _WIDTH)
            _texture(writer, "KARADATA", "rgba32f", table.values.tobytes(), _WIDTH * 16)
            writer.write(source.encode())
            out.close()
            temp.replace(path)
        finally:
            out.close()
            temp.unlink(missing_ok=True)


_SHADER = """//!PARAM PTS
//!TYPE DYNAMIC float
//!MINIMUM -1
//!MAXIMUM 10000000
-1

//!HOOK MAIN
//!BIND HOOKED
//!BIND KARAMASK
//!BIND KARADATA
float item(int i) {
    int n=i/4;
    return texelFetch(KARADATA,ivec2(n%TEXWIDTH,n/TEXWIDTH),0)[i%4];
}
int refAt(int i) { return int(item(i)); }
vec2 pairAt(int i) { return vec2(item(i),item(i+1)); }
vec3 rgbAt(int i) { return vec3(item(i),item(i+1),item(i+2)); }
// Both the scene directory and user curves are sorted pairs (time, value).
int preceding(int table, float t) {
    int lo=0, hi=refAt(table);
    while (lo+1<hi) {
        int mid=(lo+hi)/2;
        if(item(table+1+2*mid)<=t) lo=mid; else hi=mid;
    }
    return table+1+2*lo;
}
vec4 rectangleAt(int base,int track,float t) {
    if(track<0) return vec4(pairAt(base),pairAt(base+2));
    int k=preceding(track,t);
    int first=refAt(k+1);
    vec4 rect=vec4(pairAt(first),pairAt(first+2));
    if(k+2>=track+1+2*refAt(track) || t<=item(k)) return rect;
    int nextRect=refAt(k+3);
    return mix(rect,vec4(pairAt(nextRect),pairAt(nextRect+2)),(t-item(k))/(item(k+2)-item(k)));
}
bool insideRect(vec2 p,vec4 rect) {
    return all(greaterThanEqual(p,rect.xy)) && all(lessThan(p,rect.zw));
}
bool insideGroups(vec2 screen,int masks,float t) {
    if(masks<0) return true;
    int end=masks+1+refAt(masks);
    for(int i=masks+1;i<end;i++) {
        int mask=refAt(i);
        if(!insideRect(screen,rectangleAt(refAt(mask),refAt(mask+1),t))) return false;
    }
    return true;
}
float weight(int motion, int index) {
    float p=clamp((float(index)-item(motion))/item(motion+1),0.,1.);
    float peak=item(motion+2);
    if(peak>0.) p=clamp(min(p/peak,(1.-p)/(1.-peak)),0.,1.);
    int curve=refAt(motion+3);
    if(curve==0) return p;
    if(curve==1) return p*p*(3.-2.*p);
    if(curve==2) return p*p*p*(p*(6.*p-15.)+10.);
    if(curve==3) return p*p;
    if(curve==4) return 1.-(1.-p)*(1.-p);
    if(curve==5) return p<0.5 ? 2.*p*p : 1.-2.*(1.-p)*(1.-p);
    if(curve==6) return sin(3.14159265*p);
    if(curve>=8) {
        int k=curve-8;
        float t=p*item(k+1), note=item(k);
        float d=t<=note ? 1.-t/note : min(1.,(t-note)/0.30);
        return 1.-pow(clamp(d,0.,1.),item(k+2));
    }
    int knots=-4-curve;
    int k=preceding(knots,p);
    if(k+2>=knots+1+2*refAt(knots)) return item(k+1);
    return mix(item(k+1),item(k+3),(p-item(k))/(item(k+2)-item(k)));
}
vec3 rampColor(int stops,float t) {
    int end=stops+1+4*refAt(stops);
    for(int k=stops+5;k<end;k+=4) {
        if(t<=item(k)) return mix(rgbAt(k-3),rgbAt(k+1),clamp((t-item(k-4))/(item(k)-item(k-4)),0.,1.));
    }
    return rgbAt(end-3);
}
vec3 paintColor(vec3 solid,int ramp,vec2 screen,vec2 local) {
    int stops=refAt(ramp);
    if(stops<0) return solid;
    vec2 pos=item(ramp+1)>0.?screen:local;
    float t=item(ramp+2)>0.?pos.y:pos.x;
    return rampColor(stops,t);
}
mat2 basisOf(vec2 scale,vec2 skew,float angle) {
    float a=radians(angle), c=cos(a), s=sin(a);
    return mat2(c,s,-s,c)*mat2(scale.x,skew.y*scale.y,skew.x*scale.x,scale.y);
}
mat2 matrixAt(int i) { return mat2(pairAt(i),pairAt(i+2)); }
MOTION_FUNCTIONS
void applyPaint(int paint,vec2 screen,vec2 local,inout float coverage,float time,inout vec3 ink,inout float alpha,float pen){
    int data=refAt(paint+1),component=refAt(paint+3);
    if(pen<0.) pen=item(paint+4);
    time-=item(paint+2);
    switch(refAt(paint)){PAINT_CASES}
}
void applyProgram(int b,float p,out mat2 basis,out vec2 position,out float alpha,out float pen,int component,out vec3 animatedInk) {
    int data=refAt(b+1);
    vec2 pos=pairAt(b+2), scale=pairAt(b+4), skew=pairAt(b+6);
    float angle=item(b+8);
    alpha=item(b+9);
    pen=item(b+25);
    p=p*item(b+23)+item(b+24);
    #if HAS_ANIMATED_COLORS
    int colors=refAt(b+26);
    vec3 fill=vec3(0.), outline=vec3(0.);
    if(colors!=0) { fill=rgbAt(b+27); outline=rgbAt(b+30); }
    #else
    vec3 fill=vec3(0.), outline=vec3(0.);
    #endif
    switch(refAt(b)) { MOTION_CASES }
    #if HAS_ANIMATED_COLORS
    animatedInk=(colors & (1<<component))!=0 ? (component==0 ? fill : outline) : vec3(-1.);
    #else
    animatedInk=vec3(-1.);
    #endif
    mat2 outerBasis=matrixAt(b+11), localBasis=basisOf(scale,skew,angle);
    basis=outerBasis*localBasis*matrixAt(b+17);
    position=pairAt(b+15)+outerBasis*(pos+localBasis*pairAt(b+21));
    alpha*=item(b+10);
}
bool isometry(mat2 basis) {
    return abs(dot(basis[0],basis[0])-1.)<1e-6
        && abs(dot(basis[1],basis[1])-1.)<1e-6 && abs(dot(basis[0],basis[1]))<1e-6;
}
float sampleMask(int geom,vec2 local) {
    vec2 uv=local-pairAt(geom), size=pairAt(geom+2);
    if(any(lessThan(uv,vec2(0))) || any(greaterThanEqual(uv,size))) return 0.;
    if(item(geom+4)<0.) return 1.;
    vec2 texel=pairAt(geom+4)+clamp(uv,vec2(0.5),size-0.5);
    return textureLod(KARAMASK,texel/vec2(textureSize(KARAMASK,0)),0.).r;
}
float gaussianEdge(float distance,float sigma) {
    float z=clamp(distance/(1.41421356*sigma),-5.,5.), z2=z*z;
    return 0.5+0.5*sign(z)*sqrt(max(0.,1.-exp(-z2*(1.27323954+0.147*z2)/(1.+0.147*z2))));
}
float blurredStroke(float distance,float pen,float sigma,bool cutout) {
    float backing=gaussianEdge(pen-distance,sigma);
    return cutout ? max(backing-gaussianEdge(-distance,sigma),0.) : backing;
}
float segmentDistanceSquared(vec2 delta,vec2 direction) {
    float t=clamp(dot(delta,direction)/max(dot(direction,direction),1e-20),0.,1.);
    vec2 residual=delta-t*direction;
    return dot(residual,residual);
}
float fixedCoverage(int stroke,int geom,vec2 local,mat2 basis,mat2 toLocal,int role,float faceAlpha) {
    float pen=item(stroke+2), sigma=item(stroke+3), pad=pen+1.+4.*sigma;
    float raster=sigma>0. ? sampleMask(geom,local) : 0.;
    if(role==2) local-=pairAt(stroke+5);
    int grid=refAt(stroke), cols=refAt(grid+2), rows=refAt(grid+3);
    vec2 center=(local-pairAt(grid))/16.;
    mat2 axes=transpose(toLocal);
    // Pull a screen-space pen back to a conservative local rectangle for the cell lookup.
    vec2 reach=pad*vec2(length(axes[0]),length(axes[1]))/16.;
    if(sigma>0.) reach=max(reach,vec2(pad/16.));
    vec2 lo=center-reach, hi=center+reach, last=vec2(cols-1,rows-1);
    if(any(lessThan(hi,vec2(0))) || any(greaterThanEqual(lo,last+1.))) return raster;
    ivec2 firstCell=ivec2(floor(clamp(lo,vec2(0),last)));
    ivec2 lastCell=ivec2(floor(clamp(hi,vec2(0),last)));
    float nearest=pad*pad, localNearest=pad*pad;
    for(int row=firstCell.y;row<=lastCell.y;row++) {
        for(int col=firstCell.x;col<=lastCell.x;col++) {
            int bucket=grid+refAt(grid+4+row*cols+col);
            int count=refAt(bucket);
            for(int i=0;i<count;i++) {
                int line=grid+refAt(bucket+1+i);
                vec2 delta=local-pairAt(line), direction=pairAt(line+2);
                nearest=min(nearest,segmentDistanceSquared(basis*delta,basis*direction));
                if(sigma>0.) localNearest=min(localNearest,segmentDistanceSquared(delta,direction));
            }
        }
    }
    float face=sampleMask(refAt(stroke+1),local), distance=sqrt(nearest);
    bool cutout=item(stroke+4)==0. || (role==1 && faceAlpha<1.-0.5/255.);
    if(sigma==0.) {
        float edge=clamp(0.5+pen-distance,0.,1.);
        return cutout ? max(edge-face,0.) : max(edge,face);
    }
    // Keep the convolved silhouette and correct only for the pen's change of metric.
    // The two corrections cancel for an isometry, even on corners and thin strokes.
    float side=face>=0.5 ? -1. : 1.;
    float screenStroke=blurredStroke(side*distance,pen,sigma,cutout);
    float localStroke=blurredStroke(side*sqrt(localNearest),pen,sigma,cutout);
    return clamp(raster+screenStroke-localStroke,0.,1.);
}
vec4 hook() {
    vec4 bg=HOOKED_tex(HOOKED_pos);
    // mpv supplies the media timestamp. FFmpeg can leave the parameter at -1.
    int index = PTS >= 0.0
        ? int(floor(PTS * item(0) + 0.001)) - refAt(1)
        : frame - 1;
    if(index<0 || index>=refAt(2)) return bg;
    vec2 screen=HOOKED_pos*pairAt(3);
    ivec2 tile=ivec2(screen)/TILESIZE;
    int track=refAt(refAt(6)+tile.y*refAt(5)+tile.x);
    if(track<0) return bg;
    int list=refAt(preceding(track,float(index))+1);
    if(list<0) return bg;
    int count=refAt(list);
    for(int j=0;j<count;j++) {
        int cmd=refAt(list+1+j), g=refAt(cmd), p=refAt(cmd+1), m=refAt(cmd+2);
        if(!insideGroups(screen,refAt(cmd+7),float(index))) continue;
        mat2 basis=mat2(pairAt(m),pairAt(m+2));
        vec2 pos=pairAt(m+4);
        float alpha=item(cmd+4), pen=-1.;
        vec3 animatedInk=vec3(-1.);
        int motion=refAt(cmd+5);
        if(motion>=0) {
            if(refAt(motion+3)==-1) {
                float phase=clamp((float(index)-item(motion))/item(motion+1),0.,1.);
                applyProgram(refAt(motion+4),phase,basis,pos,alpha,pen,refAt(p+9),animatedInk);
            } else {
            float w=weight(motion,index);
            int end=refAt(motion+4);
            basis=mat2(mix(basis[0],pairAt(end),w),mix(basis[1],pairAt(end+2),w));
            pos=mix(pos,pairAt(end+4),w);
            float reveal=item(motion+5)>0. ? clamp(4.*(float(index)-item(motion))/item(motion+1),0.,1.) : w;
            alpha=mix(alpha,item(end+6),reveal);
            }
            int mode=refAt(motion+6);
            if(mode!=0 && (mode>0)!=(alpha*item(p+10)>=1.-0.5/255.)) continue;
        }
        if(alpha<=0. || determinant(basis)==0.) continue;
        mat2 toLocal=inverse(basis);
        vec2 local=toLocal*(screen-pos);
        int fixedStroke=refAt(g+6);
        bool useFixed=fixedStroke>=0 && !isometry(basis);
        vec2 uv=local-pairAt(g), size=pairAt(g+2);
        if(!useFixed && (any(lessThan(uv,vec2(0))) || any(greaterThanEqual(uv,size)))) continue;
        float edgeDistance=0.;
        int clip=refAt(cmd+3);
        bool waiting=false;
        if(clip < -1) {
            if(any(lessThan(local,vec2(-65536.))) || any(greaterThanEqual(local,vec2(65536.)))) continue;
            int side=-2-clip, sweep=refAt(cmd+6), k=preceding(sweep,float(index));
            float edge=item(k+1);
            if(k+2<sweep+1+2*refAt(sweep) && float(index)>item(k))
                edge=mix(edge,item(k+3),(float(index)-item(k))/(item(k+2)-item(k)));
            float coord=(side%2==0)?local.x:local.y;
            waiting=side<2 ? coord<edge : coord>=edge;
            edgeDistance=side<2 ? coord-edge : edge-coord;
        } else if(clip>=0) {
            vec2 pos=item(clip+4)>0.?local:screen;
            vec4 rect=rectangleAt(clip,refAt(cmd+6),float(index));
            edgeDistance=min(pos.x-rect.x,rect.z-pos.x);
            if(!insideRect(pos,rect)) continue;
        }
        float coverage=useFixed
            ? fixedCoverage(fixedStroke,g,local,basis,toLocal,refAt(p+9),alpha*item(p+10))
            : sampleMask(g,local);
        float a=coverage*item(p+3)*alpha;
        int feather=refAt(p+7);
        vec3 ink;
        if(refAt(p+9)==3 && refAt(p+4)>=0) {
            int shading=refAt(p+4);
            vec2 depthUV=pairAt(shading)+clamp(uv,vec2(0.5),size-0.5);
            float moment=textureLod(KARAMASK,depthUV/vec2(textureSize(KARAMASK,0)),0.).r;
            ink=mix(rgbAt(p),rgbAt(shading+2),clamp(moment/max(coverage,0.00001),0.,1.));
        } else if(waiting && feather>=0) {
            ink=paintColor(rgbAt(feather),feather+5,screen,local);
        } else {
            ink=paintColor(animatedInk.r>=0. ? animatedInk : rgbAt(p),p+4,screen,local);
            if(feather>=0 && edgeDistance<item(feather+3)) {
                float phase=edgeDistance/item(feather+3);
                vec3 before=paintColor(rgbAt(feather),feather+5,screen,local);
                ink=mix(before,ink,smoothstep(0.,1.,phase));
                int core=refAt(feather+4);
                if(core>=0) {
                    float strength=smoothstep(0.,0.16,phase)*(1.-smoothstep(0.42,0.78,phase));
                    ink=mix(ink,rgbAt(core),strength);
                }
            }
        }
        APPLY_PAINT
        bg.rgb=mix(bg.rgb,ink,a);
        bg.a=a+bg.a*(1.-a);
    }
    return bg;
}
"""
