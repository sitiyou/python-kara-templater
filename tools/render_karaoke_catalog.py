"""Render every built-in karaoke choice and four recommended combinations."""

import argparse
import hashlib
import json
import subprocess
from dataclasses import replace
from pathlib import Path
from typing import get_args

from examples.karaoke_catalog import build
from kara_templater import (
    Color,
    KaraokeDecoration,
    KaraokeEffects,
    KaraokeEntry,
    KaraokeExit,
    KaraokeSinging,
    SceneBudget,
)


def variants() -> list[tuple[str, KaraokeEffects]]:
    plain = KaraokeEffects(entry="none", exit="none", singing="none")
    choices = [
        (f"{field}-{name}", replace(plain, **{field: name}))
        for field, alias in (
            ("entry", KaraokeEntry),
            ("exit", KaraokeExit),
            ("singing", KaraokeSinging),
            ("decoration", KaraokeDecoration),
        )
        for name in get_args(alias.__value__)
    ]
    choices.extend(
        (
            ("stroke-flash", replace(plain, stroke_flash=True)),
            (
                "design-clear",
                KaraokeEffects(
                    entry="tracking_in",
                    exit="char_fade",
                    singing="scanline",
                    stroke_flash=True,
                ),
            ),
            (
                "design-sakura",
                KaraokeEffects(
                    entry="wave_in",
                    exit="petal",
                    singing="zoom_pulse",
                    decoration="petal",
                    sung=Color(255, 160, 205),
                    particle_size=0.18,
                    particle_rate=5,
                ),
            ),
            (
                "design-luminous",
                KaraokeEffects(
                    entry="glow_in",
                    exit="stretch_out",
                    singing="utopia_scanline",
                    decoration="twinkle",
                ),
            ),
            (
                "design-crystal",
                KaraokeEffects(
                    entry="assemble_in",
                    exit="dissolve_out",
                    singing="scanline",
                    decoration="snow",
                    particle_rate=4,
                ),
            ),
        )
    )
    return choices


def overview(root: Path, name: str, names: list[str], columns: int) -> None:
    """Keep overview decoding bounded; all individual originals remain 60 fps."""
    inputs = [arg for item in names for arg in ("-threads", "1", "-i", f"{item}.mp4")]
    filters = ";".join(f"[{i}:v]fps=30,scale=320:180[v{i}]" for i in range(len(names)))
    labels = "".join(f"[v{i}]" for i in range(len(names)))
    positions = "|".join(
        f"{(i % columns) * 320}_{(i // columns) * 180}" for i in range(len(names))
    )
    filters += (
        f";{labels}xstack=inputs={len(names)}:layout={positions}:fill=0x172033[out]"
    )
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-nostdin",
            "-y",
            *inputs,
            "-filter_complex_threads",
            "2",
            "-filter_complex",
            filters,
            "-map",
            "[out]",
            "-an",
            "-c:v",
            "libx264",
            "-threads",
            "2",
            "-crf",
            "18",
            f"{name}.mp4",
        ],
        cwd=root,
        check=True,
    )


def singing_comparison(root: Path) -> None:
    modes = ("utopia", "none", "no_wipe")
    inputs = [
        arg for mode in modes for arg in ("-ss", "0.9", "-i", f"singing-{mode}.mp4")
    ]
    panels = [
        f"[{i}:v]fps=20,crop=300:88:170:90,pad=426:88:126:0:color=0x172033,"
        f"drawtext=text={mode}:fontsize=21:fontcolor=white:x=12:y=31[v{i}]"
        for i, mode in enumerate(modes)
    ]
    filters = ";".join(
        (
            *panels,
            "[v0][v1][v2]vstack=3,split[v][q]",
            "[q]palettegen[p]",
            "[v][p]paletteuse",
        )
    )
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-nostdin",
            "-y",
            *inputs,
            "-t",
            "3.65",
            "-filter_complex",
            filters,
            "-loop",
            "0",
            "singing-motion.gif",
        ],
        cwd=root,
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--only", help="Optional name prefix, e.g. entry- or design-")
    args = parser.parse_args()
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=True)
    manifest = []
    for name, recipe in variants():
        if args.only and not name.startswith(args.only):
            continue
        scene = build(recipe=recipe)
        result = scene.compile(native_tweens=True, budget=SceneBudget(fps=60))
        ass = root / f"{name}.ass"
        result.document.save(ass)
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-nostdin",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "color=c=0x172033:s=640x360:r=60:d=6",
                "-vf",
                f"ass={name}.ass,drawtext=text={name}:x=18:y=18:fontsize=20:fontcolor=white",
                "-an",
                "-c:v",
                "libx264",
                "-threads",
                "2",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
                f"{name}.mp4",
            ],
            cwd=root,
            check=True,
        )
        manifest.append(
            {
                "name": name,
                "events": result.event_count,
                "bytes": ass.stat().st_size,
                "ass_sha256": hashlib.sha256(ass.read_bytes()).hexdigest(),
            }
        )
        print(f"{name}: {result.event_count} events", flush=True)
    for group in ("entry", "exit", "singing", "decoration", "design"):
        names = [
            name
            for name, _ in variants()
            if name.startswith(group + "-")
            and (not args.only or name.startswith(args.only))
        ]
        if len(names) > 1:
            overview(root, f"{group}-overview", names, 2 if group == "design" else 4)
    if {"singing-utopia", "singing-none", "singing-no_wipe"} <= {
        item["name"] for item in manifest
    }:
        singing_comparison(root)
    if any(item["name"] == "design-clear" for item in manifest):
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-nostdin",
                "-y",
                "-i",
                "design-overview.mp4",
                "-filter_complex_threads",
                "2",
                "-filter_complex",
                "fps=15,split[a][b];[a]palettegen[p];[b][p]paletteuse",
                "builtins.gif",
            ],
            cwd=root,
            check=True,
        )
    (root / f"manifest-{args.only or 'all'}.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
