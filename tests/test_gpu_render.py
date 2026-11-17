import json
import shutil
import subprocess
from importlib.util import find_spec

import pytest

from kara_templater import (
    Document,
    Lifetime,
    Line,
    Scene,
    TextObject,
    Vec2,
    VisualState,
    render_enhanced,
)


@pytest.mark.skipif(
    find_spec("moderngl") is None
    or shutil.which("ffmpeg") is None
    or shutil.which("ffprobe") is None,
    reason="optional GPU/video tools",
)
def test_gpu_render_streams_video_and_audio_with_selected_timing(tmp_path):
    video, output = tmp_path / "input.mp4", tmp_path / "output.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=black:s=160x100:r=10:d=1",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=1",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-shortest",
            str(video),
        ],
        check=True,
    )
    fallback = Document.create(width=160, height=100)
    fallback.records.append(Line(text="fallback", end_time=1000))
    scene = Scene(fallback).add(
        TextObject(
            id="word",
            text="Hi",
            lifetime=Lifetime(0, 0.3),
            state=VisualState(position=Vec2(20, 20)),
        )
    )
    enhanced = scene.enhance(fallback, fps=10)
    render_enhanced(enhanced, video, output, start=0.2, duration=0.4)
    report = json.loads(
        subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(output)]
        )
    )
    streams = {stream["codec_type"]: stream for stream in report["streams"]}
    assert streams["video"]["nb_frames"] == "4"
    assert streams["video"]["r_frame_rate"] == "10/1"
    assert abs(float(streams["video"]["duration"]) - 0.4) < 0.001
    assert abs(float(streams["audio"]["duration"]) - 0.4) < 0.03
    assert not list(tmp_path.glob("*.png"))
    assert not list(tmp_path.glob(".*.partial*"))
    with pytest.raises(FileExistsError):
        render_enhanced(enhanced, video, output)
