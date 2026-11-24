"""The example's marker lands on the measured syllable at each note attack."""

import pytest

from examples.lyric_no_sweep import PHRASES, build
from kara_templater import LyricLine, PathObject


def test_marker_lands_over_each_syllable_at_its_attack() -> None:
    scene = build()
    poses = scene.evaluator()
    lines = [obj for obj in scene.objects if isinstance(obj, LyricLine)]
    markers = {obj.id: obj for obj in scene.objects if isinstance(obj, PathObject)}

    assert len(lines) == len(markers) == len(PHRASES)
    for line, phrase in zip(lines, PHRASES, strict=True):
        marker = markers[f"{line.id}/note-marker"]
        syllables = line.query("syllable")
        assert len(syllables) == len(phrase.text)
        assert marker.lifetime.start == syllables[0].singing[0].start
        assert marker.lifetime.end == syllables[-1].singing[-1].end
        for syllable in syllables:
            onset = syllable.singing[0].start
            target = poses.at(syllable.node_id, onset).transform.apply(syllable.center)
            cue = poses.at(marker.id, onset).position
            assert cue.x == pytest.approx(target.x)
            assert cue.y < target.y
