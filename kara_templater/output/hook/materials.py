"""Compile WGSL paint functions and serialize their per-plane invocations."""

from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
from math import ceil
from pathlib import Path
from subprocess import run
from sys import platform

from ...composition import Color
from ...geometry import Vec2, finite
from ...lyrics.materials import _SweepBlend
from ...paint_fields import PaintInput, PaintValue, _PaintTrack
from .draws import DrawCommand

_CONTEXT = """struct KaraPaintContext {
    local: vec2<f32>,
    screen: vec2<f32>,
    coverage: f32,
    time: f32,
    progress: f32,
    component: i32,
}
"""

_APPLY = """void applyMaterials(int list,vec2 local,vec2 screen,float coverage,int index,int component,
                    inout vec3 ink,inout float alpha) {
    if(list<0) return;
    vec4 material=vec4(ink,alpha);
    int count=refAt(list), end=list+1+count;
    for(int i=list+1;i<end;i++) {
        int effect=refAt(i);
        if(index<refAt(effect+1) || index>=refAt(effect+2)) continue;
        float t=(float(index)-item(effect+3))/item(0);
        float progress=clamp(t/item(effect+4),0.,1.);
        int data=refAt(effect+5);
        switch(refAt(effect)) {
MATERIAL_CASES
        }
    }
    ink=material.rgb;
    alpha=material.a;
}
"""

_TRACK = """float paintTrack(int track,float time) {
    int k=preceding(track,time);
    float a=item(k+1);
    if(k+2>=track+1+2*refAt(track) || time<=item(k)) return a;
    return mix(a,item(k+3),clamp((time-item(k))/(item(k+2)-item(k)),0.,1.));
}
"""


@dataclass(frozen=True)
class _Program:
    namespace: str
    glsl: str


@lru_cache(maxsize=128)
def _compile(source: str, entry: str, types: tuple[str, ...]) -> _Program:
    if not entry or not entry.isascii() or not entry.isidentifier():
        raise ValueError("material entry point requires an ASCII identifier")
    namespace = "kara_effect_" + sha256(repr((source, entry, types)).encode()).hexdigest()[:24]
    signature = "".join(f", p{i}: {kind}" for i, kind in enumerate(types))
    arguments = "".join(f", p{i}" for i in range(len(types)))
    dummy = "".join(f", {kind}(0.0)" for kind in types)
    module = f"""{_CONTEXT}
{source}
fn kara_compile_paint(material: vec4<f32>, context: KaraPaintContext{signature}) -> vec4<f32> {{
    return {entry}(material, context{arguments});
}}
@fragment fn kara_compile_fragment() -> @location(0) vec4<f32> {{
    return kara_compile_paint(vec4<f32>(0.), KaraPaintContext(vec2<f32>(0.),vec2<f32>(0.),0.,0.,0.,0){dummy});
}}
"""
    filename = "_kara_wgsl.exe" if platform == "win32" else "_kara_wgsl"
    compiler = Path(__file__).resolve().parents[2] / filename
    try:
        result = run([str(compiler), namespace], input=module, capture_output=True, text=True,
                     encoding="utf-8", check=False)
    except OSError as error:
        raise ValueError("cannot launch the bundled WGSL compiler; rebuild the installed package") from error
    if result.returncode:
        raise ValueError(result.stderr.strip())
    return _Program(namespace, result.stdout)


def _value(value: PaintValue) -> tuple[str, str, tuple[float, ...]]:
    if isinstance(value, Color):
        return "color", "vec3", (value.red / 255, value.green / 255, value.blue / 255)
    if isinstance(value, Vec2):
        if max(abs(value.x), abs(value.y)) > 3.4028234663852886e38:
            raise ValueError("material coordinates must fit in f32")
        return "vec2", "vec2", (value.x, value.y)
    if isinstance(value, (float, int)) and not isinstance(value, bool):
        finite(value)
        if abs(value) > 3.4028234663852886e38:
            raise ValueError("material scalar must fit in f32")
        return "float", "float", (value,)
    raise ValueError("material parameters must be finite floats, colors or vectors")


@dataclass(frozen=True)
class _Input:
    kind: str
    symbols: tuple[str, ...]
    values: tuple[float, ...]


class MaterialPrograms:
    def __init__(self) -> None:
        self._functions: dict[str, str] = {}
        self._cases: dict[str, int] = {}
        self._inputs: dict[str, _Input] = {}
        self._tracks = False

    def sweep(self) -> str:
        program = _compile(_SweepBlend.wgsl, _SweepBlend.entry_point, ("vec3<f32>", "f32", "vec3<f32>", "f32"))
        namespace = program.namespace
        return program.glsl + f"""
vec3 paintSweep(vec3 ink,vec3 waiting,float phase,int core) {{
    {namespace}_KaraPaintContext context={namespace}_KaraPaintContext(vec2(0.),vec2(0.),0.,0.,0.,0);
    return {namespace}_kara_compile_paint(vec4(ink,1.),context,waiting,phase,
                                          core>=0 ? rgbAt(core) : ink,float(core>=0)).rgb;
}}
"""

    def record(self, draw: DrawCommand, component: int, add: Callable[..., int],
               fps: float, origin: float, count: float) -> int:
        records: list[int] = []
        for clip in draw.material_effects:
            targets = {"fill": 0, "outline": 1, "shadow": 2, "all": component}
            if targets[clip.target] != component:
                continue
            start = draw.time_origin + clip.start
            stop = draw.time_end if clip.duration is None else start + clip.duration
            first = ceil(round(start * fps, 9)) - origin
            end = ceil(round(stop * fps, 9)) - origin
            if max(first, 0) >= min(end, count):
                continue
            arguments: list[str] = []
            values: list[float] = []
            types: list[str] = []
            for argument in clip.effect._arguments():
                if isinstance(argument, _PaintTrack):
                    types.append("f32")
                    arguments.append(f"paintTrack(refAt(data+{len(values)}),float(index))")
                    values.append(add(len(argument.keys), *(
                        field for time, value in argument.keys
                        for field in ((draw.time_origin + time) * fps - origin, value)
                    )))
                    self._tracks = True
                    continue
                named = isinstance(argument, PaintInput)
                kind, glsl, numbers = _value(argument.value if named else argument)
                types.append("f32" if glsl == "float" else f"{glsl}<f32>")
                if named:
                    prefix = "kara_input_" + sha256(argument.name.encode()).hexdigest()[:24]
                    symbols = tuple(f"{prefix}_{i}" for i in range(len(numbers)))
                    slot = _Input(kind, symbols, numbers)
                    if self._inputs.setdefault(argument.name, slot) != slot:
                        raise ValueError(f"paint input {argument.name!r} has conflicting types or values")
                    parts = symbols
                else:
                    parts = tuple(f"item(data+{len(values) + i})" for i in range(len(numbers)))
                    values.extend(numbers)
                arguments.append(parts[0] if glsl == "float" else f"{glsl}({','.join(parts)})")
            try:
                program = _compile(clip.effect.wgsl, clip.effect.entry_point, tuple(types))
            except ValueError as error:
                raise ValueError(f"{type(clip.effect).__name__}: {error}") from error
            ns = program.namespace
            self._functions[ns] = program.glsl
            context = f"{ns}_KaraPaintContext(local,screen,coverage,t,progress,component)"
            code = f"material={ns}_kara_compile_paint({','.join(('material', context, *arguments))});"
            index = self._cases.setdefault(code, len(self._cases))
            data = add(*values) if values else -1
            records.append(add(index, first, end, start * fps - origin, stop - start, data))
        return add(len(records), *records) if records else -1

    @property
    def source(self) -> str:
        if not self._cases:
            return ""
        cases = "\n".join(f"            case {index}: {code} break;" for code, index in self._cases.items())
        return "\n".join((*self._functions.values(), _TRACK if self._tracks else "", _APPLY.replace("MATERIAL_CASES", cases)))

    def parameters(self) -> dict[str, dict[str, str | tuple[str, ...] | tuple[float, ...]]]:
        return {name: {"kind": slot.kind, "uniforms": slot.symbols, "default": slot.values}
                for name, slot in self._inputs.items()}

    def hook_parameters(self) -> str:
        return "".join(
            f"//!PARAM {symbol}\n//!TYPE DYNAMIC float\n{value:.9g}\n\n"
            for slot in self._inputs.values()
            for symbol, value in zip(slot.symbols, slot.values, strict=True)
        )
