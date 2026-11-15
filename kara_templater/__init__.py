from ._legacy_layout import LegacyLine, LegacySyllable, preprocess, split_karaoke
from .animation import (
    AnimationPlan,
    CharacterTarget,
    HighlightEnter,
    OffsetAnimation,
    OpacityAnimation,
    Pulse,
    ScaleAnimation,
    SegmentStart,
    SyllableStart,
    plan_pulses,
)
from .appearance import (
    CharacterPaint,
    ColorSpan,
    PaintPair,
    RubyPaint,
    resolve_paints,
    resolve_ruby_paints,
)
from .ass import Document, Line, Record, Style
from .ass_output import (
    ClipSpan,
    CompiledLayers,
    Fade,
    OutputCapabilityError,
    OutputSettings,
    TextLayer,
    compile_layers,
    sweep_spans,
)
from .behaviors import TargetSelection
from .characters import (
    DrawableCharacter,
    FontFace,
    LayoutCapabilityError,
    TextRange,
    layout_characters,
    select_characters,
)
from .choreography import Composition, MoveTo, OpacityTo, ScaleTo, Timeline, TransformTo
from .colors import (
    BLACK,
    BLUE,
    CYAN,
    GRAY,
    GREEN,
    MAGENTA,
    ORANGE,
    PINK,
    PURPLE,
    RED,
    WHITE,
    YELLOW,
)
from .components import Body, Component, Halo, Lyrics, Ruby
from .composition import (
    Color,
    Glow,
    Paint,
    PaintedRegion,
    TrackPaint,
    compose_highlights,
)
from .coverage_animation import CoveragePartition, GlowFunction, ScopeOpacity
from .coverage_output import CoverageResult, compile_coverage
from .cues import (
    BarsCue,
    CueContent,
    CueContext,
    CuedLayout,
    CuedLyrics,
    CueFactory,
    CuePlacement,
    CuePreset,
    TextCue,
    bind_cues,
    bind_lyric_cues,
)
from .document_lyrics import (
    DocumentLyrics,
    LyricMapping,
    LyricSegment,
    LyricUnit,
    RubyText,
    parse_document_lyrics,
)
from .document_text import (
    CueMarker,
    DocumentText,
    SingingTag,
    TextAppearance,
    TextIssue,
    TextRun,
    TextToken,
    read_document_text,
)
from .effect import Effect
from .engine import Engine, TemplateError, apply_templates
from .follow import Follow
from .fonts import LoadedFont, load_font
from .geometry import Affine2D, Contour, CubicSegment, LineSegment, Vec2, VectorPath
from .group_geometry import merge_geometry
from .import_ass import (
    AssImportError,
    ImportedKaraoke,
    ImportSettings,
    import_karaoke,
    paint_pair_from_style,
    parse_karaoke,
)
from .layout import layout_line, text_extents
from .matching import LineMatch, SourceMatch
from .material_animation import (
    ColorKeyframe,
    ColorKeyframes,
    ColorTransition,
    ColorValue,
    PaintBounds,
)
from .model import (
    Box,
    KaraokeLine,
    LaidOutLine,
    LaidOutSegment,
    LaidOutUnit,
    Segment,
    TextUnit,
)
from .motion import (
    Animate,
    Animation,
    AnimationContext,
    AnimationEvent,
    AnimationResult,
    AnimationTarget,
    Display,
    Envelope,
    FadeInAnimation,
    FadeOutAnimation,
    Milliseconds,
    On,
    Parallel,
    RateFunction,
    SegmentSinging,
    Sequence,
    SingingPulseAnimation,
    Syllable,
    TimeSpan,
    Transform,
    on,
)
from .object_references import (
    FollowObject,
    ReferenceFunction,
    StateLookup,
    StateReference,
)
from .paint_fields import (
    ColorRamp,
    ColorStop,
    LinearGradient,
    PaintBand,
    PaintField,
    SoftSweep,
)
from .particles import (
    Emission,
    ParticleContext,
    ParticleFactory,
    echoes,
    emit_particles,
    split_path,
)
from .path_animation import (
    GeometryAnimation,
    MorphPath,
    PathFunction,
    WritePath,
    WritingStroke,
)
from .path_boolean import PathBooleanOperation, path_boolean
from .path_geometry import (
    GeometryError,
    Polyline,
    flatten,
    intersect_convex,
    morph,
    path_bounds,
    resample_path,
    stroke,
)
from .path_layout import PathItem, layout_path
from .path_motion import MoveAlong
from .properties import (
    AnimatedProperties,
    CompositionMode,
    Contextual,
    Keyframe,
    Keyframes,
    ProgressMode,
    PropertyContext,
    PropertyTarget,
    PropertyValue,
    TimeInterval,
    TimeRef,
    Transition,
    display,
    ease_in,
    ease_in_out,
    ease_out,
    linear,
    singing,
    smooth,
    there_and_back,
)
from .raster_settings import RasterEstimate, RasterSettings
from .recipe import (
    EffectContext,
    EffectPlan,
    KaraokeItem,
    RubyPolicy,
    Sweep,
    TrackStyle,
)
from .render import (
    EffectBuilder,
    EffectFactory,
    EffectInput,
    PreparedKaraoke,
    RenderEstimate,
    RenderResult,
    prepare_karaoke,
    prepare_track_scene,
    render_karaoke,
)
from .sampling import (
    DynamicEffect,
    DynamicProperties,
    SampleContext,
    SamplingEstimate,
    SamplingPlan,
    SamplingSettings,
    prepare_sampling,
)
from .scene import (
    Lifetime,
    NativeEvent,
    ObjectGroup,
    PathObject,
    RectangleClip,
    RectangleFunction,
    Scene,
    SceneObject,
    TextObject,
    VectorClip,
    VisualNode,
)
from .scene_animation import (
    AnimationClip,
    Channel,
    SceneTimeline,
    StateAnimation,
    StateFunction,
    StateKeyframe,
    StatePatch,
    Tween,
    VisualState,
    linear_rate,
    smooth_rate,
)
from .scene_evaluation import SceneEvaluator, SceneReferenceError
from .scene_lyrics import LyricLayout, PositionedRuby, layout_document_lyrics
from .scene_output import (
    ObjectReport,
    SceneBudget,
    SceneCompileError,
    SceneResult,
    compile_scene,
)
from .scene_raster import RasterizedGroup, rasterize_group
from .scene_text import (
    DocumentLayout,
    PositionedText,
    SingingSpan,
    layout_document_text,
)
from .sources import EventOrigin, SourceRef, walk_karaoke
from .stylesheet import (
    INHERIT,
    UNSET,
    ColorStyle,
    NumberStyle,
    SelectionStyle,
    StyleKeyword,
    StyleOverrides,
    StyleProperties,
    StyleSheet,
    StyleValues,
    rule,
)
from .text_geometry import TextOutline, outline_text, text_to_path
from .text_style import Blur, PaintStyle, RubySpan, TextSpan, TextStyle
from .timeline import (
    DisplayWindow,
    EdgeSweep,
    HighlightTrack,
    ProgressCurve,
    Region,
    SingingPass,
    tracks_from_layout,
    union_regions,
)
from .track import Overlay, Track, TrackGroup
from .track_coverage import PreparedTrackCoverage, prepare_track_coverage
from .track_layout import DoubleLine, Layout, SingleLine

__all__ = [
    "Affine2D",
    "StateReference",
    "StateLookup",
    "FollowObject",
    "ReferenceFunction",
    "SceneEvaluator",
    "SceneReferenceError",
    "CuedLyrics",
    "bind_lyric_cues",
    "DocumentLyrics",
    "LyricMapping",
    "LyricSegment",
    "LyricUnit",
    "RubyText",
    "parse_document_lyrics",
    "LyricLayout",
    "PositionedRuby",
    "layout_document_lyrics",
    "Engine",
    "TemplateError",
    "apply_templates",
    "LegacyLine",
    "LegacySyllable",
    "preprocess",
    "split_karaoke",
    "ColorRamp",
    "ColorStop",
    "LinearGradient",
    "PaintBand",
    "PaintField",
    "SoftSweep",
    "CueMarker",
    "DocumentText",
    "SingingTag",
    "TextAppearance",
    "TextIssue",
    "TextRun",
    "TextToken",
    "read_document_text",
    "Composition",
    "MoveTo",
    "OpacityTo",
    "ScaleTo",
    "Timeline",
    "TransformTo",
    "TimeSpan",
    "Transform",
    "ColorKeyframe",
    "ColorKeyframes",
    "ColorTransition",
    "ColorValue",
    "PaintBounds",
    "Animate",
    "Animation",
    "AnimationContext",
    "AnimationEvent",
    "AnimationResult",
    "AnimationTarget",
    "Blur",
    "Display",
    "DoubleLine",
    "Envelope",
    "FadeInAnimation",
    "FadeOutAnimation",
    "Layout",
    "LineMatch",
    "Milliseconds",
    "On",
    "Overlay",
    "PaintStyle",
    "Parallel",
    "RateFunction",
    "SegmentSinging",
    "Sequence",
    "SingingPulseAnimation",
    "SingleLine",
    "SourceMatch",
    "Syllable",
    "TextSpan",
    "RubySpan",
    "TextStyle",
    "RasterEstimate",
    "RasterSettings",
    "RasterizedGroup",
    "rasterize_group",
    "Track",
    "TrackGroup",
    "on",
    "AnimationPlan",
    "AssImportError",
    "Box",
    "CharacterPaint",
    "CharacterTarget",
    "ClipSpan",
    "Color",
    "ColorSpan",
    "CompiledLayers",
    "DisplayWindow",
    "Document",
    "DrawableCharacter",
    "DynamicEffect",
    "DynamicProperties",
    "EdgeSweep",
    "EffectContext",
    "EffectPlan",
    "EventOrigin",
    "Fade",
    "FontFace",
    "Glow",
    "HighlightEnter",
    "HighlightTrack",
    "ImportSettings",
    "ImportedKaraoke",
    "KaraokeItem",
    "KaraokeLine",
    "LaidOutLine",
    "LaidOutSegment",
    "LaidOutUnit",
    "LayoutCapabilityError",
    "Line",
    "LoadedFont",
    "OffsetAnimation",
    "OpacityAnimation",
    "OutputCapabilityError",
    "OutputSettings",
    "Paint",
    "PaintPair",
    "PaintedRegion",
    "ProgressCurve",
    "Pulse",
    "Record",
    "Region",
    "PreparedKaraoke",
    "RenderEstimate",
    "RenderResult",
    "RubyPaint",
    "RubyPolicy",
    "SampleContext",
    "SamplingEstimate",
    "SamplingPlan",
    "SamplingSettings",
    "ScaleAnimation",
    "Segment",
    "SegmentStart",
    "SingingPass",
    "SourceRef",
    "Style",
    "Sweep",
    "SyllableStart",
    "TextLayer",
    "TextRange",
    "TextUnit",
    "TrackPaint",
    "TrackStyle",
    "compile_layers",
    "compose_highlights",
    "import_karaoke",
    "layout_characters",
    "layout_line",
    "load_font",
    "paint_pair_from_style",
    "parse_karaoke",
    "plan_pulses",
    "prepare_sampling",
    "prepare_karaoke",
    "prepare_track_scene",
    "render_karaoke",
    "resolve_paints",
    "resolve_ruby_paints",
    "select_characters",
    "sweep_spans",
    "text_extents",
    "tracks_from_layout",
    "union_regions",
    "walk_karaoke",
]


__all__ += [
    "BLACK",
    "BLUE",
    "CYAN",
    "GRAY",
    "GREEN",
    "INHERIT",
    "MAGENTA",
    "ORANGE",
    "PINK",
    "PURPLE",
    "RED",
    "UNSET",
    "WHITE",
    "YELLOW",
    "Body",
    "Effect",
    "Lyrics",
    "Ruby",
    "StyleSheet",
    "rule",
]


__all__ += [
    "Contextual",
    "Halo",
    "PropertyContext",
    "PropertyTarget",
    "Transition",
    "ease_in",
    "ease_in_out",
    "ease_out",
    "linear",
    "smooth",
    "there_and_back",
]


__all__ += ["Keyframe", "Keyframes", "display", "singing"]


__all__ += ["Follow"]


__all__ += [
    "AnimatedProperties",
    "ColorStyle",
    "Component",
    "CompositionMode",
    "EffectBuilder",
    "EffectFactory",
    "EffectInput",
    "NumberStyle",
    "ProgressMode",
    "PropertyValue",
    "SelectionStyle",
    "StyleKeyword",
    "StyleOverrides",
    "StyleProperties",
    "StyleValues",
    "TargetSelection",
    "TimeInterval",
    "TimeRef",
]


__all__ += [
    "AnimationClip",
    "Channel",
    "Contour",
    "CubicSegment",
    "Lifetime",
    "LineSegment",
    "NativeEvent",
    "ObjectGroup",
    "ObjectReport",
    "PathObject",
    "RectangleClip",
    "RectangleFunction",
    "Scene",
    "SceneBudget",
    "SceneCompileError",
    "SceneResult",
    "SceneTimeline",
    "StateAnimation",
    "StateFunction",
    "StatePatch",
    "StateKeyframe",
    "TextObject",
    "Tween",
    "Vec2",
    "VectorClip",
    "VectorPath",
    "VisualNode",
    "VisualState",
    "compile_scene",
    "linear_rate",
    "smooth_rate",
]


__all__ += [
    "BarsCue",
    "CuedLayout",
    "CueContent",
    "CueContext",
    "CueFactory",
    "CuePlacement",
    "CuePreset",
    "TextCue",
    "bind_cues",
    "DocumentLayout",
    "PositionedText",
    "SingingSpan",
    "layout_document_text",
]


__all__ += [
    "GeometryError",
    "Polyline",
    "flatten",
    "intersect_convex",
    "path_boolean",
    "merge_geometry",
    "PathBooleanOperation",
    "morph",
    "resample_path",
    "stroke",
    "GeometryAnimation",
    "MorphPath",
    "PathFunction",
    "WritePath",
    "WritingStroke",
    "TextOutline",
    "outline_text",
    "text_to_path",
]


__all__ += [
    "MoveAlong",
    "Emission",
    "ParticleContext",
    "ParticleFactory",
    "echoes",
    "emit_particles",
]

__all__ += ["split_path", "path_bounds"]

__all__ += ["PathItem", "layout_path"]

__all__ += ["SceneObject"]

__all__ += ["PreparedTrackCoverage", "prepare_track_coverage"]

__all__ += [
    "CoveragePartition",
    "GlowFunction",
    "ScopeOpacity",
    "CoverageResult",
    "compile_coverage",
]
