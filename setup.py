import hashlib
import os
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from setuptools import Extension, setup
from setuptools.command.build_ext import build_ext

ROOT = Path(__file__).parent.resolve()
DEPS = ["freetype2", "harfbuzz", "fribidi", "fontconfig", "libpng"]


def native_build_key(root=ROOT):
    digest = hashlib.sha256()
    digest.update(f"{sys.platform}:{sys.implementation.cache_tag}".encode())
    inputs = [
        root / "vendor/libass-0.17.5.tar.gz",
        *sorted((root / "vendor").glob("*.patch")),
        *(
            root / "native" / name
            for name in ("metrics.cpp", "meson.build", "meson.options")
        ),
    ]
    for path in inputs:
        digest.update(str(path.relative_to(root)).encode() + b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()[:20]


class NativeBuild(build_ext):
    def build_extensions(self):
        build = Path(self.build_temp).resolve() / native_build_key()
        self.build_temp = str(build)
        # The output .so/.pyd keeps its public filename even when its native
        # input key changes. Re-link it against this key's archive, never an old
        # timestamp-only extension cache. libass itself remains incremental.
        self.force = True
        build.mkdir(parents=True, exist_ok=True)
        source = build / "libass-0.17.5"
        if sys.platform == "win32":
            source = build / "native" / "subprojects" / "libass-0.17.5"
        source.parent.mkdir(parents=True, exist_ok=True)
        if not source.exists():
            # Publish a source cache only after every patch succeeds. A failed
            # patch must not leave a partially patched cache for the next run.
            with tempfile.TemporaryDirectory(dir=source.parent) as staging:
                with tarfile.open(ROOT / "vendor/libass-0.17.5.tar.gz") as archive:
                    archive.extractall(staging, filter="data")
                staged_source = Path(staging) / "libass-0.17.5"
                for patch in sorted((ROOT / "vendor").glob("*.patch")):
                    with patch.open("rb") as stream:
                        subprocess.run(
                            ["patch", "-p1"],
                            stdin=stream,
                            cwd=staged_source,
                            check=True,
                        )
                staged_source.rename(source)
        if sys.platform == "win32":
            self.build_windows(build)
            return
        if not (source / "configure").exists():
            subprocess.run(["sh", "autogen.sh"], cwd=source, check=True)
        subprocess.run(
            [
                "sh",
                "configure",
                "--disable-shared",
                "--enable-static",
                "--with-pic",
                "--enable-fontconfig",
                "--disable-libunibreak",
                "--disable-test",
            ],
            cwd=source,
            check=True,
        )
        subprocess.run(
            ["make", f"-j{min(os.cpu_count() or 1, 8)}"], cwd=source, check=True
        )
        cflags = shlex.split(
            subprocess.check_output(["pkg-config", "--cflags", *DEPS], text=True)
        )
        ldflags = shlex.split(
            subprocess.check_output(["pkg-config", "--libs", *DEPS], text=True)
        )
        for ext in self.extensions:
            ext.include_dirs.append(str(source / "libass"))
            ext.extra_compile_args.extend(cflags)
            ext.extra_objects.append(str(source / "libass/.libs/libass.a"))
            ext.extra_link_args.extend([*ldflags, "-lm", "-Wl,--exclude-libs,ALL"])
        super().build_extensions()

    def build_windows(self, build):
        project = build / "native"
        for name in ("meson.build", "meson.options", "metrics.cpp"):
            shutil.copy2(ROOT / "native" / name, project / name)
        output = build / "meson"
        env = {**os.environ, "CC": "gcc", "CXX": "g++"}
        subprocess.run(
            [
                "meson",
                "setup",
                "--reconfigure",
                str(output),
                str(project),
                f"-Dpython={sys.executable}",
            ],
            env=env,
            check=True,
        )
        subprocess.run(["meson", "compile", "-C", str(output)], env=env, check=True)
        (module,) = output.glob("_metrics*.pyd")
        target = Path(self.get_ext_fullpath("kara_templater._metrics"))
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(module, target)


setup(
    ext_modules=[
        Extension(
            "kara_templater._metrics",
            ["native/metrics.cpp"],
            language="c++",
            extra_compile_args=["-std=c++17"],
        )
    ],
    cmdclass={"build_ext": NativeBuild},
)
