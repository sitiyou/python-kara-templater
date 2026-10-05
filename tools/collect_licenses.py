import shutil
import sys
from pathlib import Path

LINUX_PACKAGES = (
    "brotli",
    "bzip2-libs",
    "expat",
    "fontconfig",
    "freetype",
    "fribidi",
    "gcc",
    "glib2",
    "graphite2",
    "harfbuzz",
    "libgcc",
    "libpng",
    "libuuid",
    "pcre2",
    "zlib",
)
WINDOWS_PACKAGES = {
    "brotli": "brotli",
    "bzip2": "bzip2",
    "freetype": "freetype",
    "fribidi": "fribidi",
    "gcc": "gcc",
    "gettext-runtime": "gettext-runtime",
    "glib2": "glib2",
    "graphite2": "graphite2",
    "harfbuzz": "harfbuzz",
    "libgcc": "libgcc",
    "libiconv": "libiconv",
    "libpng": "libpng",
    "libstdc++": "libstdcxx",
    "libwinpthread": "libwinpthread",
    "pcre2": "pcre2",
    "zlib": "zlib",
}


def collect(source, destination, platform):
    if platform == "win32":
        packages = WINDOWS_PACKAGES
    elif platform.startswith("linux"):
        packages = {name: name for name in LINUX_PACKAGES}
    else:
        raise SystemExit(f"Unsupported platform: {platform}")

    if not source.is_dir():
        raise SystemExit(f"Native dependency licenses not found: {source}")

    destination.mkdir(parents=True, exist_ok=True)
    for path in destination.iterdir():
        if path.name == "NOTICE.txt":
            continue
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()

    for package, target in packages.items():
        package_licenses = source / package
        if not package_licenses.is_dir():
            raise SystemExit(f"License directory not found: {package_licenses}")
        shutil.copytree(
            package_licenses,
            destination / target,
            ignore_dangling_symlinks=True,
        )


def main():
    root = Path(__file__).resolve().parents[1]
    if sys.platform == "win32":
        gcc = shutil.which("gcc")
        if gcc is None:
            raise SystemExit("GCC not found; cannot locate MSYS2 license files")
        source = Path(gcc).resolve().parents[1] / "share" / "licenses"
    else:
        source = Path("/usr/share/licenses")
    collect(source, root / "vendor" / "runtime-licenses", sys.platform)


if __name__ == "__main__":
    main()
