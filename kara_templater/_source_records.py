"""Read source records and recognize this project's generated ASS events."""

from dataclasses import replace
from urllib.parse import quote, unquote

from .ass import Line, Style
from .scene import SceneCompileError


def strip_generated_records(
    records: list[str | Style | Line],
    prefix: str,
    replace_records: set[int],
) -> list[str | Style | Line]:
    """Strip owned output pairs before any importer removes their Dialogue."""
    retained: list[str | Style | Line] = []
    skip_native = False
    for index, record in enumerate(records):
        if skip_native:
            if not isinstance(record, Line) or record.comment:
                raise SceneCompileError("damaged native-event provenance marker")
            skip_native = False
            continue
        if isinstance(record, Line) and record.effect.startswith(prefix):
            skip_native = record.comment and record.text == "kara native event follows"
            continue
        retained.append(
            replace(record, comment=True)
            if index in replace_records and isinstance(record, Line)
            else record
        )
    if skip_native:
        raise SceneCompileError("native-event provenance marker has no following event")
    return retained


SOURCE_PREFIX = "karaoke:source:v1:"
GENERATED_PREFIX = "kara:scene:v1:"


def generated_prefix(owner: str) -> str:
    return GENERATED_PREFIX + quote(owner, safe="") + ":"


def source_prefix(owner: str) -> str:
    return SOURCE_PREFIX + quote(owner, safe="") + ":"


def write_source_marker(owner: str, source_id: str, effect: str) -> str:
    return source_prefix(owner) + quote(source_id, safe="") + ":" + quote(effect, safe="")


def read_source_marker(marker: str, prefix: str, index: int) -> tuple[str, str]:
    identifier, separator, effect = marker[len(prefix):].partition(":")
    if not separator or not identifier:
        raise ValueError(f"record {index}: damaged lyric source marker")
    return unquote(identifier), unquote(effect)
