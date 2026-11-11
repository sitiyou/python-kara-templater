"""Assertions for source metadata attached to rendered objects and exceptions."""

from kara_templater import EventOrigin


def require_origin(value: object) -> EventOrigin:
    origin = getattr(value, "origin", None)
    assert isinstance(origin, EventOrigin)
    return origin
