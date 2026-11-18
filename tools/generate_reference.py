"""Generate the complete public API reference as deterministic GitHub Markdown.

python -m tools.generate_reference
python -m tools.generate_reference --check
The library must be installed/built so its public types can be inspected.
"""

import argparse
import ast
import inspect
import re
import sys
from collections.abc import Callable, Mapping
from dataclasses import MISSING, fields, is_dataclass
from enum import Enum
from functools import cached_property
from pathlib import Path
from types import UnionType
from typing import (
    Literal,
    TypeAliasType,
    Union,
    cast,
    get_args,
    get_origin,
    get_overloads,
    get_type_hints,
    is_typeddict,
)

import kara_templater as api

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = Path(api.__file__).resolve().parent
PUBLIC = frozenset(api.__all__)
GROUPS: dict[str, tuple[str, tuple[str, ...], str]] = {
    "documents": (
        "Documents and lyric input",
        ("ass", "document_text", "document_lyrics", "import_ass", "sources"),
        "Records, decoded text, input selection, and source mappings. Raw Line clocks use milliseconds; Document lyric singing spans and Track authoring use seconds. See [Documents](../guides/documents.md).",
    ),
    "scenes": (
        "Scenes and compilation",
        ("scene", "scene_output", "scene_evaluation", "gpu_render"),
        "Scene lifetimes and evaluation use seconds; geometry uses script pixels. Compile returns a new Document under explicit resource limits. See [objects](../guides/objects.md) and [compilation](../guides/compilation.md).",
    ),
    "animation": (
        "Animation and timing",
        ("scene_animation", "easing"),
        "Pure state/property animation and typed composition. Scene, semantic lyric rules, and animation sequences use seconds. See the [time-unit table](../guides/animation.md).",
    ),
    "tracks": (
        "Track authoring",
        ("karaoke", "orchestration", "lyric_layout", "lyric_line", "lyric_effects", "karaoke_effects"),
        "Independent lyric streams, allocation and semantic bindings into one Scene. Singing, display and animation clocks use seconds and stay separate. See [Tracks](../guides/tracks.md).",
    ),
    "text": (
        "Text measurement and layout",
        ("fonts", "characters", "layout", "model", "scene_text", "scene_lyrics"),
        "Font-dependent layout, source clusters, and editable body/ruby binding. Unicode code-point ranges must align with independently drawable clusters. See [text and cues](../guides/text-and-cues.md).",
    ),
    "geometry": (
        "Geometry and paths",
        (
            "geometry",
            "group_geometry",
            "path_geometry",
            "path_boolean",
            "path_layout",
            "path_animation",
            "path_motion",
            "text_geometry",
        ),
        "Script-space geometry, masks, deformation, path layout, and authored writing/morphing. Complexity bounds and topology requirements are explicit. See [geometry](../guides/geometry.md).",
    ),
    "paint": (
        "Colors and appearance",
        (
            "colors",
            "composition",
            "appearance",
            "paint_fields",
            "lyric_highlights",
            "lyric_paint",
        ),
        "RGB colors, typed appearance, spatial fields, and material animation. Pixel distances and opacity in 0..1 are authoring values; ASS encodings are output details. See [materials](../guides/materials.md).",
    ),
    "cues": (
        "Lyric cues",
        ("cues", "karaoke_cues"),
        "Typed content factories, reservations, independent placement, and body/ruby binding. Cue lifetimes and trigger values use seconds. See [text and cues](../guides/text-and-cues.md).",
    ),
    "particles": (
        "Particles and references",
        ("particles", "object_references", "lyric_particles"),
        "Deterministic emissions, delayed copies, and pure world-space dependencies. Time values use seconds. See [particles](../guides/particles.md).",
    ),
    "coverage": (
        "Coverage and raster output",
        (
            "coverage_animation",
            "coverage_output",
            "scene_raster",
            "raster_settings",
        ),
        "Explicit coverage/material and whole-group RGBA output. These retain distinct composition semantics and require deliberate resource limits. See [materials](../guides/materials.md).",
    ),
    "native": (
        "Regions and progress curves",
        ("timeline",),
        "Horizontal regions, normalized progress curves, and millisecond input display windows. HighlightPass and Scene animation clocks use seconds. Output goes through the common Scene compiler.",
    ),
    "templates": (
        "Python templates",
        ("engine", "_legacy_layout"),
        "The explicit ASS Python-template frontend and preserved millisecond preprocessing contexts. Ordinary Document loading does not execute templates. See [templates](../guides/templates.md).",
    ),
}


def exports() -> dict[str, str]:
    """Read the canonical import origins, including constants and type aliases."""
    tree = ast.parse((PACKAGE / "__init__.py").read_text(encoding="utf-8"))
    modules: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            for imported in node.names:
                name = imported.asname or imported.name
                if name in PUBLIC:
                    modules[name] = node.module
    if set(modules) != PUBLIC or len(PUBLIC) != len(api.__all__):
        raise ValueError(
            "public exports must be unique and have explicit import origins"
        )
    return modules


def stable(value: object) -> str:
    """Display a default without invoking a factory or embedding memory addresses."""
    if value is Ellipsis:
        return "..."
    if isinstance(value, Enum):
        return f"{type(value).__name__}.{value.name}"
    if value is None or isinstance(value, (bool, int, float, str)):
        return repr(value)
    if inspect.isclass(value) or inspect.isfunction(value):
        return value.__qualname__
    if isinstance(value, (tuple, list)):
        content = ", ".join(stable(item) for item in value)
        if isinstance(value, tuple):
            return "(" + content + ("," if len(value) == 1 else "") + ")"
        return "[" + content + "]"
    if isinstance(value, (set, frozenset)):
        return (
            type(value).__name__
            + "({"
            + ", ".join(sorted(stable(item) for item in value))
            + "})"
        )
    if isinstance(value, Mapping):
        pairs = sorted((stable(key), stable(item)) for key, item in value.items())
        return "{" + ", ".join(key + ": " + item for key, item in pairs) + "}"
    if is_dataclass(value) and not isinstance(value, type):
        content = ", ".join(
            f"{field.name}={stable(getattr(value, field.name))}"
            for field in fields(value)
        )
        return type(value).__name__ + "(" + content + ")"
    return type(value).__name__ + "()"


def annotation(value: object) -> str:
    if value is inspect.Signature.empty:
        return "unannotated"
    if value is None or value is type(None):
        return "None"
    if value is Ellipsis:
        return "..."
    if isinstance(value, str):
        return value
    if isinstance(value, TypeAliasType):
        return (
            value.__name__ if value.__name__ in PUBLIC else annotation(value.__value__)
        )
    origin = get_origin(value)
    arguments = get_args(value)
    if origin in (Union, UnionType):
        return " | ".join(annotation(item) for item in arguments)
    if origin is Literal:
        return "Literal[" + ", ".join(stable(item) for item in arguments) + "]"
    if origin is Callable and len(arguments) == 2:
        parameters, result = arguments
        inputs = (
            "..."
            if parameters is Ellipsis
            else "[" + ", ".join(annotation(item) for item in parameters) + "]"
        )
        return "Callable[" + inputs + ", " + annotation(result) + "]"
    if origin is not None:
        name = getattr(origin, "__name__", None)
        label = str(name) if name else inspect.formatannotation(origin)
        return label + "[" + ", ".join(annotation(item) for item in arguments) + "]"
    result = inspect.formatannotation(value)
    return (
        re.sub(r"kara_templater\.[a-z_]+\.", "", result)
        .replace("typing.", "")
        .replace("collections.abc.", "")
    )


def hints(value: object) -> dict[str, object]:
    module = inspect.getmodule(value)
    namespace = {
        **vars(api),
        **(vars(module) if module is not None else {}),
        **getattr(value, "__globals__", {}),
    }
    return {
        name: cast(object, expected)
        for name, expected in get_type_hints(value, globalns=namespace).items()
    }


def signature(
    value: object, label: str, *, skip_first: bool = False, constructor: bool = False
) -> str:
    if not callable(value):
        raise TypeError(f"{label} is not callable")
    raw = inspect.signature(value)
    resolved = hints(value.__init__ if constructor else value)
    parameters = [
        parameter for parameter in raw.parameters.values()
        if not (constructor and parameter.name.startswith("_"))
    ]
    if skip_first and parameters and parameters[0].name in {"self", "cls"}:
        parameters = parameters[1:]
    parts: list[str] = []
    starred = False
    for index, parameter in enumerate(parameters):
        if parameter.kind is inspect.Parameter.KEYWORD_ONLY and not starred:
            parts.append("*")
            starred = True
        prefix = (
            "*"
            if parameter.kind is inspect.Parameter.VAR_POSITIONAL
            else "**"
            if parameter.kind is inspect.Parameter.VAR_KEYWORD
            else ""
        )
        if prefix:
            starred = True
        item = prefix + parameter.name
        expected = resolved.get(parameter.name, parameter.annotation)
        if expected is not inspect.Signature.empty:
            item += ": " + annotation(expected)
        if parameter.default is not inspect.Parameter.empty:
            item += " = " + stable(parameter.default)
        parts.append(item)
        if parameter.kind is inspect.Parameter.POSITIONAL_ONLY and (
            index == len(parameters) - 1
            or parameters[index + 1].kind is not inspect.Parameter.POSITIONAL_ONLY
        ):
            parts.append("/")
    result = (
        label + "(\n" + "\n".join("    " + part + "," for part in parts) + "\n)"
        if parts
        else label + "()"
    )
    if not constructor:
        returned = resolved.get("return", raw.return_annotation)
        if returned is not inspect.Signature.empty:
            result += " -> " + annotation(returned)
    return result


def cell(value: str) -> str:
    return value.replace("|", r"\|").replace("\n", " ")


def source_link(value: object) -> str:
    if not (inspect.isclass(value) or inspect.isfunction(value)):
        return ""
    try:
        source = inspect.getsourcefile(value)
        if source is None:
            return ""
        path = Path(source).resolve().relative_to(PACKAGE.parent)
        line = inspect.getsourcelines(value)[1]
    except (TypeError, OSError, ValueError):
        return ""
    return f"[Source](../../{path.as_posix()}#L{line})"


def members(value: type) -> list[tuple[str, object, bool]]:
    results = []
    for name, raw in inspect.getmembers_static(value):
        if name.startswith("_") and name not in {"__call__", "__iter__", "__getitem__"}:
            continue
        property_member = isinstance(raw, (property, cached_property))
        function = (
            raw.fget
            if isinstance(raw, property)
            else raw.func
            if isinstance(raw, cached_property)
            else raw.__func__
            if isinstance(raw, (classmethod, staticmethod))
            else raw
        )
        if inspect.isfunction(function) and function.__module__.startswith(
            "kara_templater"
        ):
            results.append((name, function, property_member))
    return results


def describe_class(value: type, name: str, *, level: int = 2) -> list[str]:
    lines: list[str] = [
        f"{'#' * level} {name}",
        "",
        inspect.getdoc(value) or "",
        "",
        source_link(value),
        "",
    ]
    if issubclass(value, Enum):
        lines += [f"{'#' * (level + 1)} Values", ""]
        lines += [f"- `{name}.{item.name}` = `{stable(item.value)}`" for item in value]
        lines.append("")
    elif not is_typeddict(value) and not getattr(value, "_is_protocol", False):
        try:
            constructor = signature(value, name, constructor=True)
        except (TypeError, ValueError):
            if issubclass(value, BaseException):
                lines += [
                    f"Construction: `{name}(*args)` using the inherited exception constructor.",
                    "",
                ]
            elif issubclass(value, dict):
                lines += [
                    "Supports standard dict construction and attribute access to stored keys.",
                    "",
                    f"Example: `{name}(res_x=1280, res_y=720)`.",
                    "",
                ]
            else:
                raise
        else:
            lines += ["```python", constructor, "```", ""]
    resolved = hints(value)
    if is_dataclass(value):
        values = [
            (
                field.name,
                resolved.get(field.name, field.type),
                "required"
                if field.default is MISSING and field.default_factory is MISSING
                else stable(field.default)
                if field.default is not MISSING
                else getattr(field.default_factory, "__name__", "factory") + "()",
            )
            for field in fields(value)
            if not field.name.startswith("_")
        ]
    else:
        values = [
            (
                field,
                expected,
                "required key"
                if is_typeddict(value)
                and field in getattr(value, "__required_keys__", ())
                else "optional key"
                if is_typeddict(value)
                else "instance attribute",
            )
            for field, expected in resolved.items()
            if not field.startswith("_")
        ]
    if values:
        lines += [
            f"{'#' * (level + 1)} Fields",
            "",
            "| Name | Type | Default |",
            "| --- | --- | --- |",
        ]
        lines += [
            f"| `{field}` | `{cell(annotation(expected))}` | `{cell(default)}` |"
            for field, expected, default in values
        ]
        lines.append("")
    for member, function, property_member in members(value):
        if is_dataclass(value) and member in {field.name for field in fields(value)}:
            # Callable defaults are configuration fields, not instance methods.
            continue
        description = inspect.cleandoc(function.__doc__) if function.__doc__ else None
        if not description:
            raise ValueError(
                f"public member {name}.{member} needs an English docstring"
            )
        lines += [f"{'#' * (level + 1)} {name}.{member}", "", description, ""]
        if property_member:
            returned = hints(function).get("return", inspect.Signature.empty)
            lines += [f"Type: `{cell(annotation(returned))}`.", ""]
        else:
            lines += [
                "```python",
                signature(function, name + "." + member, skip_first=True),
                "```",
                "",
            ]
    for member, child in vars(value).items():
        if (
            not member.startswith("_")
            and inspect.isclass(child)
            and child.__module__.startswith("kara_templater")
            and child.__qualname__.startswith(value.__qualname__ + ".")
        ):
            lines.extend(describe_class(child, name + "." + member, level=level + 1))
    return lines


def generate() -> dict[Path, str]:
    modules = exports()
    grouped: dict[str, list[str]] = {group: [] for group in GROUPS}
    owners: dict[str, str] = {}
    for name, module in modules.items():
        choices = [
            group
            for group, (_, candidates, _) in GROUPS.items()
            if module in candidates
        ]
        if len(choices) != 1:
            raise ValueError(f"{name} needs exactly one reference group: {module}")
        owners[name] = choices[0]
        grouped[choices[0]].append(name)
    pages: dict[Path, str] = {}
    index = [
        "# API reference",
        "",
        "Generated from the final public exports, signatures, fields, and English docstrings.",
        "Reference signatures describe contracts; use the [tutorials](../tutorials/custom-animation.md)",
        "and [guides](../README.md) for complete workflows. Types remain importable from",
        "`kara_templater`; grouping here does not change their import paths.",
        "",
        "Regenerate from a built checkout with `python -m tools.generate_reference`.",
        "Use `--check` to verify that committed pages match the current public API.",
        "",
        "## Topics",
        "",
        "| Topic | Symbols |",
        "| --- | --- |",
    ]
    for group, (title, _, introduction) in GROUPS.items():
        names = sorted(grouped[group])
        index.append(f"| [{title}]({group}.md) | {len(names)} |")
        lines: list[str] = [
            f"# {title}",
            "",
            introduction,
            "",
            "[All public symbols](README.md#symbol-index)",
            "",
            "## Contents",
            "",
        ]
        lines += [f"- [{name}](#{name.lower()})" for name in names]
        lines.append("")
        for name in names:
            value = getattr(api, name)
            if inspect.isclass(value):
                if not inspect.getdoc(value):
                    raise ValueError(f"public type {name} needs an English docstring")
                lines.extend(describe_class(value, name))
            elif inspect.isfunction(value):
                description = inspect.getdoc(value)
                if not description:
                    raise ValueError(
                        f"public function {name} needs an English docstring"
                    )
                lines += [f"## {name}", "", description, "", source_link(value), ""]
                for overload in get_overloads(value) or (value,):
                    lines += ["```python", signature(overload, name), "```", ""]
            elif isinstance(value, TypeAliasType):
                lines += [
                    f"## {name}",
                    "",
                    "Public type alias:",
                    "",
                    "```python",
                    f"type {name} = {annotation(value.__value__)}",
                    "```",
                    "",
                ]
            else:
                lines += [
                    f"## {name}",
                    "",
                    "Public constant:",
                    "",
                    "```python",
                    name + " = " + stable(value),
                    "```",
                    "",
                ]
        pages[ROOT / "docs/reference" / f"{group}.md"] = (
            "\n".join(lines).rstrip() + "\n"
        )
    index += ["", "## Symbol index", "", f"{len(PUBLIC)} public exports.", ""]
    index += [
        f"- [{name}]({owners[name]}.md#{name.lower()})" for name in sorted(PUBLIC)
    ]
    pages[ROOT / "docs/reference/README.md"] = "\n".join(index) + "\n"
    return pages


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    pages = generate()
    changed = [
        path
        for path, content in pages.items()
        if not path.exists() or path.read_text(encoding="utf-8") != content
    ]
    if args.check:
        if changed:
            for path in changed:
                print(f"out of date: {path.relative_to(ROOT)}", file=sys.stderr)
            raise SystemExit(1)
    else:
        for path, content in pages.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
    print(
        f"{len(PUBLIC)} public exports, {len(pages)} reference pages {'checked' if args.check else 'generated'}"
    )


if __name__ == "__main__":
    main()
