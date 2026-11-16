"""Compare common Scene native opacity with independently encoded static ASS."""

import argparse
import hashlib
import json
from dataclasses import replace
from pathlib import Path

from PIL import Image

from kara_templater import (
    Document,
    Lifetime,
    Line,
    Scene,
    StatePatch,
    Style,
    TextObject,
    Tween,
    Vec2,
    VisualState,
    load_font,
)
from kara_templater._raster import rasterize

TIMES = (500, 1000, 1250, 1500, 1750, 2000, 2500)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    output = parser.parse_args().output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    font = load_font(Path(__file__).resolve().parents[1] / "tests/fonts/DejaVuSans.ttf")
    style = Style(fontname=font.family, fontsize=64, outline=0, shadow=0)
    document = Document.create(width=640, height=480, styles=(style,))
    glyph = TextObject(
        id="before",
        text="W",
        font=font.family,
        font_size=64,
        lifetime=Lifetime(0, 1),
        state=VisualState(position=Vec2(200, 180)),
    )
    # Discontinuous exposure boundaries remain explicit objects; the middle
    # object's continuous ramp uses the same Tween as every other Scene visual.
    ramp = replace(
        glyph,
        id="ramp",
        lifetime=Lifetime(1, 2),
        state=replace(glyph.state, opacity=0.2),
    ).animate(
        Tween(StatePatch(opacity=0.8)),
        duration=1,
    )
    after = replace(
        glyph,
        id="after",
        lifetime=Lifetime(2, 3),
        state=replace(glyph.state, opacity=0.8),
    )
    result = Scene(document).add(glyph, ramp, after).compile(native_tweens=True)
    assert any(item.strategy == "native-tween" for item in result.objects)
    result.document.save(output / "native.ass")
    reference = Document.create(width=640, height=480, styles=(style,))
    for time in TIMES:
        opacity = 1 if time < 1000 else 0.2 + 0.6 * min(1, (time - 1000) / 1000)
        alpha = int(255 * (1 - opacity) + 0.5)
        reference.records.append(
            Line(
                start_time=time,
                end_time=time + 10,
                text=(rf"{{\an7\q2\pos(200,180)\alpha&H{alpha:02X}&}}W"),
            )
        )
    reference.save(output / "reference.ass")
    frames = []
    for time in TIMES:
        actual = rasterize(result.document.dumps(), time, (640, 480)).rgba
        expected = rasterize(reference.dumps(), time, (640, 480)).rgba
        assert max(actual[3::4]) > 20, (time, "missing glyph")

        def on_black(rgba: bytes) -> bytes:
            image = Image.frombytes("RGBA", (640, 480), rgba)
            return (
                Image.alpha_composite(Image.new("RGBA", image.size, "black"), image)
                .convert("RGB")
                .tobytes()
            )

        error = max(
            abs(a - b)
            for a, b in zip(on_black(actual), on_black(expected), strict=True)
        )
        alpha_error = max(
            abs(a - b) for a, b in zip(actual[3::4], expected[3::4], strict=True)
        )
        assert alpha_error <= 1, (time, alpha_error)
        # Native ASS interpolates quantized endpoint alphas; the reference rounds
        # the analytic alpha once. Keep the prior validator's 3-channel bound.
        assert error <= 3, (time, error)
        if time in (500, 1000, 2000, 2500):
            assert error == 0, (time, "endpoint mismatch")
        Image.frombytes("RGBA", (640, 480), actual).save(output / f"native-{time}.png")
        frames.append(
            {
                "time_ms": time,
                "max_channel_error": error,
                "sha256": hashlib.sha256(actual).hexdigest(),
            }
        )
    report = {
        "font_sha256": font.sha256,
        "events": result.event_count,
        "frames": frames,
        "max_channel_tolerance": 3,
        "reference": "Direct static ASS with independently calculated opacity; no Scene evaluator or compiler.",
    }
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        f"{len(frames)} native opacity reference frames passed; {result.event_count} events"
    )


if __name__ == "__main__":
    main()
