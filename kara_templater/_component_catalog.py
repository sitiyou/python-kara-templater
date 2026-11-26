"""Export built-in component declarations and their optional preview resources."""

import json
from collections.abc import Mapping
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path, PurePosixPath
from typing import NotRequired, TypedDict, cast

from .components import (
    ComponentParameter,
    ComponentTarget,
    ComponentValue,
    effect_components,
)


class ComponentParameterData(TypedDict):
    """JSON representation of an editable parameter declaration."""

    label: str
    kind: str
    default: ComponentValue
    bounds: list[float] | None
    step: float | None
    unit: str
    choices: list[str]
    live: bool
    advanced: bool


class EffectComponentData(TypedDict):
    """JSON representation of one editable effect component."""

    label: str
    slot: str
    targets: list[ComponentTarget]
    repeatable: bool
    parameters: dict[str, ComponentParameterData]


class ComponentCardData(TypedDict):
    """Preview card metadata with portable media names and a time in seconds."""

    id: str
    group: str
    api: str
    reference: str
    title: str
    zh: str
    details: NotRequired[str]
    zh_details: NotRequired[str]
    gallery: NotRequired[str]
    sampled: NotRequired[bool]
    ass: NotRequired[bool]
    start: NotRequired[float]
    end: NotRequired[float]
    still: NotRequired[float]
    live: NotRequired[Mapping[str, float]]
    poster: NotRequired[str]
    video: NotRequired[str]
    start_at: NotRequired[float]


class ComponentCatalog(TypedDict):
    """Versioned JSON catalog of components and preview cards."""

    schema_version: int
    script_height: int
    components: dict[str, EffectComponentData]
    cards: dict[str, ComponentCardData]
    preferred_cards: dict[str, str]


def _preview_root(directory: str | Path | None) -> Traversable:
    return Path(directory) if directory is not None else files("kara_templater").joinpath("_component_previews")


def component_preview_resource(
    name: str, *, preview_directory: str | Path | None = None,
) -> Traversable:
    """Locate a JPG or MP4 named in the component catalog.

    Names are relative POSIX paths. Use the returned resource's
    `open("rb")` or `read_bytes()` to access the packaged file. An explicit
    preview directory selects a locally generated catalog and its media.
    Invalid names raise ValueError. Opening missing media raises FileNotFoundError.
    """
    path = PurePosixPath(name)
    if (
        path.is_absolute() or path.as_posix() != name or ".." in path.parts
        or "\\" in name or ":" in name or path.suffix not in {".jpg", ".mp4"}
    ):
        raise ValueError(f"invalid component preview resource: {name!r}")
    return _preview_root(preview_directory).joinpath(*path.parts)


def _parameter_data(parameter: ComponentParameter) -> ComponentParameterData:
    return {
        "label": parameter.label,
        "kind": parameter.kind,
        "default": parameter.default,
        "bounds": list(parameter.bounds) if parameter.bounds is not None else None,
        "step": parameter.step,
        "unit": parameter.unit,
        "choices": list(parameter.choices),
        "live": parameter.live,
        "advanced": parameter.advanced,
    }


def component_catalog(
    *, script_height: int = 1080, preview_directory: str | Path | None = None,
) -> ComponentCatalog:
    """Return JSON-ready effect declarations and available preview cards.

    Parameter defaults and ranges use script pixels at the given height.
    Card examples use their own fixed script resolution. Card IDs are separate
    from editable component IDs, with preferred_cards linking the two.
    A source checkout without generated media still returns component declarations.
    The explicit preview directory accepts a generated components.json and its
    media. An incompatible manifest version raises ValueError. This call only
    reads metadata and never renders media.
    """
    components: dict[str, EffectComponentData] = {
        name: {
            "label": spec.label,
            "slot": spec.slot,
            "targets": list(spec.targets),
            "repeatable": spec.repeatable,
            "parameters": {
                key: _parameter_data(parameter) for key, parameter in spec.parameters.items()
            },
        }
        for name, spec in effect_components(script_height=script_height).items()
    }
    manifest = _preview_root(preview_directory).joinpath("components.json")
    cards: dict[str, ComponentCardData] = {}
    preferred: dict[str, str] = {}
    if manifest.is_file():
        data = cast("ComponentCatalog", json.loads(manifest.read_text(encoding="utf-8")))
        if data["schema_version"] != 1:
            raise ValueError("unsupported component preview catalog version")
        cards = data["cards"]
        preferred = {
            key: card for key, card in data["preferred_cards"].items()
            if key in components and card in cards
        }
    return {
        "schema_version": 1, "script_height": script_height,
        "components": components, "cards": cards, "preferred_cards": preferred,
    }
