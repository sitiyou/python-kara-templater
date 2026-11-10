"""Resolve source-range appearance independently of singing partitions."""

from dataclasses import dataclass, field

from .characters import DrawableCharacter, TextRange, select_characters
from .composition import Paint
from .sources import _source_location


@dataclass(frozen=True)
class PaintPair:
    before: Paint = field(default_factory=Paint)
    after: Paint = field(default_factory=Paint)


DEFAULT_PAINTS = PaintPair()


@dataclass(frozen=True)
class ColorSpan:
    source: TextRange
    before: Paint | None = None
    after: Paint | None = None
    priority: int = 0

    def __post_init__(self):
        if type(self.priority) is not int:
            raise ValueError("span priority must be an integer")
        if self.before is None and self.after is None:
            raise ValueError("a color span must override before or after appearance")


@dataclass(frozen=True)
class CharacterPaint:
    character: DrawableCharacter
    paints: PaintPair

    def highlighted(self, track_override: Paint | None = None) -> Paint:
        return self.paints.after if track_override is None else track_override


def resolve_paints(
    characters: tuple[DrawableCharacter, ...],
    *,
    default: PaintPair = DEFAULT_PAINTS,
    spans: tuple[ColorSpan, ...] = (),
) -> tuple[CharacterPaint, ...]:
    """Precedence: line defaults, source spans, then explicit track override.

    Equal-priority spans conflict only if they specify different values for the
    same before/after state. Every range must preserve drawable clusters.
    """
    selections = [
        (span, {c.id for c in select_characters(characters, span.source)})
        for span in spans
    ]
    result = []
    for char in characters:
        with _source_location(char.source.unit_index):
            values = {}
            for state in ("before", "after"):
                active = [
                    span
                    for span, ids in selections
                    if char.id in ids and getattr(span, state) is not None
                ]
                if not active:
                    values[state] = getattr(default, state)
                    continue
                top = max(span.priority for span in active)
                choices = {
                    getattr(span, state) for span in active if span.priority == top
                }
                if len(choices) != 1:
                    raise ValueError(
                        f"{char.id}: conflicting {state} color spans at priority {top}"
                    )
                values[state] = choices.pop()
            result.append(CharacterPaint(char, PaintPair(**values)))
    return tuple(result)


@dataclass(frozen=True)
class RubyPaint:
    unit_index: int
    segment_index: int
    paints: PaintPair


def resolve_ruby_paints(
    layout,
    characters: tuple[CharacterPaint, ...],
    *,
    overrides: tuple[RubyPaint, ...] = (),
) -> tuple[RubyPaint, ...]:
    """Inherit homogeneous associated body appearance, otherwise require a map.

    Ruby is associated through its measured segment partition, never a second
    text layout. Explicit overrides can assign one pair to each reading segment.
    """
    explicit = {(r.unit_index, r.segment_index): r.paints for r in overrides}
    if len(explicit) != len(overrides):
        raise ValueError("duplicate ruby appearance override")
    result = []
    for ui, unit in enumerate(layout.units):
        for si, segment in enumerate(unit.segments):
            with _source_location(ui, si):
                if segment.ruby is None:
                    continue
                paints = explicit.pop((ui, si), None)
                if paints is None:
                    choices = {
                        c.paints
                        for c in characters
                        if c.character.source.unit_index == ui
                        and c.character.timing_region.left < segment.right
                        and c.character.timing_region.right > segment.left
                    }
                    if len(choices) != 1:
                        raise ValueError(
                            f"unit {ui}/segment {si}: ruby needs explicit appearance for ambiguous body colors"
                        )
                    paints = choices.pop()
                result.append(RubyPaint(ui, si, paints))
    if explicit:
        raise ValueError(
            f"ruby overrides reference missing readings: {sorted(explicit)}"
        )
    return tuple(result)
