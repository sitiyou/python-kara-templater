"""Render authoring previews from compiled events and pass RGBA frames to encoders."""

import subprocess
from math import ceil
from pathlib import Path

from PIL import Image

from kara_templater._ass_preview import rasterize


def frame(script: str, time_ms: int, width: int, height: int) -> Image.Image:
    result = Image.new("RGBA", (width, height))
    for x, y, w, h, _, color, pixels in rasterize(
        script, time_ms, width, height, 64_000_000, 50_000
    ):
        alpha = 255 - (color & 255)
        mask = Image.frombytes("L", (w, h), pixels)
        if alpha != 255:
            mask = mask.point([round(i * alpha / 255) for i in range(256)])
        ink = Image.new(
            "RGBA", (w, h), (color >> 24, color >> 16 & 255, color >> 8 & 255, 255)
        )
        ink.putalpha(mask)
        result.alpha_composite(ink, (x, y))
    return result


def encode_preview(
    script: str,
    size: tuple[int, int],
    fps: int,
    duration: float,
    background: str,
    filters: str,
    output_args: list[str],
    directory: Path,
) -> None:
    width, height = size
    command = [
        "ffmpeg",
        "-v",
        "error",
        "-nostdin",
        "-y",
        "-f",
        "lavfi",
        "-i",
        background,
        "-f",
        "rawvideo",
        "-pixel_format",
        "rgba",
        "-video_size",
        f"{width}x{height}",
        "-framerate",
        str(fps),
        "-i",
        "pipe:0",
        "-filter_complex",
        "[0:v][1:v]overlay=shortest=1" + filters,
        *output_args,
    ]
    with subprocess.Popen(command, cwd=directory, stdin=subprocess.PIPE) as process:
        assert process.stdin is not None
        try:
            for index in range(ceil(duration * fps)):
                process.stdin.write(
                    frame(script, round(index * 1000 / fps), width, height).tobytes()
                )
        finally:
            process.stdin.close()
        if process.wait():
            raise subprocess.CalledProcessError(process.returncode, command)
