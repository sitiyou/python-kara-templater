"""Fixed 180-second composition of the existing effect fixtures.

uv run python -m examples.scene_whole_song output.ass
Each six-second slot copies a complete object group, including local clocks and
internal references. This is a cost/determinism fixture, not a musical score.
"""

import argparse
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from examples.scene_cues import build as word_backgrounds
from examples.scene_fragments import build as fragments
from examples.scene_gradient import build as gradient
from examples.scene_lyric_cues import build as cues
from examples.scene_lyrics import build as lyrics
from examples.scene_morph import build as morph
from examples.scene_outlines import build as outlines
from examples.scene_round import build as round_text
from examples.scene_sakura import build as sakura
from examples.scene_staggered import build as staggered
from examples.scene_sweep import build as sweep
from examples.scene_writing import build as writing
from kara_templater import (
    Document,
    Lifetime,
    NativeEvent,
    ObjectGroup,
    Scene,
    SceneBudget,
)


@dataclass(frozen=True)
class Case:
    id: str
    name: str
    factory: Callable[[], Scene]


CASES = (
    Case("E01", "lyrics", lyrics),
    Case("E02", "staggered", staggered),
    Case("E03", "round", round_text),
    Case("E04", "sakura", sakura),
    Case("E05", "fragments", fragments),
    Case("E06", "word-backgrounds", word_backgrounds),
    Case("E07", "outlines", outlines),
    Case("E08", "writing", writing),
    Case("E09", "gradient", gradient),
    Case("E10", "morph", morph),
    Case("E11", "sweep", sweep),
    Case("E12", "lyric-cues", cues),
)
SLOT_SECONDS = 6
SLOTS = 30
BUDGET = SceneBudget(max_events=250_000, max_bytes=100 * 1024 * 1024, max_active=2_000)


def build() -> Scene:
    templates: list[ObjectGroup] = []
    for case in CASES:
        source = case.factory()
        if any(isinstance(node, NativeEvent) for node in source.objects):
            raise ValueError(f"{case.id}: whole-song fixture requires editable objects")
        templates.append(
            ObjectGroup(
                id=case.name,
                lifetime=Lifetime(0, SLOT_SECONDS),
                children=tuple(
                    node for node in source.objects if not isinstance(node, NativeEvent)
                ),
            )
        )
    scene = Scene(Document.create(), owner="whole-song")
    for slot in range(SLOTS):
        template = templates[slot % len(templates)]
        scene.add(
            template.copy(id=f"slot:{slot:02}:{template.id}", delay=slot * SLOT_SECONDS)
        )
    return scene


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    result = build().compile(budget=BUDGET)
    result.document.save(parser.parse_args().output)
    print(
        f"{result.event_count} events, {result.peak_active} active, {result.byte_count} bytes"
    )


if __name__ == "__main__":
    main()
