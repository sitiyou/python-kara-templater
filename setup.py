import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from setuptools import Extension, setup
from setuptools.command.build_ext import build_ext

ROOT = Path(__file__).parent.resolve()
DEPS = ["freetype2", "harfbuzz", "fribidi", "fontconfig"]
WGSL_COMPILER = "_kara_wgsl.exe" if sys.platform == "win32" else "_kara_wgsl"


class NativeBuild(build_ext):
    def run(self):
        super().run()
        target = Path(self.build_temp).resolve() / "wgsl"
        cargo = [
            "cargo", "rustc", "--locked", "--release", "--target-dir", str(target),
            "--manifest-path", str(ROOT / "native/wgsl/Cargo.toml"),
        ]
        if sys.platform == "win32":
            # The translator is a separate process with its own DLL search path.
            cargo.extend(("--", "-C", "target-feature=+crt-static"))
        subprocess.run(cargo, check=True)
        compiler = target / "release" / ("kara-wgsl.exe" if sys.platform == "win32" else "kara-wgsl")
        output = Path(self.build_lib) / "kara_templater" / WGSL_COMPILER
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(compiler, output)
        if self.inplace:
            shutil.copy2(compiler, ROOT / "kara_templater" / WGSL_COMPILER)

    def get_outputs(self):
        return [*super().get_outputs(), str(Path(self.build_lib) / "kara_templater" / WGSL_COMPILER)]

    def build_extensions(self):
        if sys.platform == "win32":
            self.build_windows(Path(self.build_temp).resolve())
            return
        cflags = shlex.split(
            subprocess.check_output(["pkg-config", "--cflags", *DEPS], text=True)
        )
        ldflags = shlex.split(
            subprocess.check_output(["pkg-config", "--libs", *DEPS], text=True)
        )
        for ext in self.extensions:
            ext.extra_compile_args.extend(cflags)
            ext.extra_link_args.extend(ldflags)
        super().build_extensions()

    def build_windows(self, build):
        project = build / "native"
        project.mkdir(parents=True, exist_ok=True)
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
        (module,) = output.glob("_text_native*.pyd")
        target = Path(self.get_ext_fullpath("kara_templater._text_native"))
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(module, target)


setup(
    ext_modules=[
        Extension(
            "kara_templater._text_native",
            ["native/metrics.cpp"],
            language="c++",
            extra_compile_args=["-std=c++17"],
        )
    ],
    cmdclass={"build_ext": NativeBuild},
)
