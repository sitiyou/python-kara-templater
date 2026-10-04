# Third-party sources

The Python template engine and C++ binding are newly written. The observable template interface was studied in Aegisub's `automation/autoload/kara-templater.lua`, `automation/include/karaskel-auto4.lua`, and karaoke parser. No Lua scripts or Lua runtime are included in this package.

Text measurement uses libass 0.17.5 under the ISC license. Its original source archive, license, and two metrics patches are included in `vendor/`:

- `libass-0.17.5.tar.gz`: https://github.com/libass/libass/releases/tag/0.17.5
- `001-libass-metrics-api.patch`: experimental metrics API associated with https://github.com/libass/libass/pull/856
- `002-libass-metrics-crashfix.patch`: metrics lifetime and empty-event corrections distributed with aegisub-karaskel-fix.
- `LICENSE.libass`: the upstream libass license.

The native build compiles the bundled patched libass statically; Linux hides its symbols. It does not replace or link against the system libass. FreeType, HarfBuzz, and FriBidi are shared dependencies. Linux also uses Fontconfig and libpng; Windows uses the system DirectWrite/GDI font provider instead of Fontconfig.

Release wheels bundle non-system shared dependencies using auditwheel or delvewheel. Their upstream licenses are included under `vendor/runtime-licenses/` in distribution license metadata; the project's MIT license does not replace these licenses. These include FriBidi's LGPL license and the GCC runtime licenses and exceptions when those libraries are bundled. Dependency source packages are available through the MSYS2 and distribution repositories listed in `vendor/runtime-licenses/NOTICE.txt`. Source installs use separately installed native dependencies. Building libass itself uses the bundled source without downloading it.

The C++ binding consumes run advances, ascent, and descent from `ass_get_metrics`. No bitmap-boundary scanning is used. Non-breaking spaces retain edge-space advances; hard breaks are measured as separate rows. The metrics API is experimental and pinned to the bundled version.

Build requirements are setuptools, Python headers, a C/C++ toolchain, pkg-config, patch, and the native dependencies listed above. Linux uses Autoconf, Automake, and libtool; Windows uses MSYS2 UCRT64, Meson, and Ninja. NASM enables libass's x86 assembly optimizations. The renderer stays inside the extension module and measurements hold the Python GIL. Build and publication configuration is documented in `docs/releasing.md`.

Run verification with:

```sh
python -m unittest discover -s tests -v
```
