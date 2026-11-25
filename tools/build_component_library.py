"""Stage the visual component library and validate built-in preset coverage."""

import json
import re
import tomllib
from pathlib import Path
from typing import NotRequired, TypedDict, cast

from examples.component_previews import FPS, PRESETS, build
from kara_templater import VisualNode
from tools.docs_preview_media import render_card


class Component(TypedDict):
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


PRESET_WINDOWS = {
    "entry": (0.4, 1.8, 0.9),
    "exit": (2.15, 4.75, 3.5),
    "highlight": (1.25, 3.85, 2.9),
    "decoration": (1.25, 4.4, 2.6),
}
PRESET_POSTERS = {
    "entry-stretch-in": 0.63,
    "exit-stretch-out": 4.10,
    "decoration-twinkle": 1.72,
}
NONE_LABELS = {
    "highlight": ("Steady colour wipe", "匀速走字"),
    "decoration": ("Plain wipe", "走字无装饰"),
}


def preset_cards(labels: dict[str, tuple[str, str]]) -> list[Component]:
    values = {value for presets in PRESETS.values() for value in presets}
    if missing := values.symmetric_difference(labels):
        raise ValueError(
            f"Update [presets] in components.toml for {', '.join(sorted(missing))}"
        )
    entries: list[Component] = []
    for group, presets in PRESETS.items():
        start, end, still = PRESET_WINDOWS[group]
        for preset in presets:
            slug = f"{group}-{preset.replace('_', '-')}"
            title, zh = (
                NONE_LABELS.get(group, labels[preset])
                if preset == "none"
                else labels[preset]
            )
            entries.append(
                {
                    "id": slug,
                    "group": group,
                    "api": f'{group}="{preset}"',
                    "reference": f"tracks#karaoke{group}",
                    "title": title,
                    "zh": zh,
                    "start": start,
                    "end": end,
                    "still": PRESET_POSTERS.get(slug, still),
                }
            )
    return entries


def stage_components(stage: Path, manifest: Path, gallery_ids: set[str]) -> None:
    data = tomllib.loads(manifest.read_text(encoding="utf-8"))
    components = cast("list[Component]", data["component"])
    presets = preset_cards(cast("dict[str, tuple[str, str]]", data["presets"]))
    entries = presets + components
    if len({entry["id"] for entry in entries}) != len(entries):
        raise ValueError("Duplicate component IDs in components.toml")

    def stage_card(entry: Component) -> None:
        slug = entry["id"]
        if not re.fullmatch(r"[a-z]+(?:-[a-z]+)*", slug):
            raise ValueError(f"Invalid component ID {slug!r}")
        if reused := entry.get("gallery"):
            if reused not in gallery_ids:
                raise ValueError(f"{slug}: unknown gallery example {reused}")
            return
        scene = build(slug)
        start = round(entry.get("start", 0) * FPS) / FPS
        scene_end = max(
            (
                node.lifetime.end
                for node in scene.objects
                if isinstance(node, VisualNode)
            ),
            default=0,
        )
        end = round(entry.get("end", scene_end) * FPS) / FPS
        render_card(
            scene.ass.compile().document if entry.get("ass") else scene.prepare_hook(),
            stage / "public" / "component-previews" / slug,
            resolution=(scene.document.meta.res_x, scene.document.meta.res_y),
            fps=FPS,
            start=start,
            duration=end - start,
            still=entry.get("still", 1.75),
            animated=entry["group"] != "typography",
        )

    for entry in components + presets:
        try:
            stage_card(entry)
        except Exception as error:
            error.add_note(f"Component preview: {entry['id']}")
            raise
    (stage / "components.json").write_text(
        json.dumps(entries, ensure_ascii=False), encoding="utf-8"
    )
    sources = stage / "public/component-previews"
    source = Path(__file__).resolve().parents[1] / "examples/component_previews.py"
    (sources / source.name).write_bytes(source.read_bytes())
    print(f"{len(entries)} component previews staged")
