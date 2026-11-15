"""Keep native Track setup short in focused lowering and rendering tests."""

from kara_templater import prepare_tracks


def compile_tracks(document, items=None, *, budget=None, **kwargs):
    return prepare_tracks(document, items, mode="native", **kwargs).compile(
        budget=budget
    )
