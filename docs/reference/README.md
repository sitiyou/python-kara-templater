# API reference

Complete signatures, fields, defaults, and docstrings for every public symbol exported by kara_templater.

Every symbol listed here is importable directly from `kara_templater`; topic pages group related types without changing their import path. For step-by-step workflows, start with [Core concepts](../concepts.md), the [tutorials](../tutorials/README.md), or the [authoring guides](../guides/README.md).

> [!NOTE]
> This reference is generated from the package exports with `python -m tools.generate_reference`. Run with `--check` to verify committed pages match the current API.

## Topics

| Topic | Covers | Symbols |
| --- | --- | --- |
| [Documents and lyric input](documents.md) | Records, decoded lyric text, input selection, and source mappings. Raw line clocks use milliseconds; lyric timing spans use seconds. | 21 |
| [Track authoring](tracks.md) | Independent vocal streams, row layout, and built-in karaoke effects assembled into a Scene. Timing, display, and animation clocks use seconds. | 38 |
| [Text measurement and layout](text.md) | Font registration, shaped glyph metrics, source clusters, and body/ruby binding. | 19 |
| [Scenes and compilation](scenes.md) | Scene objects, world-space evaluation, real-time browser preview, and shader and ASS export. Lifetimes use seconds. Geometry uses script pixels. | 20 |
| [Animation and timing](animation.md) | Pure state and property animation, easing curves, and typed composition on second-based clocks. | 35 |
| [Colors and appearance](paint.md) | RGB colors, fills, outlines, spatial paint fields, WGSL materials, and lyric highlight styles. | 36 |
| [Geometry and paths](geometry.md) | Script-space vectors, clips, masks, path boolean operations, deformation, extrusion, and morphing. | 32 |
| [Lyric cues](cues.md) | Count-ins, reservations, independent cue tracks, and inline lyric markers measured in seconds. | 13 |
| [Particles and references](particles.md) | Deterministic particle emitters, delayed copies, echoes, and world-space object references. | 14 |
| [Raster previews](native.md) | Raster preview capability errors and display windows in absolute milliseconds. | 2 |

## Symbol index

230 public exports grouped alphabetically.

### A

[`Affine2D`](geometry.md#affine2d) · [`Animation`](animation.md#animation) · [`AnimationClip`](animation.md#animationclip) · [`AnimationSequence`](animation.md#animationsequence) · [`AssBudget`](scenes.md#assbudget) · [`AssDialogue`](scenes.md#assdialogue) · [`AssEstimate`](scenes.md#assestimate) · [`AssObjectReport`](scenes.md#assobjectreport) · [`AssResult`](scenes.md#assresult)

### B

[`BackRate`](animation.md#backrate) · [`BarsCue`](cues.md#barscue) · [`bind_cues`](cues.md#bind_cues) · [`bind_lyric_cues`](cues.md#bind_lyric_cues) · [`BLACK`](paint.md#black) · [`BLUE`](paint.md#blue) · [`Box`](geometry.md#box) · [`build_lyric_scene`](tracks.md#build_lyric_scene)

### C

[`Canvas`](animation.md#canvas) · [`Channel`](animation.md#channel) · [`CharacterTarget`](text.md#charactertarget) · [`Color`](paint.md#color) · [`ColorRamp`](paint.md#colorramp) · [`ColorStop`](paint.md#colorstop) · [`component_catalog`](tracks.md#component_catalog) · [`component_preview_resource`](tracks.md#component_preview_resource) · [`ComponentCardData`](tracks.md#componentcarddata) · [`ComponentCatalog`](tracks.md#componentcatalog) · [`ComponentParameter`](tracks.md#componentparameter) · [`ComponentParameterData`](tracks.md#componentparameterdata) · [`ComponentSelection`](tracks.md#componentselection) · [`ComponentTarget`](tracks.md#componenttarget) · [`ComponentValue`](tracks.md#componentvalue) · [`compose_track`](tracks.md#compose_track) · [`Contour`](geometry.md#contour) · [`CubicSegment`](geometry.md#cubicsegment) · [`CueContent`](cues.md#cuecontent) · [`CueContext`](cues.md#cuecontext) · [`CuedLayout`](cues.md#cuedlayout) · [`CuedLyrics`](cues.md#cuedlyrics) · [`CueFactory`](cues.md#cuefactory) · [`CueMarker`](documents.md#cuemarker) · [`CuePlacement`](cues.md#cueplacement) · [`CuePreset`](cues.md#cuepreset) · [`CurveIn`](animation.md#curvein) · [`CYAN`](paint.md#cyan)

### D

[`DisplayWindow`](native.md#displaywindow) · [`Document`](documents.md#document) · [`DocumentLyrics`](documents.md#documentlyrics) · [`DocumentText`](documents.md#documenttext) · [`DrawableCharacter`](text.md#drawablecharacter) · [`DriftOut`](animation.md#driftout)

### E

[`ease_in`](animation.md#ease_in) · [`ease_in_out`](animation.md#ease_in_out) · [`ease_out`](animation.md#ease_out) · [`echoes`](particles.md#echoes) · [`effect_components`](tracks.md#effect_components) · [`EffectComponent`](tracks.md#effectcomponent) · [`EffectComponentData`](tracks.md#effectcomponentdata) · [`Emission`](particles.md#emission) · [`emit_particles`](particles.md#emit_particles) · [`EventOrigin`](documents.md#eventorigin) · [`Extrusion`](paint.md#extrusion)

### F

[`FadeIn`](animation.md#fadein) · [`FadeOut`](animation.md#fadeout) · [`flatten`](geometry.md#flatten) · [`FollowObject`](particles.md#followobject) · [`FontFace`](text.md#fontface)

### G

[`GeometryAnimation`](geometry.md#geometryanimation) · [`GeometryError`](geometry.md#geometryerror) · [`Glow`](paint.md#glow) · [`Glyph`](animation.md#glyph) · [`GRAY`](paint.md#gray) · [`GREEN`](paint.md#green)

### H

[`Highlight`](paint.md#highlight) · [`HighlightArrival`](paint.md#highlightarrival) · [`HighlightPass`](paint.md#highlightpass)

### I

[`intersect_convex`](geometry.md#intersect_convex)

### J

[`Jump`](animation.md#jump)

### K

[`KaraokeDecoration`](tracks.md#karaokedecoration) · [`KaraokeEffects`](tracks.md#karaokeeffects) · [`KaraokeEntry`](tracks.md#karaokeentry) · [`KaraokeExit`](tracks.md#karaokeexit) · [`KaraokeHighlight`](tracks.md#karaokehighlight) · [`KaraokeRows`](tracks.md#karaokerows) · [`KaraokeTheme`](paint.md#karaoketheme)

### L

[`Layout`](tracks.md#layout) · [`layout_characters`](text.md#layout_characters) · [`layout_document_lyrics`](text.md#layout_document_lyrics) · [`layout_document_text`](text.md#layout_document_text) · [`layout_lyrics`](text.md#layout_lyrics) · [`layout_path`](geometry.md#layout_path) · [`LayoutCapabilityError`](text.md#layoutcapabilityerror) · [`LayoutContext`](tracks.md#layoutcontext) · [`LengthExpr`](animation.md#lengthexpr) · [`Lifetime`](scenes.md#lifetime) · [`Line`](documents.md#line) · [`linear_rate`](animation.md#linear_rate) · [`LinearGradient`](paint.md#lineargradient) · [`LineLayoutRequest`](tracks.md#linelayoutrequest) · [`LineSegment`](geometry.md#linesegment) · [`load_font`](text.md#load_font) · [`LoadedFont`](text.md#loadedfont) · [`lyric_effects`](tracks.md#lyric_effects) · [`LyricAnchor`](tracks.md#lyricanchor) · [`LyricAnimationContext`](tracks.md#lyricanimationcontext) · [`LyricEcho`](tracks.md#lyricecho) · [`LyricEffect`](tracks.md#lyriceffect) · [`LyricGlow`](paint.md#lyricglow) · [`LyricGradient`](paint.md#lyricgradient) · [`LyricHighlights`](paint.md#lyrichighlights) · [`LyricLayout`](text.md#lyriclayout) · [`LyricLine`](tracks.md#lyricline) · [`LyricLinePlan`](tracks.md#lyriclineplan) · [`LyricMapping`](documents.md#lyricmapping) · [`LyricParticles`](particles.md#lyricparticles) · [`LyricRole`](tracks.md#lyricrole) · [`LyricRule`](tracks.md#lyricrule) · [`LyricScene`](tracks.md#lyricscene) · [`LyricSegment`](documents.md#lyricsegment) · [`LyricSource`](tracks.md#lyricsource) · [`LyricSweep`](paint.md#lyricsweep) · [`LyricTarget`](tracks.md#lyrictarget) · [`LyricUnit`](documents.md#lyricunit)

### M

[`MAGENTA`](paint.md#magenta) · [`MaterialClip`](paint.md#materialclip) · [`MaterialEffect`](paint.md#materialeffect) · [`merge_geometry`](geometry.md#merge_geometry) · [`morph`](geometry.md#morph) · [`MorphPath`](geometry.md#morphpath) · [`MoveAlong`](geometry.md#movealong)

### N

[`Note`](animation.md#note)

### O

[`ObjectGroup`](scenes.md#objectgroup) · [`ORANGE`](paint.md#orange) · [`outline_text`](geometry.md#outline_text) · [`OutputCapabilityError`](native.md#outputcapabilityerror)

### P

[`Paint`](paint.md#paint) · [`paint_pair_from_style`](paint.md#paint_pair_from_style) · [`PaintControl`](paint.md#paintcontrol) · [`PaintInput`](paint.md#paintinput) · [`PaintPair`](paint.md#paintpair) · [`PaintValue`](paint.md#paintvalue) · [`parse_document_lyrics`](documents.md#parse_document_lyrics) · [`ParticleContext`](particles.md#particlecontext) · [`ParticleFactory`](particles.md#particlefactory) · [`path_boolean`](geometry.md#path_boolean) · [`path_bounds`](geometry.md#path_bounds) · [`PathBooleanOperation`](geometry.md#pathbooleanoperation) · [`PathFunction`](geometry.md#pathfunction) · [`PathItem`](geometry.md#pathitem) · [`PathObject`](scenes.md#pathobject) · [`Petal`](particles.md#petal) · [`PINK`](paint.md#pink) · [`Placement`](tracks.md#placement) · [`Polyline`](geometry.md#polyline) · [`PositionedRuby`](text.md#positionedruby) · [`PositionedText`](text.md#positionedtext) · [`PreparedHook`](scenes.md#preparedhook) · [`ProgressCurve`](animation.md#progresscurve) · [`PURPLE`](paint.md#purple)

### R

[`read_document_text`](documents.md#read_document_text) · [`Record`](documents.md#record) · [`RectangleClip`](scenes.md#rectangleclip) · [`RectangleFunction`](scenes.md#rectanglefunction) · [`RectangleKeyframes`](scenes.md#rectanglekeyframes) · [`RED`](paint.md#red) · [`ReferenceFunction`](particles.md#referencefunction) · [`Region`](geometry.md#region) · [`resample_path`](geometry.md#resample_path) · [`Ribbon`](particles.md#ribbon) · [`RubyText`](documents.md#rubytext)

### S

[`ScalePulse`](animation.md#scalepulse) · [`ScatterOut`](tracks.md#scatterout) · [`Scene`](scenes.md#scene) · [`SceneCompileError`](scenes.md#scenecompileerror) · [`SceneEvaluator`](scenes.md#sceneevaluator) · [`SceneObject`](scenes.md#sceneobject) · [`SceneReferenceError`](scenes.md#scenereferenceerror) · [`SecondaryOutline`](paint.md#secondaryoutline) · [`select_characters`](text.md#select_characters) · [`ShaderMotion`](animation.md#shadermotion) · [`ShaderPaint`](paint.md#shaderpaint) · [`SignalCue`](cues.md#signalcue) · [`Slide`](animation.md#slide) · [`smooth_rate`](animation.md#smooth_rate) · [`smoother_rate`](animation.md#smoother_rate) · [`SourceRef`](documents.md#sourceref) · [`Sparkle`](particles.md#sparkle) · [`split_path`](particles.md#split_path) · [`StateAnimation`](animation.md#stateanimation) · [`StateFunction`](animation.md#statefunction) · [`StateKeyframe`](animation.md#statekeyframe) · [`StateLookup`](particles.md#statelookup) · [`StatePatch`](animation.md#statepatch) · [`StateReference`](particles.md#statereference) · [`stroke`](geometry.md#stroke) · [`StudioSpacing`](text.md#studiospacing) · [`Style`](documents.md#style)

### T

[`text_extents`](text.md#text_extents) · [`text_to_path`](geometry.md#text_to_path) · [`TextAppearance`](documents.md#textappearance) · [`TextCue`](cues.md#textcue) · [`TextIssue`](documents.md#textissue) · [`TextLayout`](text.md#textlayout) · [`TextObject`](scenes.md#textobject) · [`TextOutline`](geometry.md#textoutline) · [`TextRange`](text.md#textrange) · [`TextRun`](documents.md#textrun) · [`TextToken`](documents.md#texttoken) · [`there_and_back`](animation.md#there_and_back) · [`TimedTextSpan`](documents.md#timedtextspan) · [`TimeExpr`](animation.md#timeexpr) · [`Timeline`](animation.md#timeline) · [`TimeSpan`](animation.md#timespan) · [`TimingTag`](documents.md#timingtag) · [`Track`](tracks.md#track) · [`TrailPath`](geometry.md#trailpath) · [`Transform`](animation.md#transform) · [`Tween`](animation.md#tween)

### U

[`union_regions`](geometry.md#union_regions)

### V

[`Vec2`](geometry.md#vec2) · [`VectorClip`](scenes.md#vectorclip) · [`VectorGuide`](text.md#vectorguide) · [`VectorPath`](geometry.md#vectorpath) · [`VisualNode`](scenes.md#visualnode) · [`VisualState`](animation.md#visualstate) · [`VolumeCue`](cues.md#volumecue)

### W

[`WHITE`](paint.md#white) · [`WritePath`](geometry.md#writepath) · [`WritingStroke`](geometry.md#writingstroke)

### Y

[`YELLOW`](paint.md#yellow)
