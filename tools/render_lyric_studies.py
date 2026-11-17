"""Render actual ASS for eight lyric studies on dark/light/moving backgrounds."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from examples.lyric_studies import EFFECTS, build
from kara_templater import SceneBudget


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--japanese", action="store_true")
    args = parser.parse_args()
    assert isinstance(args.output, Path)
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, object] = {}
    backgrounds = {
        "dark": "color=c=0x20252f:s=640x360:r=60:d=6.5",
        "light": "color=c=0xe6e3dc:s=640x360:r=60:d=6.5",
        "moving": "testsrc2=s=640x360:r=60:d=6.5",
    }
    for effect in EFFECTS:
        scene = build(effect, japanese=args.japanese)
        result = scene.compile(native_tweens=True, budget=SceneBudget(fps=60))
        ass = root / f"{effect}.ass"
        result.document.save(ass)
        data = ass.read_bytes()
        manifest[effect] = {
            "events": result.event_count, "bytes": len(data), "peak_active": result.peak_active,
            "sha256": hashlib.sha256(data).hexdigest(), "japanese": args.japanese,
            "fonts": sorted({style.fontname for style in scene.document.styles.values()}),
        }
        for background, source in backgrounds.items():
            subprocess.run([
                "ffmpeg", "-v", "error", "-nostdin", "-y", "-f", "lavfi", "-i", source,
                "-vf", f"ass={effect}.ass,drawtext=text={effect}:x=16:y=12:fontsize=18:fontcolor=white:box=1:boxcolor=black@0.6",
                "-an", "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p",
                f"{effect}-{background}.mp4",
            ], cwd=root, check=True)
        print(f"{effect}: {result.event_count} events / {len(data)} bytes", flush=True)
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    for background in backgrounds:
        inputs = [item for effect in EFFECTS for item in ("-i", f"{effect}-{background}.mp4")]
        filters = ";".join(f"[{i}:v]scale=320:180[v{i}]" for i in range(len(EFFECTS)))
        labels = "".join(f"[v{i}]" for i in range(len(EFFECTS)))
        filters += f";{labels}xstack=inputs=8:layout=0_0|320_0|640_0|960_0|0_180|320_180|640_180|960_180[out]"
        subprocess.run([
            "ffmpeg", "-v", "error", "-nostdin", "-y", *inputs,
            "-filter_complex", filters, "-map", "[out]", "-an", "-c:v", "libx264",
            "-crf", "20", f"comparison-{background}.mp4",
        ], cwd=root, check=True)


if __name__ == "__main__":
    main()
