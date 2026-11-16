import pytest

from kara_templater.composition import Color, Glow, Paint


def test_rgb_and_appearance_validation():
    assert Color.hex("#0123ff") == Color(1, 35, 255)
    for value in ("112233", "#zz2233", "#123", "# 12345"):
        with pytest.raises(ValueError):
            Color.hex(value)
    with pytest.raises(ValueError):
        Paint(opacity=2)
    with pytest.raises(ValueError):
        Glow(blur=-1)
