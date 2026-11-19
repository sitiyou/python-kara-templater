"""Serialize shared Scene draws as textures in a standalone libplacebo user shader."""

from array import array
from collections import defaultdict
from collections.abc import Iterator
from heapq import merge
from itertools import groupby
from math import ceil, floor, isfinite
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Protocol

from ._gpu_scene import DrawCommand, SceneFrames
from ._hook_motion import Span, spans
from ._native_types import RasterImage
from .geometry import Affine2D
from .lyric_highlights import _FeatheredSingingClip
from .paint_fields import LinearGradient
from .scene import Scene
from .timeline import ProgressCurve

_WIDTH = 2048
_TILE = 128


class _Writer(Protocol):
    def write(self, data: bytes, /) -> int: ...


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
        self.values = array("f")
        self.records: dict[tuple[float, ...], int] = {}

    def add(self, *record: float) -> int:
        existing = self.records.get(record)
        if existing is not None:
            return existing
        offset = len(self.values)
        if offset + len(record) > 2**24 - 4:
            raise ValueError(
                "hook data exceeds exact float addressing; export a shorter interval"
            )
        self.values.extend(record)
        self.records[record] = offset
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
) -> int:
    x, y, w, h, kind, color, pixels = image
    u, v = atlas.add(w, h, pixels)
    mat = draw.gradient
    stops = _ramp_record(table, mat, kind)
    feather = -1
    if edge is not None and kind in (0, 1):
        before = edge.unsung_fill if kind == 0 else edge.unsung_outline
        core = edge.front_color
        core_id = -1 if core is None else table.add(core.red / 255, core.green / 255, core.blue / 255)
        base = edge.unsung_gradient
        feather = table.add(before.red / 255, before.green / 255, before.blue / 255,
                            edge.width, core_id, _ramp_record(table, base, kind),
                            int(base is not None and base.space == "screen"),
                            int(base is not None and base.axis == "y"))
    geom = table.add(x, y, w, h, u, v)
    paint = table.add(
        *(float(color >> s & 255) / 255 for s in (24, 16, 8)),
        1 - (color & 255) / 255,
        stops,
        int(mat is not None and mat.space == "screen"),
        int(mat is not None and mat.axis == "y"),
        feather,
    )
    m = draw.transform
    transform = table.add(m.a, m.b, m.c, m.d, m.tx, m.ty)
    clip = (
        -1 if draw.clip is None else table.add(*draw.clip.bounds, int(draw.clip.local))
    )
    return table.add(geom, paint, transform, clip, draw.opacity, motion, clip_motion)


def _texture(
    out: _Writer, name: str, fmt: str, data: bytes | bytearray, stride: int
) -> None:
    rows = max(1, ceil(len(data) / stride))
    out.write(f"//!TEXTURE {name}\n//!SIZE {_WIDTH} {rows}\n//!FORMAT {fmt}\n".encode())
    out.write(b"//!FILTER LINEAR\n" if fmt == "r8" else b"//!FILTER NEAREST\n")
    for start in range(0, len(data), 32768):
        out.write(data[start : start + 32768].hex().encode())
    out.write(b"00" * (rows * stride - len(data)) + b"\n\n")


def _motion_record(table: _Table, span: Span, fps: int, origin: int, opacity_mode: int) -> int:
    motion = span.motion
    if motion is None:
        return -1
    curve = motion.curve
    if isinstance(curve, tuple):
        curve = 3 + table.add(*curve)
    elif isinstance(curve, ProgressCurve):
        curve = table.add(len(curve.knots), *(v for knot in curve.knots for v in knot))
        # Negative indices distinguish shared knot tables from the built-in rates.
        curve = -1 - curve
    m = motion.end.transform
    end = table.add(m.a, m.b, m.c, m.d, m.tx, m.ty, motion.end.opacity)
    return table.add(
        motion.start * fps - origin,
        motion.duration * fps,
        motion.peak,
        curve,
        end,
        span.first - origin if isinstance(motion.curve, tuple) else 0,
        int(motion.fast_reveal),
        opacity_mode,
    )


def _tiles(
    image: RasterImage, transforms: tuple[Affine2D, ...], cols: int, rows: int
) -> Iterator[int]:
    x, y, w, h, *_ = image
    corners = [
        (m.a * s + m.c * t + m.tx, m.b * s + m.d * t + m.ty)
        for m in transforms
        for s in (x, x + w)
        for t in (y, y + h)
    ]
    xs, ys = zip(*corners, strict=True)
    for ty in range(max(0, floor(min(ys) / _TILE)), min(rows, ceil(max(ys) / _TILE))):
        for tx in range(
            max(0, floor(min(xs) / _TILE)), min(cols, ceil(max(xs) / _TILE))
        ):
            yield ty * cols + tx


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

    stream = merge(
        *(
            events(i, spans(frames, leaf, fps, origin, origin + count))
            for i, leaf in enumerate(frames.leaves)
        ),
        key=lambda event: event[:2],
    )
    active: dict[int, dict[int, list[int]]] = {}
    timeline = [0, table.add(*([-1] * (cols * rows)))]
    for i, changes in groupby(stream, key=lambda event: event[0]):
        if i == count:
            break
        for _, order, span in changes:
            if span is None:
                del active[order]
                continue
            draw = span.draw
            transforms = (
                (draw.transform,)
                if span.motion is None
                else (draw.transform, span.motion.end.transform)
            )
            clip_motion = (
                -1
                if span.clip_end is None
                else table.add(
                    span.first - origin, span.stop - 1 - origin, *span.clip_end
                )
            )
            batch: dict[int, list[int]] = defaultdict(list)
            clip = frames.leaves[order].node.clip
            edge = clip if isinstance(clip, _FeatheredSingingClip) else None
            variants = [(draw.images, 0)]
            if span.alternate_masks is not None:
                # Select the native border bitmap at playback opacity without
                # sampling an entire fade or exporting a per-frame command list.
                mode = 1 if round((1 - draw.opacity) * 255) == 0 else -1
                variants = [(draw.images, mode), (span.alternate_masks, -mode)]
            for images, mode in variants:
                motion = _motion_record(table, span, fps, origin, mode)
                for image in images:
                    record = _draw_record(table, atlas, draw, image, motion, clip_motion, edge)
                    for tile in _tiles(image, transforms, cols, rows):
                        batch[tile].append(record)
            active[order] = batch
        tiles: dict[int, list[int]] = defaultdict(list)
        for order in sorted(active):
            for tile, draws in active[order].items():
                tiles[tile].extend(draws)
        directory = [-1] * (cols * rows)
        for tile, draws in tiles.items():
            directory[tile] = table.add(len(draws), *draws)
        record = table.add(*directory)
        if i == 0:
            timeline[1] = record
        elif record != timeline[-1]:
            timeline.extend((i, record))
    return table.add(len(timeline) // 2, *timeline)


def export_hook(
    scene: Scene, path: Path, fps: int, start: float, duration: float | None
) -> None:
    if type(fps) is not int or not 1 <= fps <= 240:
        raise ValueError("hook fps must be an integer in 1..240")
    if not isfinite(start) or start < 0 or abs(start * fps - round(start * fps)) > 1e-7:
        raise ValueError("hook start must be nonnegative and frame aligned")
    frames = SceneFrames(scene)
    length = frames.end - start if duration is None else duration
    if not isfinite(length) or not 0 < length * fps <= 250000:
        raise ValueError("hook interval must cover 1..250000 frames")
    count = ceil(length * fps)
    atlas, table = _Atlas(), _Table()
    w, h = frames.resolution
    cols, rows = ceil(w / _TILE), ceil(h / _TILE)
    timeline = _timeline(
        frames, atlas, table, fps, round(start * fps), count, cols, rows
    )
    source = (
        _SHADER.replace("NFRAMES", str(count))
        .replace("TIMELINE", str(timeline))
        .replace("EXPORT_FPS", str(fps))
        .replace("START_FRAME", str(round(start * fps)))
        .replace("CANVAS", f"vec2({w}.,{h}.)")
        .replace("NCOLS", str(cols))
        .replace("TILESIZE", str(_TILE))
        .replace("TEXWIDTH", str(_WIDTH))
    )
    with NamedTemporaryFile(dir=path.parent, delete=False) as out:
        temp = Path(out.name)
        try:
            _texture(out, "KARAMASK", "r8", atlas.data, _WIDTH)
            _texture(out, "KARADATA", "rgba32f", table.values.tobytes(), _WIDTH * 16)
            out.write(source.encode())
            out.close()
            temp.replace(path)
        finally:
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
float weight(int motion, int index) {
    float p=clamp((float(index)-item(motion))/item(motion+1),0.,1.);
    float peak=item(motion+2);
    if(peak>0.) p=clamp(min(p/peak,(1.-p)/(1.-peak)),0.,1.);
    int curve=refAt(motion+3);
    if(curve==0) return p;
    if(curve==1) return p*p*(3.-2.*p);
    if(curve==2) return p*p*p*(p*(6.*p-15.)+10.);
    if(curve>=3) return item(curve-3+index-refAt(motion+5));
    int knots=-1-curve;
    int k=preceding(knots,p);
    if(k+2>=knots+1+2*refAt(knots)) return item(k+1);
    return mix(item(k+1),item(k+3),(p-item(k))/(item(k+2)-item(k)));
}
vec3 paintColor(vec3 solid,int ramp,vec2 screen,vec2 local) {
    int stops=refAt(ramp);
    if(stops<0) return solid;
    vec2 pos=item(ramp+1)>0.?screen:local;
    float t=item(ramp+2)>0.?pos.y:pos.x;
    int end=stops+1+4*refAt(stops);
    for(int k=stops+5;k<end;k+=4) {
        if(t<=item(k)) return mix(rgbAt(k-3),rgbAt(k+1),clamp((t-item(k-4))/(item(k)-item(k-4)),0.,1.));
    }
    return rgbAt(end-3);
}
vec4 hook() {
    vec4 bg=HOOKED_tex(HOOKED_pos);
    // mpv supplies the media timestamp. FFmpeg can leave the parameter at -1.
    int index = PTS >= 0.0
        ? int(floor(PTS * float(EXPORT_FPS) + 0.001)) - START_FRAME
        : frame - 1;
    if(index<0 || index>=NFRAMES) return bg;
    vec2 screen=HOOKED_pos*CANVAS;
    ivec2 tile=ivec2(screen)/TILESIZE;
    int list=refAt(refAt(preceding(TIMELINE,float(index))+1)+tile.y*NCOLS+tile.x);
    if(list<0) return bg;
    int count=refAt(list);
    for(int j=0;j<count;j++) {
        int cmd=refAt(list+1+j), g=refAt(cmd), p=refAt(cmd+1), m=refAt(cmd+2);
        mat2 basis=mat2(pairAt(m),pairAt(m+2));
        vec2 pos=pairAt(m+4);
        float alpha=item(cmd+4);
        int motion=refAt(cmd+5);
        if(motion>=0) {
            float w=weight(motion,index);
            int end=refAt(motion+4);
            basis=mat2(mix(basis[0],pairAt(end),w),mix(basis[1],pairAt(end+2),w));
            pos=mix(pos,pairAt(end+4),w);
            float reveal=item(motion+6)>0. ? clamp(4.*(float(index)-item(motion))/item(motion+1),0.,1.) : w;
            alpha=mix(alpha,item(end+6),reveal);
            int mode=refAt(motion+7);
            if(mode!=0 && (mode>0)!=(alpha>=1.-0.5/255.)) continue;
        }
        if(alpha<=0. || determinant(basis)==0.) continue;
        vec2 local=inverse(basis)*(screen-pos);
        vec2 uv=local-pairAt(g), size=pairAt(g+2);
        if(any(lessThan(uv,vec2(0))) || any(greaterThanEqual(uv,size))) continue;
        float edgeDistance=0.;
        int clip=refAt(cmd+3);
        if(clip>=0) {
            vec2 pos=item(clip+4)>0.?local:screen;
            vec4 rect=vec4(pairAt(clip),pairAt(clip+2));
            int sweep=refAt(cmd+6);
            if(sweep>=0) {
                float t=(float(index)-item(sweep))/(item(sweep+1)-item(sweep));
                rect=mix(rect,vec4(pairAt(sweep+2),pairAt(sweep+4)),t);
            }
            edgeDistance=min(pos.x-rect.x,rect.z-pos.x);
            if(any(lessThan(pos,rect.xy)) || any(greaterThanEqual(pos,rect.zw))) continue;
        }
        vec2 mask=pairAt(g+4)+clamp(uv,vec2(0.5),size-0.5);
        float a=textureLod(KARAMASK,mask/vec2(textureSize(KARAMASK,0)),0.).r*item(p+3)*alpha;
        vec3 ink=paintColor(rgbAt(p),p+4,screen,local);
        int feather=refAt(p+7);
        if(feather>=0) {
            float phase=edgeDistance/item(feather+3);
            if(phase<1.) {
                vec3 before=paintColor(rgbAt(feather),feather+5,screen,local);
                ink=mix(before,ink,smoothstep(0.,1.,phase));
                int core=refAt(feather+4);
                if(core>=0) {
                    float strength=smoothstep(0.,0.16,phase)*(1.-smoothstep(0.42,0.78,phase));
                    ink=mix(ink,rgbAt(core),strength);
                }
            }
        }
        bg.rgb=mix(bg.rgb,ink,a);
        bg.a=a+bg.a*(1.-a);
    }
    return bg;
}
"""
