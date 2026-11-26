"""Render small, silent card previews with the standalone Hook renderer."""

import hashlib
import json
import os
import shutil
import subprocess
from functools import cache
from pathlib import Path
from tempfile import TemporaryDirectory

from kara_templater import Document, PreparedHook

WIDTH = 480
PREVIEW_BUILD = Path(__file__).resolve().parents[1] / "build" / "component-catalog"
MEDIA_CACHE = PREVIEW_BUILD / "cache"


@cache
def _renderer_identity(ass: bool) -> bytes:
    identity = hashlib.sha256(Path(__file__).read_bytes())
    identity.update(subprocess.check_output(["ffmpeg", "-version"]))
    if ass:
        fonts = subprocess.check_output(["fc-list", "--format", "%{file}\n"], text=True)
        for path in sorted({Path(name) for name in fonts.splitlines()}):
            stat = path.stat()
            identity.update(f"{path}:{stat.st_size}:{stat.st_mtime_ns}\n".encode())
    return identity.digest()


def render_card(
    source: PreparedHook | Document,
    folder: Path,
    *,
    resolution: tuple[int, int],
    fps: int,
    start: float = 0,
    duration: float,
    still: float,
    animated: bool = True,
    cache_directory: Path | None = None,
) -> None:
    """Emit a playable loop and a matching static fallback from the same render."""
    source_width, source_height = resolution
    width = min(WIDTH, source_width) // 2 * 2
    height = round(width * source_height / source_width / 2) * 2
    frames = round(duration * fps)
    poster_frame = round((still - start) * fps)
    if not 0 <= poster_frame < frames:
        raise ValueError(f"{folder.name}: preview poster must fall inside the clip")

    folder.mkdir(parents=True, exist_ok=True)
    if isinstance(source, PreparedHook):
        input_file = folder / "card.hook"
        source.export(input_file, fps=fps, start=start, duration=duration)
        device = ["-init_hw_device", "vulkan=vk"]
        render = "libplacebo=custom_shader_path=card.hook:format=yuv420p"
    else:
        input_file = folder / "card.ass"
        source.save(input_file)
        device = []
        render = f"setpts=PTS+{start}/TB,ass=card.ass,setpts=PTS-STARTPTS"
    poster_filter = f"select=eq(n\\,{poster_frame})"
    video_output = []
    if animated:
        poster_filter = f"split[loop][frames];[frames]{poster_filter}"
        video_output = [
            "-map",
            "[loop]",
            "-frames:v",
            str(frames),
            "-an",
            "-c:v",
            "libx264",
            "-threads",
            "2",
            "-preset",
            "fast",
            "-crf",
            "21",
            "-movflags",
            "+faststart",
            "card.mp4",
        ]
    try:
        cached = None
        media = ("card.jpg", "card.mp4") if animated else ("card.jpg",)
        if cache_directory is not None:
            options = (width, height, fps, start, frames, poster_frame, animated)
            key = hashlib.sha256(json.dumps(options).encode())
            key.update(_renderer_identity(isinstance(source, Document)))
            key.update(input_file.read_bytes())
            cached = cache_directory / key.hexdigest()
            if all((cached / filename).is_file() for filename in media):
                for filename in media:
                    shutil.copyfile(cached / filename, folder / filename)
                return
        subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-nostdin",
                *device,
                "-filter_complex_threads",
                "1",
                "-f",
                "lavfi",
                "-i",
                f"color=c=0x161827:s={width}x{height}:r={fps}:d={duration}",
                "-filter_complex",
                f"[0:v]{render},{poster_filter}[poster]",
                *video_output,
                "-map",
                "[poster]",
                "-frames:v",
                "1",
                "-threads",
                "1",
                "-q:v",
                "3",
                "-update",
                "1",
                "card.jpg",
            ],
            cwd=folder,
            check=True,
        )
        if cached is not None:
            cached.parent.mkdir(parents=True, exist_ok=True)
            with TemporaryDirectory(dir=cached.parent) as temporary:
                completed = Path(temporary) / "card"
                completed.mkdir()
                for filename in media:
                    shutil.copyfile(folder / filename, completed / filename)
                try:
                    os.rename(completed, cached)
                except OSError:
                    if not all((cached / filename).is_file() for filename in media):
                        raise
    finally:
        input_file.unlink()
