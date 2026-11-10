"""Optional extra font resources for the native measurement renderer.

Styles select their own font families; registration adds available resources
without selecting a global font or changing any style.
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path

from . import _metrics


@dataclass(frozen=True)
class LoadedFont:
    family: str
    sha256: str


_loaded: dict[str, LoadedFont] = {}


def load_font(path: str | Path) -> LoadedFont:
    """Make an extra font file available to this interpreter's metrics renderer.

    Each style still selects its font by family name via ``Style.fontname``.
    This does not set a global font or bind a style to a specific font file.
    Registration persists for this interpreter. Duplicate bytes are loaded once.
    ASS playback/rendering must be configured with the same font separately.
    """
    data = Path(path).read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest not in _loaded:
        family = _metrics.add_font(digest, data)
        _loaded[digest] = LoadedFont(family, digest)
    return _loaded[digest]
