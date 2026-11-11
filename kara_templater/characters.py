"""Source-mapped, independently drawable clusters verified against libass shapes."""

from dataclasses import dataclass, replace
from unicodedata import category, name

from . import _metrics
from .animation import CharacterTarget
from .ass import Style
from .model import Box, LaidOutLine
from .sources import _source_location
from .timeline import Region


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
    """Actual face names reported by FreeType, not a font file identity."""

    family: str
    style: str


@dataclass(frozen=True)
class DrawableCharacter:
    source: TextRange
    text: str
    box: Box
    ink_bounds: Box | None
    timing_region: Region
    font_faces: tuple[FontFace, ...] = ()

    @property
    def id(self) -> str:
        return (
            f"unit:{self.source.unit_index}/text:{self.source.start}:{self.source.end}"
        )

    @property
    def target(self) -> CharacterTarget:
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
    karaoke guide dots are candidates. Combining marks stay with the preceding base. Joining
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
            in "々ー●"  # Japanese marks and karaoke guide dots; shape-checked below.
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


def _shape(style, text, placement_x=0):
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
            # libass positions outlines on a 1/64-pixel grid. Permit one grid
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
    layout: LaidOutLine, *, style: Style
) -> tuple[DrawableCharacter, ...]:
    """Measure verified clusters in the original unit layout, without relayout.

    Ink bounds are conservative outline control-point bounds (no blur/stroke),
    not exact raster extents. TextRange identities are independent of timing and
    appearance. Empty-outline spaces retain advance but are not pulse targets.
    """
    result = []
    for index, unit in enumerate(layout.units):
        with _source_location(index):
            if not unit.source.text:
                continue
            try:
                clusters = _clusters(unit.source.text)
            except LayoutCapabilityError as error:
                raise LayoutCapabilityError(f"unit {index}: {error}") from error
            width, _, _, baseline, outlines = _shape(
                style, unit.source.text, unit.box.left
            )
            if abs(width - unit.box.width) > 1 / 64:
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
                    text = unit.source.text[start:end]
                    source = TextRange(index, start, end)
                    try:
                        cw, ch, _, cb, isolated = _shape(style, text, unit.box.left)
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
                cursor += len(isolated)
                dx, dy = shift if shift is not None else (advance, 0)
                box = Box(unit.box.left + dx, unit.box.top + baseline + dy - cb, cw, ch)
                points = [point for outline, _, _, _ in actual for point in outline]
                ink = None
                if points:
                    xs, ys = zip(*points, strict=True)
                    ink = Box(
                        unit.box.left + min(xs),
                        unit.box.top + baseline + min(ys),
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
                                FontFace(face[0], face[1]) for _, _, _, face in actual
                            )
                        ),
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
                left = character.box.left if ci else unit.box.left
                right = (
                    unit_characters[ci + 1].box.left
                    if ci + 1 < len(unit_characters)
                    else unit.box.right
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
