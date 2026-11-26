"""Stage the visual component library and validate built-in preset coverage."""

import argparse
import hashlib
import json
import re
import shutil
import sys
import tomllib
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal, cast

from examples.component_previews import FPS, PRESETS, build
from kara_templater import (
    ComponentCardData,
    ComponentCatalog,
    VisualNode,
    component_catalog,
)
from tools.docs_preview_media import MEDIA_CACHE, PREVIEW_BUILD, render_card

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs" / "examples" / "components.toml"

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
LIVE_SWEEP_CARDS = {"sweep-color", "sweep-width", "sweep-softness", "sweep-strength"}


def preset_cards(labels: dict[str, tuple[str, str]]) -> list[ComponentCardData]:
    values = {value for presets in PRESETS.values() for value in presets}
    if missing := values.symmetric_difference(labels):
        raise ValueError(
            f"Update [presets] in components.toml for {', '.join(sorted(missing))}"
        )
    entries: list[ComponentCardData] = []
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


def describe_cards(manifest: Path = MANIFEST) -> ComponentCatalog:
    data = tomllib.loads(manifest.read_text(encoding="utf-8"))
    components = cast("list[ComponentCardData]", data["component"])
    presets = preset_cards(cast("dict[str, tuple[str, str]]", data["presets"]))
    entries = presets + components
    cards = {entry["id"]: entry for entry in entries}
    if len(cards) != len(entries):
        raise ValueError("Duplicate card IDs in components.toml")
    if any(not re.fullmatch(r"[a-z]+(?:-[a-z0-9]+)*", slug) for slug in cards):
        raise ValueError("Invalid card ID in components.toml")
    catalog = component_catalog()
    preferred = {name: name for name in catalog["components"] if name in cards}
    overrides = cast("dict[str, str]", data.get("preferred_cards", {}))
    if unknown := overrides.keys() - catalog["components"].keys():
        raise ValueError(f"Unknown editable components: {', '.join(sorted(unknown))}")
    if missing := set(overrides.values()) - cards.keys():
        raise ValueError(f"Unknown preview cards: {', '.join(sorted(missing))}")
    preferred.update(overrides)
    catalog.update(cards=cards, preferred_cards=preferred)
    return catalog


def stage_card(stage: Path, entry: ComponentCardData, gallery_ids: set[str]) -> None:
    slug = entry["id"]
    if reused := entry.get("gallery"):
        if reused not in gallery_ids:
            raise ValueError(f"{slug}: unknown gallery example {reused}")
        folder = stage / "public" / "previews" / reused
    else:
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
        folder = stage / "public" / "component-previews" / slug
        width, height = scene.document.meta.res_x, scene.document.meta.res_y
        still = entry.get("still", 1.75)
        prepared = None if entry.get("ass") else scene.prepare_hook()
        if slug in LIVE_SWEEP_CARDS and prepared is not None:
            folder.mkdir(parents=True, exist_ok=True)
            prepared.export_resources(folder / "live", fps=FPS, start=start, duration=end - start)
            entry["live"] = {"width": width, "height": height, "still": still - start}
        render_card(
            prepared if prepared is not None else scene.ass.compile().document,
            folder,
            resolution=(width, height),
            fps=FPS,
            start=start,
            duration=end - start,
            still=still,
            animated=entry["group"] != "typography",
            cache_directory=MEDIA_CACHE,
        )
        if entry["group"] != "typography":
            entry["start_at"] = round(max(0, still - start), 3)
    entry["poster"] = (folder / "card.jpg").relative_to(stage / "public").as_posix()
    if (folder / "card.mp4").is_file():
        entry["video"] = (folder / "card.mp4").relative_to(stage / "public").as_posix()


def stage_cards(stage: Path, catalog: ComponentCatalog, gallery_ids: set[str]) -> None:
    for entry in catalog["cards"].values():
        try:
            stage_card(stage, entry, gallery_ids)
        except Exception as error:
            error.add_note(f"Component preview: {entry['id']}")
            raise


def stage_components(stage: Path, gallery_ids: set[str]) -> None:
    catalog = describe_cards()
    stage_cards(stage, catalog, gallery_ids)
    (stage / "components.json").write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
    sources = stage / "public/component-previews"
    source = ROOT / "examples/component_previews.py"
    shutil.copyfile(source, sources / source.name)
    print(f"{len(catalog['cards'])} component previews staged")


@contextmanager
def _preview_manifest_lock(output: Path) -> Generator[None]:
    # An advisory lock releases on close, including after an interrupted build.
    with output.with_name(f".{output.name}.lock").open("a+b") as lock:
        if sys.platform == "win32":
            import msvcrt

            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def publish_previews(
    stage: Path, catalog: ComponentCatalog, output: Path, *, merge: bool,
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output) as temporary:
        fields: tuple[Literal["poster"], Literal["video"]] = ("poster", "video")
        for entry in catalog["cards"].values():
            entry.pop("live", None)
            for field in fields:
                if not (name := entry.get(field)):
                    continue
                source = stage / "public" / name
                with source.open("rb") as stream:
                    digest = hashlib.file_digest(stream, "sha256").hexdigest()
                resource = digest + source.suffix
                if not (output / resource).is_file():
                    staged = Path(temporary) / resource
                    shutil.copyfile(source, staged)
                    staged.replace(output / resource)
                entry[field] = resource
        with _preview_manifest_lock(output):
            if merge:
                previous = component_catalog(preview_directory=output)
                catalog["cards"] = previous["cards"] | catalog["cards"]
                catalog["preferred_cards"] = previous["preferred_cards"] | catalog["preferred_cards"]
            manifest = Path(temporary) / "components.json"
            manifest.write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
            manifest.replace(output / manifest.name)


def main() -> None:
    from tools.build_docs_site import stage_gallery

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=PREVIEW_BUILD / "previews")
    parser.add_argument("--card", action="append", help="Render only this card; repeat as needed")
    parser.add_argument("--editable", action="store_true", help="Only include editable component cards")
    args = parser.parse_args()
    catalog = describe_cards()
    selected = set(args.card or catalog["cards"])
    if unknown := selected - catalog["cards"].keys():
        parser.error(f"unknown preview cards: {', '.join(sorted(unknown))}")
    if args.editable:
        selected.intersection_update(catalog["preferred_cards"].values())
    catalog["cards"] = {name: card for name, card in catalog["cards"].items() if name in selected}
    catalog["preferred_cards"] = {
        name: card for name, card in catalog["preferred_cards"].items() if card in selected
    }
    PREVIEW_BUILD.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=PREVIEW_BUILD) as temporary:
        stage = Path(temporary)
        reused = {card["gallery"] for card in catalog["cards"].values() if "gallery" in card}
        gallery_ids = stage_gallery(stage, only=reused)
        stage_cards(stage, catalog, gallery_ids)
        publish_previews(stage, catalog, args.output, merge=bool(args.card))
    print(f"{len(selected)} component previews updated in {args.output}")


if __name__ == "__main__":
    main()
