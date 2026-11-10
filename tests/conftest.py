from pathlib import Path

from kara_templater.fonts import load_font


def pytest_configure(config):
    font = load_font(Path(__file__).parent / "fonts/DejaVuSans.ttf")
    assert (
        font.sha256
        == "6038a160b491e121c1f12c7bccb4a9c8730296e3adc1086a059404ed84b7451c"
    )
