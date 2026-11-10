import os
import runpy
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def build_key(tmp_path):
    with patch("setuptools.setup"):
        namespace = runpy.run_path(
            str(Path(__file__).resolve().parents[1] / "setup.py")
        )
    for name in (
        "vendor/libass-0.17.5.tar.gz",
        "vendor/001.patch",
        "native/metrics.cpp",
        "native/meson.build",
        "native/meson.options",
    ):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"original input")
    return namespace["native_build_key"], tmp_path


@pytest.mark.parametrize(
    "name",
    [
        "vendor/libass-0.17.5.tar.gz",
        "vendor/001.patch",
        "native/metrics.cpp",
        "native/meson.build",
        "native/meson.options",
    ],
)
def test_native_cache_uses_content_not_timestamps(build_key, name):
    key, root = build_key
    original = key(root)
    path = root / name
    before = path.stat()
    path.write_bytes(b"modified input")
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert key(root) != original
    path.write_bytes(b"original input")
    assert key(root) == original


def test_adding_or_renaming_patch_invalidates_native_cache(build_key):
    key, root = build_key
    original = key(root)
    added = root / "vendor/002.patch"
    added.write_bytes(b"second patch")
    second = key(root)
    assert second != original
    added.rename(root / "vendor/003.patch")
    assert key(root) != second
