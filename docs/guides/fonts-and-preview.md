# Fonts and preview

Text metrics and glyph geometry depend on the actual selected font, fallback,
and shaping environment. Keep font selection consistent between compilation and
playback when comparing layout or pixels.

## Register and select a font

`load_font(path)` makes that font's bytes available to the current interpreter's
native metrics renderer. It returns LoadedFont with family and SHA-256 metadata.
Select the family through Style.fontname, TextStyle.font_name, or TextObject.font.
Registration does not select a global font or embed it into every output ASS.
Duplicate font bytes are registered once per interpreter.

The playback application must also receive the font. Install the font, attach it
through your delivery container, or configure the preview renderer's font path.
A fallback can change advances, outlines, line positions, and supported glyphs.
Reported font-face names are diagnostics, not proof of identical file bytes.

The repository includes small fixed test fonts with separate licenses. Examples
that use them load bytes from tests/fonts while building. Those paths require a
checkout or source distribution; they are not wheel-installed example assets.

## Render the exported ASS

The gallery tool first saves ASS, then asks FFmpeg/libass to render that file:

```sh
python -m tools.render_gallery --case sweep
```

Run it from a checkout with FFmpeg/libass and the checks dependencies installed.
It writes ASS, copied preview fonts, and a provenance report under build/gallery,
and creates the selected GIF under docs/examples/assets. Omit --case to rebuild
the complete twelve-effect gallery. Override --output or --assets for a local
experiment without replacing tracked previews.

For detailed continuous-playback and seek checks of a particular example:

```sh
python -m tools.validate_scene_core --scene sweep build/preview-sweep
```

This writes its generated ASS and diagnostic report to the requested output
directory. It checks a fixed example in the configured libass environment; it
does not establish equivalent rendering in every player.

For ordinary playback, load the saved ASS in your target player and inspect
entrance, singing transitions, repeated highlights, and exit. For pixel-level
comparisons, keep resolution, fonts, timestamp, background, color matrix, and
RGB/chroma composition settings fixed. See [ASS and playback](../ass-and-playback.md).
