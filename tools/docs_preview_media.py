"""Render small, silent card previews with the standalone Hook renderer."""

import subprocess
from pathlib import Path

from kara_templater import Document, PreparedHook

WIDTH = 480


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
    finally:
        input_file.unlink()
