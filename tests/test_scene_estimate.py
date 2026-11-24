"""ASS preflight reports an immutable estimate before emitting events."""

from dataclasses import FrozenInstanceError

import pytest

from kara_templater import AssEstimate, Document, Lifetime, Scene, TextObject


def test_cancel_before_output_without_mutating_sources():
    document = Document.create()
    node = TextObject(id="line", text="A", lifetime=Lifetime(0, 1))
    scene = Scene(document).add(node)
    original = document.dumps()

    def cancel(estimate: AssEstimate) -> None:
        assert estimate.estimated_events == 1
        with pytest.raises(FrozenInstanceError):
            estimate.estimated_events = 0  # ty: ignore[invalid-assignment]
        raise RuntimeError("cancel export")

    with pytest.raises(RuntimeError, match="cancel export"):
        scene.ass.compile(on_estimate=cancel)
    assert document.dumps() == original
    assert tuple(scene.objects) == (node,)
    assert scene.ass.compile().event_count == 1
