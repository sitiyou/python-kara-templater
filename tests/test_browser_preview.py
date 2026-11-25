import json
import re
import webbrowser
from base64 import b64decode
from hashlib import sha256

import pytest

from kara_templater import Document, Lifetime, PathObject, Scene, VectorPath


def _scene():
    return Scene(Document.create(width=64, height=32)).add(PathObject(
        id="mark", path=VectorPath.rectangle(14, 14), lifetime=Lifetime(0, 2),
    ))


def test_browser_preview_embeds_resources_and_opens_the_saved_file(tmp_path, monkeypatch):
    opened = []

    def open_browser(uri):
        opened.append(uri)
        return True

    monkeypatch.setattr(webbrowser, "open", open_browser)
    destination = tmp_path / "预览 #1.html"
    path = _scene().preview(destination, fps=12, start=0.5, duration=1)
    assert path == destination
    assert opened == [destination.as_uri()]
    assert list(tmp_path.iterdir()) == [destination]
    html = path.read_text(encoding="utf-8")
    assert '<canvas width="64" height="32"' in html
    assets = dict(re.findall(r'data-preview-asset="(\w+)">([^<]+)</script>', html))
    manifest = json.loads(assets["manifest"])
    assert manifest["clock"] == [12, 6, 12]
    assert "vec4 hook()" in json.loads(assets["shader"])
    assert sha256(b64decode(assets["mask"])).hexdigest() == manifest["hashes"]["KARAMASK"]
    assert sha256(b64decode(assets["table"])).hexdigest() == manifest["hashes"]["KARADATA"]
    assert 'customElements.define("kara-preview"' in html


def test_browser_preview_preserves_destination_on_compilation_failure(tmp_path, monkeypatch):
    def unexpected_open(_uri):
        pytest.fail("Invalid previews must not open a browser")

    monkeypatch.setattr(webbrowser, "open", unexpected_open)
    destination = tmp_path / "preview.html"
    destination.write_text("previous preview")
    with pytest.raises(ValueError, match="frame aligned"):
        _scene().preview(destination, start=0.03)
    assert destination.read_text() == "previous preview"
    assert list(tmp_path.iterdir()) == [destination]


def test_browser_preview_can_be_saved_without_opening_a_browser(tmp_path, monkeypatch):
    opened = []
    monkeypatch.setattr(webbrowser, "open", lambda uri: opened.append(uri) or False)
    destination = tmp_path / "preview.html"
    assert _scene().preview(destination, open_browser=False) == destination
    assert opened == []
    with pytest.warns(RuntimeWarning, match="Could not open the browser"):
        path = _scene().preview()
    try:
        assert opened == [path.as_uri()]
        assert path.is_file()
    finally:
        path.unlink()
