"""Explicit v0.1.0 Python-template compatibility frontend."""

from __future__ import annotations

import math
import random
import re
from collections.abc import Callable, Iterator, Sequence
from copy import copy, deepcopy
from dataclasses import dataclass, field
from typing import cast
from urllib.parse import quote

from ._legacy_layout import LegacyLine, LegacySyllable, preprocess
from .ass import Document, Line, Record, Style, number
from .layout import text_extents
from .scene import NativeEvent, Scene
from .scene_output import SceneBudget
from .sources import EventOrigin, SourceRef


class TemplateError(ValueError):
    pass


MODIFIERS = {
    "once",
    "pre-line",
    "line",
    "syl",
    "furi",
    "char",
    "all",
    "repeat",
    "loop",
    "notext",
    "keeptags",
    "noblank",
    "multi",
    "fx",
    "fxgroup",
}


@dataclass
class Template:
    source: Line
    index: int
    modes: list[str] = field(default_factory=list)
    text: str = ""
    pre: str = ""
    code: bool = False
    style: str | None = None
    loops: int = 1
    addtext: bool = True
    keeptags: bool = False
    noblank: bool = False
    multi: bool = False
    perchar: bool = False
    fx: str | None = None
    fxgroup: str | None = None

    def error(self, message: str) -> TemplateError:
        return TemplateError(f"Event {self.index} ({self.source.effect}): {message}")


def parse_templates(lines: Sequence[Line]) -> list[Template]:
    templates: list[Template] = []
    named: dict[str, Template] = {}
    for index, line in enumerate(lines, 1):
        tokens = line.effect.split()
        if (
            not line.comment
            or not tokens
            or tokens[0].lower() not in {"template", "code"}
        ):
            continue
        t = Template(line, index, code=tokens[0].lower() == "code", style=line.style)
        identifier = None
        pre = False
        changes = set()
        i = 1
        while i < len(tokens):
            modifier = tokens[i].lower()
            i += 1
            if modifier in {"once", "line", "pre-line", "syl", "furi"}:
                if modifier == "once" and not t.code:
                    raise t.error("once is only valid for code")
                if modifier == "pre-line" and t.code:
                    raise t.error("pre-line is only valid for text templates")
                mode = "line" if modifier == "pre-line" else modifier
                t.modes.append(mode)
                pre = modifier == "pre-line"
                if (
                    mode == "line"
                    and not t.code
                    and i < len(tokens)
                    and tokens[i].lower() not in MODIFIERS
                ):
                    identifier = tokens[i].lower()
                    i += 1
            elif modifier in {"repeat", "loop", "fx", "fxgroup"}:
                if i >= len(tokens):
                    raise t.error(f"Missing value for {modifier}")
                value = tokens[i]
                i += 1
                if modifier in {"repeat", "loop"}:
                    changes.add("loops")
                    try:
                        t.loops = int(value)
                    except ValueError as error:
                        raise t.error("Loop count must be an integer") from error
                    if t.loops < 0:
                        raise t.error("Loop count cannot be negative")
                else:
                    changes.add(modifier)
                    setattr(t, modifier, value)
            elif modifier == "all":
                changes.add("style")
                t.style = None
            elif modifier == "notext":
                changes.add("addtext")
                t.addtext = False
            elif modifier == "char":
                changes.add("perchar")
                t.perchar = True
            elif modifier in {"keeptags", "noblank", "multi"}:
                changes.add(modifier)
                setattr(t, modifier, True)
            else:
                raise t.error(f"Unknown modifier: {modifier}")
        t.modes = list(dict.fromkeys(t.modes or (["once"] if t.code else ["syl"])))
        if "line" in t.modes and len(t.modes) > 1 and not t.code:
            raise t.error(
                "Line templates cannot be combined with syllable/furigana templates"
            )
        if pre:
            t.pre = line.text
        else:
            t.text = line.text
        if identifier in named:
            existing = named[identifier]
            existing.pre += t.pre
            existing.text += t.text
            for attr in changes:
                setattr(existing, attr, getattr(t, attr))
        else:
            templates.append(t)
            if identifier:
                named[identifier] = t
    return templates


def _round(value: float) -> int:
    return math.floor(value + 0.5)


def _line_context(line: LegacyLine) -> _Context:
    ctx = _Context(
        layer=line.layer,
        style=line.style,
        actor=line.actor,
        li=line.i,
        syln=len(line.kara) - 1,
        lstart=line.start_time,
        lend=line.end_time,
        ldur=line.duration,
        lmid=line.start_time + line.duration / 2,
    )
    for attr in (
        "left",
        "center",
        "right",
        "width",
        "top",
        "middle",
        "bottom",
        "height",
        "x",
        "y",
    ):
        ctx["l" + attr] = _round(getattr(line, attr))
        ctx[attr] = ctx["l" + attr]
    for side in ("l", "r", "v", "t", "b"):
        ctx["margin_" + side] = getattr(line, "eff_margin_" + side)
    ctx.update(
        start=ctx.lstart,
        end=ctx.lend,
        dur=ctx.ldur,
        mid=ctx.lmid,
        kdur=math.floor(ctx.ldur / 10),
        i=line.i,
    )
    return ctx


def _syl_context(line: LegacyLine, syl: LegacySyllable) -> _Context:
    ctx = _line_context(line)
    ctx.update(
        sstart=syl.start_time,
        send=syl.end_time,
        sdur=syl.duration,
        skdur=syl.duration / 10,
        smid=syl.start_time + syl.duration / 2,
        si=syl.i,
    )
    for short, source in {
        "start": "sstart",
        "end": "send",
        "dur": "sdur",
        "kdur": "skdur",
        "mid": "smid",
        "i": "si",
    }.items():
        ctx[short] = ctx[source]
    for attr in ("left", "center", "right"):
        ctx["s" + attr] = _round(line.left + _coordinate(syl, attr))
    ctx.swidth = _round(syl.width)
    ctx.sheight = syl.height
    ctx.stop = _round(ctx.ltop - syl.height) if syl.isfuri else ctx.ltop
    ctx.smiddle = _round(ctx.ltop - syl.height / 2) if syl.isfuri else ctx.lmiddle
    ctx.sbottom = ctx.ltop if syl.isfuri else ctx.lbottom
    ctx.sx = ctx["s" + line.halign]
    ctx.sy = ctx["s" + line.valign]
    for attr in (
        "left",
        "center",
        "right",
        "width",
        "top",
        "middle",
        "bottom",
        "height",
        "x",
        "y",
    ):
        ctx[attr] = ctx["s" + attr]
    return ctx


def _expression_end(text: str, start: int) -> int:
    quote = None
    i = start
    while i < len(text):
        char = text[i]
        if quote:
            if char == "\\":
                i += 2
                continue
            if text.startswith(quote, i):
                i += len(quote)
                quote = None
                continue
        elif char in {"'", '"'}:
            quote = char * 3 if text.startswith(char * 3, i) else char
            i += len(quote)
            continue
        elif char == "!" and not text.startswith("!=", i):
            return i
        i += 1
    raise TemplateError("Unclosed !expression!")


class _Context(Record):
    lstart: float
    lend: float
    ldur: float
    lmid: float
    ltop: float
    lmiddle: float
    lbottom: float
    swidth: float
    sheight: float
    stop: float
    smiddle: float
    sbottom: float


def _coordinate(value: LegacyLine | LegacySyllable, name: str) -> float:
    result: object = getattr(value, name)
    if not isinstance(result, (int, float)):
        raise TemplateError(f"expected numeric coordinate {name}")
    return result


type _Decorator = Callable[[str], object] | str | None


class Engine:
    def __init__(
        self,
        *,
        max_iterations: int = 10000,
        max_output_lines: int = 100000,
        video_size: tuple[int, int] | None = None,
        owner: str = "legacy-templates",
        budget: SceneBudget | None = None,
    ) -> None:
        if any(type(n) is not int or n < 1 for n in (max_iterations, max_output_lines)):
            raise ValueError("template limits must be positive integers")
        self.owner = owner
        self.budget = budget
        self.env: dict[str, object] = {}
        self.memory: dict[object, object] = {}
        self.scopes: dict[object, _Decorator] = {}
        self.generated: list[LegacyLine] = []
        self.origins: list[EventOrigin] = []
        self._source_index = 0
        self.max_iterations = max_iterations
        self.max_output_lines = max_output_lines
        self.video_size = video_size

    def apply(self, document: Document) -> Document:
        return self.to_scene(document).compile(budget=self.budget).document

    def to_scene(self, document: Document) -> Scene:
        """Execute trusted legacy templates explicitly and return a composable scene."""
        result = deepcopy(document)
        source_records = {
            id(record): index for index, record in enumerate(result.records)
        }
        prefix = "kara:scene:v1:" + quote(self.owner, safe="") + ":"
        result.records = [
            x
            for x in result.records
            if not isinstance(x, Line)
            or (not x.effect.startswith(prefix) and (x.comment or x.effect != "fx"))
        ]
        templates = parse_templates(result.lines)
        styles = result.styles
        if not styles:
            raise TemplateError("No ASS styles found")
        if self.video_size:
            w, h = self.video_size
            if w <= 0 or h <= 0:
                raise ValueError("Video dimensions must be positive")
            result.meta.video_x_correct_factor = (h / w) / (
                result.meta.res_y / result.meta.res_x
            )
        self.env = {
            "math": math,
            "random": random,
            "meta": result.meta,
            "styles": styles,
            "text_extents": text_extents,
            "fxgroup": {},
            "line": None,
            "orgline": None,
            "syl": None,
            "basesyl": None,
        }
        self.env["tenv"] = self.env
        self.memory, self.scopes = {}, {}
        self.generated = []
        self.origins = []
        self._install_helpers(styles)
        for t in templates:
            if "once" in t.modes:
                self._run_code(t)
        for index, line in enumerate(result.lines, 1):
            # New frontends own their generated events and source markers.
            if line.effect.startswith(("karaoke:v1:", "kara:scene:v1:")):
                continue
            if not (
                (not line.comment and line.effect == "")
                or re.search(r"[Kk]araoke", line.effect)
            ):
                continue
            line = preprocess(line, styles, result.meta)
            line.i = index
            self._source_index = source_records[id(line)]
            self.env.update(orgline=line, line=None, syl=None, basesyl=None)
            before = len(self.generated)
            for t in templates:
                if "line" in t.modes and self._matches(t, line):
                    if t.code:
                        self.env["line"] = line
                        self._run_code(t)
                    else:
                        self._run_line(t, line)
            for mode, units in (("syl", line.kara), ("furi", line.furi)):
                for syl in units:
                    for t in templates:
                        if mode in t.modes and self._matches(t, line):
                            self.env.update(syl=syl, basesyl=syl)
                            self._run_syl(t, line, syl)
            if len(self.generated) > before:
                line.comment = True
                line.effect = "karaoke"
        added_styles = [s for name, s in styles.items() if name not in result.styles]
        if added_styles:
            pos = (
                max(
                    i
                    for i, x in enumerate(result.records)
                    if not isinstance(x, str) and not isinstance(x, Line)
                )
                + 1
            )
            result.records[pos:pos] = added_styles
        scene = Scene(result, owner=self.owner)
        for index, (event, origin) in enumerate(
            zip(self.generated, self.origins, strict=True)
        ):
            scene.add(NativeEvent(f"template:{index}", event, origin))
        return scene

    def _matches(self, t: Template, line: LegacyLine) -> bool:
        return (t.style is None or t.style == line.style) and (
            not t.fxgroup or self._groups().get(t.fxgroup) is not False
        )

    def _loops(self, t: Template) -> Iterator[int | float]:
        self.env.update(j=0, maxj=t.loops)
        iterations = 0
        while self._counter("j") < self._counter("maxj"):
            iterations += 1
            if iterations > self.max_iterations:
                raise t.error("Iteration limit exceeded")
            self.env["j"] = self._counter("j") + 1
            yield self._counter("j")

    def _run_code(self, t: Template) -> None:
        try:
            code = compile(t.text, f"<ASS code event {t.index}>", "exec")
            for _ in self._loops(t):
                exec(code, self.env)
        except Exception as error:
            raise t.error(f"{type(error).__name__}: {error}") from error

    def _render(self, text: str, t: Template, context: _Context) -> str:
        def variable(match: re.Match[str]) -> str:
            name = match[1].lower()
            if name not in context:
                raise t.error(f"Unknown variable: ${name}")
            return str(number(context[name]))

        text = re.sub(r"\$([a-zA-Z_]+)", variable, text)
        chunks: list[str] = []
        start = 0
        try:
            while True:
                opening = text.find("!", start)
                if opening < 0:
                    chunks.append(text[start:])
                    break
                closing = _expression_end(text, opening + 1)
                chunks.append(text[start:opening])
                value: object = eval(text[opening + 1 : closing], self.env)
                chunks.append("" if value is None else str(number(value)))
                start = closing + 1
        except Exception as error:
            raise t.error(f"{type(error).__name__}: {error}") from error
        return "".join(chunks)

    def _emit(self, line: LegacyLine, t: Template) -> None:
        if len(self.generated) >= self.max_output_lines:
            raise t.error("Output line limit exceeded")
        line.comment = False
        line.effect = "fx"
        self.generated.append(line)
        self.origins.append(
            EventOrigin(
                (SourceRef(f"record:{self._source_index}"),),
                f"template:event:{t.index}",
            )
        )

    def _run_line(self, t: Template, original: LegacyLine) -> None:
        for _ in self._loops(t):
            line = copy(original)
            line.layer = t.source.layer
            self.env.update(line=line, syl=None, basesyl=None)
            text = self._render(t.pre, t, _line_context(original))
            if t.text:
                for syl in original.kara[1:]:
                    self.env.update(syl=syl, basesyl=syl)
                    text += self._render(t.text, t, _syl_context(original, syl))
                    if t.addtext:
                        text += syl.text if t.keeptags else syl.text_stripped
            else:
                text += original.text if t.keeptags else original.text_stripped
            line.text = text
            self._emit(line, t)

    def _run_syl(self, t: Template, original: LegacyLine, base: LegacySyllable) -> None:
        if (t.fx is not None and t.fx != base.inline_fx) or (
            t.noblank
            and (base.duration <= 0 or not base.text_stripped.strip(" \t\r\n\u3000"))
        ):
            return
        units = [base]
        if t.perchar:
            units = []
            left = base.left
            for char in base.text_stripped:
                unit = LegacySyllable(base)
                unit.update(
                    text=char,
                    text_stripped=char,
                    text_spacestripped=char,
                    prespace="",
                    postspace="",
                    prespacewidth=0,
                    postspacewidth=0,
                )
                unit.width = (
                    text_extents(base.style, char)[0]
                    * self._meta().video_x_correct_factor
                )
                unit.left, unit.center, unit.right = (
                    left,
                    left + unit.width / 2,
                    left + unit.width,
                )
                left = unit.right
                units.append(unit)
        for unit in units:
            highlights = unit.highlights if t.multi else [None]
            for hl in highlights:
                syl = unit if hl is None else LegacySyllable(unit)
                if hl is not None:
                    syl.update(hl)
                    syl.kdur = syl.duration / 10
                if t.noblank and (
                    syl.duration <= 0 or not syl.text_stripped.strip(" \t\r\n\u3000")
                ):
                    continue
                self.env["syl"] = syl
                if t.code:
                    self.env["line"] = original
                    self._run_code(t)
                else:
                    for _ in self._loops(t):
                        line = copy(original)
                        line.layer = t.source.layer
                        line.style, line.styleref = syl.style.name, syl.style
                        self.env["line"] = line
                        line.text = self._render(t.text, t, _syl_context(original, syl))
                        if t.keeptags:
                            line.text += syl.text
                        elif t.addtext:
                            line.text += syl.text_stripped
                        self._emit(line, t)

    def _counter(self, key: str) -> int | float:
        value = self.env[key]
        if not isinstance(value, (int, float)):
            raise TemplateError(f"{key} must be numeric")
        return value

    def _groups(self) -> dict[str, object]:
        value = self.env["fxgroup"]
        if not isinstance(value, dict):
            raise TemplateError("fxgroup must be a dictionary")
        return cast(dict[str, object], value)

    def _meta(self) -> Record:
        value = self.env["meta"]
        if not isinstance(value, Record):
            raise TemplateError("meta must be a Record")
        return value

    def _line(self) -> LegacyLine | None:
        value = self.env["line"]
        if value is None or isinstance(value, LegacyLine):
            return value
        raise TemplateError("line must be a preprocessed Line")

    def _require_line(self) -> LegacyLine:
        value = self._line()
        if value is None:
            raise TemplateError("helper requires a current line")
        return value

    def _syllable(self) -> LegacySyllable | None:
        value = self.env["syl"]
        if value is None or isinstance(value, LegacySyllable):
            return value
        raise TemplateError("syl must be a preprocessed syllable")

    def _install_helpers(self, styles: dict[str, Style]) -> None:
        def retime(mode: str, addstart: float = 0, addend: float = 0) -> str:
            line, syl = self._line(), self._syllable()
            if line is None:
                raise TemplateError("retime requires a current line")
            a, b = line.start_time, line.end_time
            if mode in {"set", "abs"}:
                a, b = 0, 0
            elif mode == "preline":
                b = a
            elif mode == "postline":
                a = b
            elif mode != "line":
                if syl is None:
                    raise TemplateError(f"retime({mode!r}) requires a syllable")
                start, end = a + syl.start_time, a + syl.end_time
                if mode == "syl":
                    a, b = start, end
                elif mode == "presyl":
                    a, b = start, start
                elif mode == "postsyl":
                    a, b = end, end
                elif mode == "start2syl":
                    b = start
                elif mode == "syl2end":
                    a = end
                elif mode == "sylpct":
                    a, b = start, start
                    addstart *= syl.duration / 100
                    addend *= syl.duration / 100
                else:
                    raise TemplateError(f"Unknown retime mode: {mode}")
            line.start_time, line.end_time = a + addstart, b + addend
            line.duration = line.end_time - line.start_time
            return ""

        def relayer(layer: int | float) -> str:
            self._require_line().layer = int(layer)
            return ""

        def restyle(style: str) -> str:
            self._require_line().styleref = styles[style]
            self._require_line().style = style
            return ""

        def maxloop(count: int | float) -> str:
            self.env["maxj"] = int(count)
            return ""

        def loopctl(j: int | float, count: int | float) -> str:
            self.env["j"], self.env["maxj"] = int(j), int(count)
            return ""

        def memory_key(name: object, decorator: _Decorator) -> object:
            if callable(decorator):
                return decorator(str(name))
            if isinstance(decorator, str):
                return decorator, id(self.env[decorator]), name
            return name

        def remember(
            name: object, value: object, decorator: _Decorator = None
        ) -> object:
            self.scopes[name] = decorator
            self.memory[memory_key(name, decorator)] = value
            return value

        def recall(name: object, default: object = None) -> object:
            return self.memory.get(memory_key(name, self.scopes.get(name)), default)

        def remember_if(
            name: object, value: object, condition: object, decorator: _Decorator = None
        ) -> object:
            return remember(name, value, decorator) if condition else value

        self.env.update(
            retime=retime,
            relayer=relayer,
            restyle=restyle,
            maxloop=maxloop,
            maxloops=maxloop,
            loopctl=loopctl,
            remember=remember,
            recall=recall,
            remember_if=remember_if,
            remember_line=lambda name, value: remember(name, value, "orgline"),
            remember_syl=lambda name, value: remember(name, value, "syl"),
            remember_basesyl=lambda name, value: remember(name, value, "basesyl"),
        )


def apply_templates(
    document: Document,
    *,
    max_iterations: int = 10000,
    max_output_lines: int = 100000,
    video_size: tuple[int, int] | None = None,
    owner: str = "legacy-templates",
    budget: SceneBudget | None = None,
) -> Document:
    """Apply trusted v0.1.0 Python templates through the shared ASS compiler."""
    return Engine(
        max_iterations=max_iterations,
        max_output_lines=max_output_lines,
        video_size=video_size,
        owner=owner,
        budget=budget,
    ).apply(document)
