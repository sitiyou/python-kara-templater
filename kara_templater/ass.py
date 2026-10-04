from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


class Record(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as error:
            raise AttributeError(name) from error

    def __setattr__(self, name, value):
        self[name] = value


STYLE_FORMAT = "Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding"
EVENT_FORMAT = "Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"
STYLE_NAMES = {
    "fontname": "fontname",
    "fontsize": "fontsize",
    "scalex": "scale_x",
    "scaley": "scale_y",
    "alignment": "align",
    "marginl": "margin_l",
    "marginr": "margin_r",
    "marginv": "margin_v",
}
EVENT_NAMES = {
    "start": "start_time",
    "end": "end_time",
    "name": "actor",
    "marginl": "margin_l",
    "marginr": "margin_r",
    "marginv": "margin_v",
}


def parse_time(value: str) -> int:
    match = re.fullmatch(r"(\d+):(\d{2}):(\d{2})[.](\d{2})", value.strip())
    if not match:
        raise ValueError(f"Invalid ASS timestamp: {value!r}")
    h, m, s, cs = map(int, match.groups())
    if m >= 60 or s >= 60:
        raise ValueError(f"Invalid ASS timestamp: {value!r}")
    return ((h * 60 + m) * 60 + s) * 1000 + cs * 10


def format_time(value: float) -> str:
    cs = max(0, int(value) // 10)
    minutes, cs = divmod(cs, 6000)
    h, m = divmod(minutes, 60)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02}:{s:02}.{cs:02}"


@dataclass
class Style:
    name: str = "Default"
    fontname: str = "Arial"
    fontsize: float = 20
    bold: bool = False
    italic: bool = False
    scale_x: float = 100
    scale_y: float = 100
    spacing: float = 0
    encoding: int = 1
    align: int = 2
    margin_l: int = 10
    margin_r: int = 10
    margin_v: int = 10
    outline: float = 2
    shadow: float = 2
    fields: dict[str, str] = field(default_factory=dict, repr=False)

    @property
    def margin_t(self):
        return self.margin_v

    @property
    def margin_b(self):
        return self.margin_v

    def serialize(self):
        defaults = dict(
            zip(
                STYLE_FORMAT.split(", "),
                [
                    "Default",
                    "Arial",
                    "20",
                    "&H00FFFFFF",
                    "&H000000FF",
                    "&H00000000",
                    "&H00000000",
                    "0",
                    "0",
                    "0",
                    "0",
                    "100",
                    "100",
                    "0",
                    "0",
                    "1",
                    "2",
                    "2",
                    "2",
                    "10",
                    "10",
                    "10",
                    "1",
                ],
            )
        )
        values = self.fields or defaults
        result = []
        for key, value in values.items():
            attr = STYLE_NAMES.get(key.lower(), key.lower())
            if hasattr(self, attr):
                value = getattr(self, attr)
                value = -int(value) if isinstance(value, bool) else number(value)
            result.append(str(value))
        return "Style: " + ",".join(result)


@dataclass
class Line:
    text: str = ""
    start_time: float = 0
    end_time: float = 0
    style: str = "Default"
    actor: str = ""
    layer: int = 0
    margin_l: int = 0
    margin_r: int = 0
    margin_v: int = 0
    effect: str = ""
    comment: bool = False
    fields: dict[str, str] = field(default_factory=dict, repr=False)

    @property
    def margin_t(self):
        return self.margin_v

    @property
    def margin_b(self):
        return self.margin_v

    def serialize(self):
        values = self.fields or dict.fromkeys(EVENT_FORMAT.split(", "), "")
        result = []
        for key, value in values.items():
            attr = EVENT_NAMES.get(key.lower(), key.lower())
            if hasattr(self, attr):
                value = getattr(self, attr)
                value = format_time(value) if attr in {"start_time", "end_time"} else number(value)
            result.append(str(value))
        return ("Comment: " if self.comment else "Dialogue: ") + ",".join(result)


def number(value):
    return int(value) if isinstance(value, float) and value.is_integer() else value


def _parse_record(cls, text, columns, names):
    values = text.split(",", len(columns) - 1)
    if len(values) != len(columns):
        raise ValueError(f"Expected {len(columns)} fields: {text!r}")
    fields = dict(zip(columns, values))
    obj = cls(fields=fields)
    for key, value in fields.items():
        attr = names.get(key.lower(), key.lower())
        if attr not in cls.__dataclass_fields__ or attr == "fields":
            continue
        value_type = cls.__dataclass_fields__[attr].type
        current = getattr(obj, attr)
        if attr in {"start_time", "end_time"}:
            value = parse_time(value)
        elif isinstance(current, bool):
            value = bool(int(value))
        elif value_type == "float":
            value = float(value)
        elif value_type == "int":
            value = int(value)
        elif attr != "text":
            value = value.strip()
        setattr(obj, attr, value)
    return obj


@dataclass
class Document:
    records: list[str | Style | Line]
    meta: Record

    @classmethod
    def parse(cls, text: str) -> Document:
        records = []
        meta = Record()
        section = ""
        columns = []
        for raw in text.lstrip("\ufeff").splitlines():
            stripped = raw.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                section = stripped.lower()
                columns = []
            key, sep, value = raw.partition(":")
            kind = key.strip().lower()
            if section == "[v4 styles]" and kind == "format":
                raise ValueError("SSA styles are not supported; use ASS v4.00+")
            if kind == "format" and section in {"[v4+ styles]", "[events]"}:
                columns = [x.strip() for x in value.split(",")]
                if section == "[events]" and (not columns or columns[-1].lower() != "text"):
                    raise ValueError("ASS event Text must be the final field")
            if section == "[script info]" and sep and not kind.startswith(";"):
                meta[kind] = value.strip()
            if section == "[v4+ styles]" and kind == "style":
                if not columns:
                    raise ValueError("Missing style Format")
                records.append(_parse_record(Style, value.lstrip(), columns, STYLE_NAMES))
            elif section == "[events]" and kind in {"dialogue", "comment"}:
                if not columns:
                    raise ValueError("Missing event Format")
                line = _parse_record(Line, value.lstrip(), columns, EVENT_NAMES)
                line.comment = kind == "comment"
                records.append(line)
            else:
                records.append(raw)
        x, y = int(meta.get("playresx", 0)), int(meta.get("playresy", 0))
        if not x and not y:
            x, y = 384, 288
        elif not x:
            x = 1280 if y == 1024 else y * 4 // 3
        elif not y:
            y = 1024 if x == 1280 else x * 3 // 4
        meta.res_x, meta.res_y = x, y
        meta.video_x_correct_factor = 1.0
        return cls(records, meta)

    @classmethod
    def load(cls, path: str | Path) -> Document:
        return cls.parse(Path(path).read_text(encoding="utf-8-sig"))

    @property
    def styles(self):
        return {x.name: x for x in self.records if isinstance(x, Style)}

    @property
    def lines(self):
        return [x for x in self.records if isinstance(x, Line)]

    def dumps(self):
        return "\n".join(x if isinstance(x, str) else x.serialize() for x in self.records) + "\n"

    def save(self, path: str | Path):
        Path(path).write_text(self.dumps(), encoding="utf-8-sig")
