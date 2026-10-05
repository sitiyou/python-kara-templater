# Third-party sources

The Python template engine and C++ binding are newly written. The observable template interface was studied in Aegisub's `automation/autoload/kara-templater.lua`, `automation/include/karaskel-auto4.lua`, and karaoke parser. No Lua scripts or Lua runtime are included in this package.

Text measurement uses libass 0.17.5 under the ISC license. Its original source archive, license, and two metrics patches are included in `vendor/`:

- `libass-0.17.5.tar.gz`: https://github.com/libass/libass/releases/tag/0.17.5
- `001-libass-metrics-api.patch`: experimental metrics API associated with https://github.com/libass/libass/pull/856
- `002-libass-metrics-crashfix.patch`: metrics lifetime and empty-event corrections distributed with aegisub-karaskel-fix.
- `LICENSE.libass`: the upstream libass license.

The native build compiles the bundled patched libass statically; Linux hides its symbols. It does not replace or link against the system libass. FreeType, HarfBuzz, and FriBidi are shared dependencies. Linux also uses Fontconfig and libpng; Windows uses the system DirectWrite/GDI font provider instead of Fontconfig.

Windows release wheels bundle their shared DLL dependencies using delvewheel. Linux wheels dynamically link against the system's FreeType, HarfBuzz, FriBidi, Fontconfig, libpng, and C++ runtime libraries; those runtime packages must be installed by the user. The project's MIT license does not replace the licenses of linked libraries. Their license texts are included under `vendor/runtime-licenses/` in distribution metadata. Dependency source packages are available through the MSYS2 and distribution repositories listed in `vendor/runtime-licenses/NOTICE.txt`. Building libass itself uses the bundled source without downloading it.

The C++ binding consumes run advances, ascent, and descent from `ass_get_metrics`. No bitmap-boundary scanning is used. Non-breaking spaces retain edge-space advances; hard breaks are measured as separate rows. The metrics API is experimental and pinned to the bundled version.

Build requirements are setuptools, Python headers, a C/C++ toolchain, pkg-config, patch, and the native dependencies listed above. Linux uses Autoconf, Automake, and libtool; Windows uses MSYS2 UCRT64, Meson, and Ninja. NASM enables libass's x86 assembly optimizations. The renderer stays inside the extension module and measurements hold the Python GIL. Build and publication configuration is documented in `docs/releasing.md`.

Run verification with:

```sh
python -m unittest discover -s tests -v
```
