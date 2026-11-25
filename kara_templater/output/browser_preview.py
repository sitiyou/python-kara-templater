"""Wrap the scene's GPU resources in a self-contained browser player."""

from __future__ import annotations

import json
import webbrowser
from base64 import b64encode
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import TYPE_CHECKING
from warnings import warn

if TYPE_CHECKING:
    from ..scene import Scene


_ASSETS = Path(__file__).with_name("preview")


def preview_in_browser(
    scene: Scene, path: str | Path | None, *, fps: int, start: float,
    duration: float | None, open_browser: bool,
) -> Path:
    target = None if path is None else Path(path).absolute()
    template = (_ASSETS / "index.html").read_text(encoding="utf-8")
    head, _, tail = template.partition("<!-- preview data -->")
    footer, _, end = tail.partition("<!-- preview player -->")
    player = (_ASSETS / "player.js").read_bytes()
    head = head.replace("@WIDTH@", str(scene.document.meta.res_x))
    head = head.replace("@HEIGHT@", str(scene.document.meta.res_y))

    with TemporaryDirectory() as tmp:
        resources = Path(tmp) / "resources"
        scene.export_resources(resources, fps=fps, start=start, duration=duration)
        staged: Path | None = None
        try:
            with NamedTemporaryFile(
                prefix="karaoke-preview-", suffix=".html",
                dir=None if target is None else target.parent, delete=False,
            ) as output:
                staged = Path(output.name)
                output.write(head.encode())
                for key, filename in (("manifest", "textures.json"), ("shader", "scene.frag")):
                    raw = (resources / filename).read_text(encoding="utf-8")
                    data = (json.dumps(raw) if key == "shader" else raw).replace("<", r"\u003c")
                    output.write(f'<script type="application/json" data-preview-asset="{key}">'.encode())
                    output.write(data.encode())
                    output.write(b"</script>\n")
                for key, filename in (("mask", "KARAMASK.bin"), ("table", "KARADATA.bin")):
                    output.write(f'<script type="application/octet-stream" data-preview-asset="{key}">'.encode())
                    with (resources / filename).open("rb") as texture:
                        for chunk in iter(lambda: texture.read(3 * 65536), b""):
                            output.write(b64encode(chunk))
                    output.write(b"</script>\n")
                output.write(footer.encode())
                output.write(player)
                output.write(end.encode())
            result = staged if target is None else staged.replace(target)
        except BaseException:
            if staged is not None:
                staged.unlink(missing_ok=True)
            raise

    if open_browser:
        try:
            opened = webbrowser.open(result.as_uri())
        except webbrowser.Error:
            opened = False
        if not opened:
            warn(f"Could not open the browser. Open the preview at {result}", RuntimeWarning, stacklevel=3)
    return result
