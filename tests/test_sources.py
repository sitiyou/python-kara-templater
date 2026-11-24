import pytest

from kara_templater import SourceRef


@pytest.mark.parametrize(
    "args", [("",), ("x", -1), ("x", True), ("x", None, 0), ("x", 0, 1.5)]
)
def test_invalid_reference(args):
    with pytest.raises(ValueError):
        SourceRef(*args)
