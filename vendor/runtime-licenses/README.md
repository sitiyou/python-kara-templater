# Fixed native dependency notices

These are version-controlled license-text snapshots for the native runtime DLLs
in the reviewed Windows bundle. Builds include these files directly; they do not
scan the host or collect licenses automatically. Linux host-linked libraries are supplied by
the operating system.

The Fontconfig and Expat COPYING files accompany the Windows font provider and XML parser.

Update this collection manually when changing dependency versions or bundled
DLLs. The source texts were copied verbatim from the following MSYS2 UCRT64
package archives; GCC runtime texts are shared by libgcc and libstdc++.

| Directory | MSYS2 component | Package version |
| --- | --- | --- |
| `brotli` | `brotli` | `1.2.1-1` |
| `bzip2` | `bzip2` | `1.0.8-4` |
| `freetype` | `freetype` | `2.15.0-1` |
| `fribidi` | `fribidi` | `1.0.18-1` |
| `gcc-runtime` | `libgcc / libstdc++` | `16.2.0-7` |
| `gettext-runtime` | `gettext-runtime` | `1.0-1` |
| `glib` | `glib2` | `2.90.1-1` |
| `graphite` | `graphite2` | `1.3.15-1` |
| `harfbuzz` | `harfbuzz` | `15.1.0-1` |
| `iconv` | `libiconv` | `1.19.1-1` |
| `libpng` | `libpng` | `1.6.59-2` |
| `pcre2` | `pcre2` | `10.49-2` |
| `winpthreads` | `libwinpthread` | `14.0.0.r598.ge3d18511f-1` |
| `zlib` | `zlib` | `1.4-2` |

Package archive prefix: `mingw-w64-ucrt-x86_64-`; suffix: `-any.pkg.tar.zst`.
The GCC libstdc++ archive uses the same package version as libgcc.

Sources: [MSYS2 package repository](https://repo.msys2.org/mingw/ucrt64/),
[MSYS2 build recipes](https://github.com/msys2/MINGW-packages).

These notices preserve upstream license texts. Dependency redistribution must
also follow the applicable upstream terms, including corresponding-source and
runtime-exception provisions where relevant.
