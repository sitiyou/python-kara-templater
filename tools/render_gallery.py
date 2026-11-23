"""Render the representative examples to ASS and GitHub-friendly animated GIFs.

Run from a source checkout with FFmpeg and the checks dependencies:
python -m tools.render_gallery --case word-backgrounds
Historical sampled ASS cases cannot be regenerated with this exporter. Reports and ASS stay under build/.
"""

import argparse
import hashlib
import json
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from examples.scene_cues import build
from kara_templater import load_font
from tools.preview_frames import encode_preview

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class GalleryArtifact:
    """Provenance for a preview rendered from a saved ASS file."""

    name: str
    source: str
    source_sha256: str
    ass_sha256: str
    gif_sha256: str
    events: int
    active: int
    ass_bytes: int
    gif_bytes: int
    width: int
    fps: int
    duration: float


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render(
    output: Path,
    assets: Path,
    *,
    width: int,
    fps: int,
    duration: float,
) -> GalleryArtifact:
    """Compile one fixture, then encode its CPU preview with FFmpeg."""
    scene = build()
    result = scene.ass.compile()
    subtitle = output / "word-backgrounds.ass"
    result.document.save(subtitle)
    ass_digest = digest(subtitle)
    destination = assets / "word-backgrounds.gif"
    size = f"{scene.document.meta.res_x}x{scene.document.meta.res_y}"
    graph = (f",scale={width}:-2:flags=lanczos,split[frames][colors];"
             "[colors]palettegen[palette];[frames][palette]paletteuse=dither=bayer:bayer_scale=3")
    encode_preview(result.document.dumps(), (scene.document.meta.res_x, scene.document.meta.res_y),
                   fps, duration, f"color=c=0x181b24:s={size}:r={fps}:d={duration}",
                   graph, ["-loop", "0", str(destination)], output)
    if digest(subtitle) != ass_digest:
        raise RuntimeError("preview generation changed the exported ASS")
    source = ROOT / (build.__module__.replace(".", "/") + ".py")
    return GalleryArtifact(
        "word-backgrounds",
        str(source.relative_to(ROOT)),
        digest(source),
        ass_digest,
        digest(destination),
        result.event_count,
        result.peak_active,
        subtitle.stat().st_size,
        destination.stat().st_size,
        width,
        fps,
        duration,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--case", choices=("word-backgrounds",), default="word-backgrounds"
    )
    parser.add_argument("--output", type=Path, default=ROOT / "build/gallery")
    parser.add_argument("--assets", type=Path, default=ROOT / "docs/examples/assets")
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--fps", type=int, default=12)
    parser.add_argument("--duration", type=float, default=5.0)
    args = parser.parse_args()
    if args.width < 16 or not 1 <= args.fps <= 50 or args.duration <= 0:
        parser.error("width must be at least 16, fps in 1..50, and duration positive")
    output = args.output.resolve()
    assets = args.assets.resolve()
    output.mkdir(parents=True, exist_ok=True)
    assets.mkdir(parents=True, exist_ok=True)
    fonts = output / "fonts"
    fonts.mkdir(exist_ok=True)
    for path in sorted((ROOT / "tests/fonts").glob("*.ttf")):
        load_font(path)
        shutil.copyfile(path, fonts / path.name)
    version = subprocess.run(
        ["ffmpeg", "-version"], capture_output=True, text=True, check=True
    ).stdout.splitlines()[0]
    artifact = render(output, assets, width=args.width, fps=args.fps, duration=args.duration)
    print(f"{artifact.name}: {artifact.events} events, {artifact.gif_bytes} GIF bytes")
    (output / "report.json").write_text(
        json.dumps(
            {
                "renderer": version,
                "background": "#181b24",
                "fonts": {
                    path.name: digest(path) for path in sorted(fonts.glob("*.ttf"))
                },
                "artifacts": [asdict(artifact)],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
