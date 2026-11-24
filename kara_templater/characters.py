"""Source-mapped, independently drawable clusters verified against shaped glyph outlines."""

from dataclasses import dataclass, field, replace
from unicodedata import category, name

from . import _metrics
from .ass import Style
from .geometry import Box, Region, Vec2, _finite
from .sources import _source_location
from .text.measurement import text_extents


@dataclass(frozen=True)
class CharacterTarget:
    """An independently drawable cluster supplied by layout, never a codepoint.

    A layout backend must establish that the cluster can be drawn independently.
    This model deliberately does not split text or claim shaping support.
    """

    id: str
    unit_index: int
    region: Region
    center_y: float
    drawable: bool = True
    center_x: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id:
            raise ValueError("character target needs a stable id")
        if type(self.unit_index) is not int or self.unit_index < 0:
            raise ValueError("unit_index must be a nonnegative integer")
        _finite(self.center_y, "center_y")
        if self.center_x is not None:
            _finite(self.center_x, "center_x")


class LayoutCapabilityError(ValueError):
    """The available metrics cannot establish a safe independent drawing."""


@dataclass(frozen=True)
class TextRange:
    """Half-open Python string offsets in an immutable source unit.

    Offsets are source references, not drawable character indices. A range used
    for painting must end on the verified cluster boundaries.
    """

    unit_index: int
    start: int
    end: int

    def __post_init__(self) -> None:
        if (
            any(
                type(v) is not int or v < 0
                for v in (self.unit_index, self.start, self.end)
            )
            or self.end <= self.start
        ):
            raise ValueError(
                "text range needs a nonnegative unit and positive half-open interval"
            )


@dataclass(frozen=True)
class FontFace:
    """Face names and em-to-ASS-size ratio from FreeType. Names determine equality."""

    family: str
    style: str
    em_ratio: float = field(default=1.0, compare=False)


@dataclass(frozen=True)
class DrawableCharacter:
    """An independently drawable shaped cluster with unit-local source range, advance/ink bounds, timing region, and actual font faces.

    A cluster can contain several Unicode code points. Add pen_offset to the
    allocated box origin to draw the cluster with ordinary ASS font metrics.
    """

    source: TextRange
    text: str
    box: Box
    ink_bounds: Box | None
    timing_region: Region
    font_faces: tuple[FontFace, ...] = ()
    pen_offset: Vec2 = Vec2()

    @property
    def id(self) -> str:
        """The stable layout-local identity of this drawable source cluster."""
        return (
            f"unit:{self.source.unit_index}/text:{self.source.start}:{self.source.end}"
        )

    @property
    def target(self) -> CharacterTarget:
        """Expose the character region, source unit, and center for highlight scheduling."""
        return CharacterTarget(
            self.id,
            self.source.unit_index,
            self.timing_region,
            self.box.middle,
            self.ink_bounds is not None and not self.text.isspace(),
            self.box.center,
        )


def _clusters(text):
    """Conservative LTR repertoire, not a replacement for Unicode segmentation.

    Latin/Greek/Cyrillic, CJK, kana, modern Hangul, digits, punctuation and
    common lyric symbols are candidates. Combining marks stay with the preceding base. Joining
    scripts, bidi controls, emoji sequences and archaic jamo require a later backend.
    Candidate segmentation is subsequently checked against actual outlines.
    """
    result = []
    for index, char in enumerate(text):
        kind = category(char)
        label = name(char, "")
        if kind.startswith("M") and result and not result[-1][2].isspace():
            start, _, previous = result.pop()
            result.append((start, index + 1, previous + char))
            continue
        accepted = (
            kind == "Zs"
            or char
            in "々ー●|☆★♥♡♪♫"  # Lyric marks, shape-checked below.
            or 0x1100 <= ord(char) <= 0x1112
            or 0x1161 <= ord(char) <= 0x1175
            or 0x11A8 <= ord(char) <= 0x11C2
            or kind.startswith("P")
            or label.startswith(
                (
                    "LATIN ",
                    "GREEK ",
                    "CYRILLIC ",
                    "CJK UNIFIED IDEOGRAPH",
                    "CJK COMPATIBILITY IDEOGRAPH",
                    "HIRAGANA ",
                    "KATAKANA ",
                    "HANGUL SYLLABLE ",
                    "DIGIT ",
                    "FULLWIDTH ",
                )
            )
        )
        if not accepted or char in "\\{}\n\r\t" or kind.startswith("C"):
            raise LayoutCapabilityError(
                f"unsupported cluster at source offset {index}: U+{ord(char):04X}"
            )
        result.append((index, index + 1, char))
    return result


def _shape(style, text, placement_x=0, *, palt=False):
    try:
        return _metrics.text_shape(
            style.fontname,
            style.fontsize,
            int(style.bold),
            int(style.italic),
            style.scale_x,
            style.scale_y,
            style.spacing,
            style.encoding,
            text,
            placement_x,
            palt,
        )
    except ValueError as error:
        raise LayoutCapabilityError(str(error)) from error


def _translation(actual, isolated, *, source):
    if len(actual) != len(isolated):
        raise LayoutCapabilityError(
            f"{source}: shaping changes glyph count across character boundaries"
        )
    shift = None
    origin_shift = None
    for (points, segments, origin, face), (
        reference,
        reference_segments,
        reference_origin,
        reference_face,
    ) in zip(actual, isolated, strict=True):
        if face != reference_face:
            raise LayoutCapabilityError(
                f"{source}: independent drawing changes font face or glyph index"
            )
        delta = (origin[0] - reference_origin[0], origin[1] - reference_origin[1])
        if origin_shift is None:
            origin_shift = delta
        elif any(
            abs(a - b) > 1 / 64 + 1e-8 for a, b in zip(delta, origin_shift, strict=True)
        ):
            raise LayoutCapabilityError(
                f"{source}: shaping changes glyph origins across character boundaries"
            )
        if segments != reference_segments or len(points) != len(reference):
            raise LayoutCapabilityError(
                f"{source}: shaping changes glyph contours across character boundaries"
            )
        for (x, y), (rx, ry) in zip(points, reference, strict=True):
            if shift is None:
                shift = (x - rx, y - ry)
            # The C++ text engine positions outlines on a 1/64-pixel grid. Permit one grid
            # step of rounding, but never accept scaled or substituted glyphs.
            if (
                abs(x - rx - shift[0]) > 1 / 64 + 1e-8
                or abs(y - ry - shift[1]) > 1 / 64 + 1e-8
            ):
                raise LayoutCapabilityError(
                    f"{source}: shaping changes glyph contours across character boundaries"
                )
    return shift


def layout_characters(
    text: str, *, style: Style, origin: Vec2 | None = None, palt: bool = False,
) -> tuple[DrawableCharacter, ...]:
    """Measure independently drawable clusters and source ranges in a text run.

    Origin is the top-left of the run in script pixels, with (0, 0) as the default. Ink bounds exclude
    decoration. Spaces retain their advance even when they have no outline.
    """
    origin = origin or Vec2()
    width, height, _, _ = text_extents(replace(style, outline=0), text, palt=palt)
    return _measure_clusters(text, Box(origin.x, origin.y, width, height), style=style, palt=palt)


def _measure_clusters(
    source_text: str, bounds: Box, *, style: Style, index: int = 0, palt: bool = False,
) -> tuple[DrawableCharacter, ...]:
    if not source_text:
        return ()
    result = []
    with _source_location(index):
        try:
            clusters = _clusters(source_text)
        except LayoutCapabilityError as error:
            raise LayoutCapabilityError(f"unit {index}: {error}") from error
        width, _, _, baseline, outlines = _shape(
            style, source_text, bounds.left, palt=palt
        )
        if abs(width - bounds.width) > 1 / 64:
            raise LayoutCapabilityError(
                f"unit {index}: supplied style does not match original layout"
            )
        cursor, advance = 0, 0
        unit_characters = []
        ci = 0
        while ci < len(clusters):
            start = clusters[ci][0]
            last_error = None
            matched = None
            # A ligature cannot be redrawn as independent source characters.
            # Grow the source range until its isolated contours exactly match
            # the original run. Whitespace remains a separate timing region.
            for stop in range(ci, len(clusters)):
                if stop > ci and (
                    clusters[ci][2].isspace() or clusters[stop][2].isspace()
                ):
                    break
                end = clusters[stop][1]
                text = source_text[start:end]
                source = TextRange(index, start, end)
                try:
                    cw, ch, _, cb, isolated = _shape(style, text, bounds.left, palt=palt)
                    actual = outlines[cursor : cursor + len(isolated)]
                    shift = _translation(actual, isolated, source=source)
                except LayoutCapabilityError as error:
                    last_error = error
                    continue
                ci = stop + 1
                matched = (text, source, cw, ch, cb, isolated, actual, shift)
                break
            if matched is None:
                assert last_error is not None
                raise last_error
            text, source, cw, ch, cb, isolated, actual, shift = matched
            pen_offset = Vec2()
            if palt and isolated:
                # The portable renderer draws this cluster without palt. Bake
                # the GPOS translation into its pen, separately from its cell.
                plain = _shape(style, text, bounds.left)[4]
                offset = _translation(isolated, plain, source=source)
                if offset is not None:
                    pen_offset = Vec2(*offset)
            cursor += len(isolated)
            dx, dy = shift if shift is not None else (advance, 0)
            box = Box(bounds.left + dx, bounds.top + baseline + dy - cb, cw, ch)
            points = [point for outline, _, _, _ in actual for point in outline]
            ink = None
            if points:
                xs, ys = zip(*points, strict=True)
                ink = Box(
                    bounds.left + min(xs),
                    bounds.top + baseline + min(ys),
                    max(xs) - min(xs),
                    max(ys) - min(ys),
                )
            unit_characters.append(
                DrawableCharacter(
                    source,
                    text,
                    box,
                    ink,
                    Region(box.left, box.right),
                    tuple(
                        dict.fromkeys(
                            FontFace(face[0], face[1], face[3]) for _, _, _, face in actual
                        )
                    ),
                    pen_offset,
                )
            )
            advance = dx + cw
        if cursor != len(outlines):
            raise LayoutCapabilityError(
                f"unit {index}: shaping changes glyph count across character boundaries"
            )
        # Outline positions are grid-quantized, advances are not. Keep the last
        # timing boundary exactly at the unit edge so every character completes.
        for ci, character in enumerate(unit_characters):
            left = character.box.left if ci else bounds.left
            right = (
                unit_characters[ci + 1].box.left
                if ci + 1 < len(unit_characters)
                else bounds.right
            )
            if right < left:
                raise LayoutCapabilityError(
                    f"{character.source}: non-monotone character positions"
                )
            result.append(replace(character, timing_region=Region(left, right)))
    return tuple(result)


def select_characters(
    characters: tuple[DrawableCharacter, ...], source: TextRange
) -> tuple[DrawableCharacter, ...]:
    """Select complete drawable clusters covered by a TextRange.

    Reject boundaries that cut a cluster instead of silently expanding or reshaping
    the selection.
    """
    with _source_location(source.unit_index):
        selected = tuple(
            c
            for c in characters
            if c.source.unit_index == source.unit_index
            and c.source.start < source.end
            and source.start < c.source.end
        )
        if (
            not selected
            or selected[0].source.start != source.start
            or selected[-1].source.end != source.end
        ):
            raise LayoutCapabilityError(
                f"{source}: range is outside text or cuts a drawable cluster"
            )
        return selected
