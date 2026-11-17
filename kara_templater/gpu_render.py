"""Explicit enhanced-ASS video rendering; no frame sequence is written to disk."""

import argparse
import json
import math
import subprocess
import tempfile
from pathlib import Path
from uuid import uuid4

from ._gpu import CoverageRenderer
from ._gpu_bundle import EnhancedFrames
from .ass import Document


def render_enhanced(
    document: Document,
    video: str | Path,
    output: str | Path,
    *,
    start: float = 0,
    duration: float | None = None,
    backend: str = "egl",
    overwrite: bool = False,
) -> None:
    """Burn an enhanced ASS into video with GPU coverage/gradient rendering.

    Requires ModernGL, a working OpenGL 3.3 context and FFmpeg on PATH. Frames
    stream as premultiplied RGBA to FFmpeg; video is encoded with libx264 and
    optional input audio with AAC. Original audio/video timing is retained for
    the selected interval, rebased to zero. Resolution/fps come from the payload.
    Start must be on that frame grid; duration rounds up to a whole frame. Output
    is atomically replaced only on success; existing files require overwrite.
    """
    frames = EnhancedFrames.read(document)
    if (
        not math.isfinite(start)
        or start < 0
        or abs(start * frames.fps - round(start * frames.fps)) > 1e-6
    ):
        raise ValueError(
            "render start must be nonnegative and on the payload frame grid"
        )
    if duration is not None and (not math.isfinite(duration) or duration <= 0):
        raise ValueError("render duration must be finite and positive")
    video, output = Path(video).resolve(), Path(output).resolve()
    if video == output:
        raise ValueError("render output must differ from input video")
    if not video.is_file():
        raise FileNotFoundError(video)
    if output.exists() and not overwrite:
        raise FileExistsError(output)
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(video),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode:
        raise RuntimeError(f"FFprobe failed: {probe.stderr[:16384]}")
    try:
        video_duration = float(json.loads(probe.stdout)["format"]["duration"])
    except (ValueError, KeyError, TypeError) as error:
        raise ValueError("input video needs a finite duration") from error
    if not math.isfinite(video_duration) or video_duration <= 0:
        raise ValueError("input video needs a finite positive duration")
    first = round(start * frames.fps)
    last = math.ceil(video_duration * frames.fps)
    end = (
        last
        if duration is None
        else min(last, first + math.ceil(duration * frames.fps))
    )
    if first >= end:
        raise ValueError("render interval does not intersect the input video")
    temporary = output.with_name(f".{output.stem}.{uuid4().hex}.partial{output.suffix}")
    command = [
        "ffmpeg",
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-n",
        "-filter_complex_threads",
        "2",
        "-threads",
        "2",
        "-ss",
        str(start),
        "-i",
        str(video),
        "-f",
        "rawvideo",
        "-pixel_format",
        "rgba",
        "-video_size",
        f"{frames.width}x{frames.height}",
        "-framerate",
        str(frames.fps),
        "-i",
        "pipe:0",
        "-filter_complex",
        f"[0:v]fps={frames.fps},scale={frames.width}:{frames.height},setpts=PTS-STARTPTS[base];"
        "[base][1:v]overlay=alpha=premultiplied:shortest=1:format=auto[out]",
        "-map",
        "[out]",
        "-map",
        "0:a?",
        "-c:v",
        "libx264",
        "-threads",
        "4",
        "-crf",
        "18",
        "-preset",
        "fast",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-t",
        str((end - first) / frames.fps),
        "-shortest",
        str(temporary),
    ]
    try:
        with (
            CoverageRenderer(frames.width, frames.height, backend=backend) as gpu,
            tempfile.TemporaryFile() as errors,
        ):
            print(f"GPU: {gpu.device}", flush=True)
            process = subprocess.Popen(
                command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=errors
            )
            assert process.stdin is not None
            try:
                decoded = iter(frames.frames())
                for index in range(end):
                    draws = next(decoded, ())
                    if index < first:
                        continue
                    gpu.clear()
                    for draw in draws:
                        draw.draw(gpu)
                    process.stdin.write(gpu.read())
                process.stdin.close()
                code = process.wait()
                if code:
                    errors.seek(0)
                    raise RuntimeError(
                        f"FFmpeg exited {code}: {errors.read(16384).decode(errors='replace')}"
                    )
            except BaseException as error:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                process.stdin.close()
                if isinstance(error, BrokenPipeError):
                    errors.seek(0)
                    raise RuntimeError(
                        f"FFmpeg closed the frame stream: {errors.read(16384).decode(errors='replace')}"
                    ) from error
                raise
        if not overwrite and output.exists():
            raise FileExistsError(output)
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render enhanced ASS into video using GPU shaders"
    )
    parser.add_argument("subtitle", type=Path)
    parser.add_argument("video", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--start", type=float, default=0)
    parser.add_argument("--duration", type=float)
    parser.add_argument("--backend", default="egl")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    try:
        render_enhanced(
            Document.load(args.subtitle),
            args.video,
            args.output,
            start=args.start,
            duration=args.duration,
            backend=args.backend,
            overwrite=args.overwrite,
        )
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(1, f"kara-render: {error}\n")


if __name__ == "__main__":
    main()
