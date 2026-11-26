import json
from dataclasses import asdict
from pathlib import Path

import pytest

from kara_templater import (
    component_catalog,
    component_preview_resource,
    effect_components,
)
from tools.build_component_library import describe_cards, publish_previews


def test_catalog_serializes_the_effects_for_the_requested_height(tmp_path: Path) -> None:
    for height in (720, 1080):
        catalog = component_catalog(script_height=height, preview_directory=tmp_path)
        components = {
            name: asdict(spec)
            for name, spec in effect_components(script_height=height).items()
        }
        assert catalog["components"] == json.loads(json.dumps(components))
        assert catalog["script_height"] == height
        assert catalog["schema_version"] == 1
        assert not catalog["cards"]


def test_partial_preview_export_keeps_existing_media(tmp_path: Path) -> None:
    stage = tmp_path / "stage"
    public = stage / "public"
    public.mkdir(parents=True)
    output = tmp_path / "output"
    catalog = describe_cards()
    assert catalog["preferred_cards"]["echo"] == "lyric-echo"
    for card_id, component in (("entry-fade", "entry-fade"), ("lyric-echo", "echo")):
        (public / "poster.jpg").write_bytes(card_id.encode())
        card = catalog["cards"][card_id].copy()
        card["poster"] = "poster.jpg"
        partial = catalog.copy()
        partial["cards"] = {card_id: card}
        partial["preferred_cards"] = {component: card_id}
        publish_previews(
            stage,
            partial,
            output,
            merge=True,
        )
    exported = component_catalog(preview_directory=output)
    assert exported["preferred_cards"] == {"entry-fade": "entry-fade", "echo": "lyric-echo"}
    for card_id, card in exported["cards"].items():
        resource = component_preview_resource(card["poster"], preview_directory=output)
        assert resource.read_bytes() == card_id.encode()
    with pytest.raises(ValueError, match="invalid component preview"):
        component_preview_resource("../poster.jpg", preview_directory=output)
