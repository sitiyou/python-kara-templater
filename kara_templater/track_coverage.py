"""Track frontend for editable, Document-backed coverage material scenes."""

from dataclasses import dataclass

from ._track_compiler import PreparedTrack
from ._track_coverage import CoverageTrack, track_coverage
from .ass import Document
from .ass_output import OutputSettings
from .composition import Glow
from .coverage_animation import CoveragePartition, GlowFunction, ScopeOpacity
from .coverage_output import CoverageResult, compile_coverage
from .geometry import finite
from .import_ass import ImportSettings
from .karaoke import KaraokeItem
from .paint_fields import PaintField
from .raster_settings import RasterSettings
from .render import _prepare_tracks
from .scene import Lifetime, ObjectGroup, SceneObject
from .scene_output import SceneBudget
from .track import Track, TrackGroup

_DEFAULT_SETTINGS = RasterSettings()
_DEFAULT_BUDGET = SceneBudget()


@dataclass(frozen=True)
class PreparedTrackCoverage:
    """Editable group plus explicit material bindings and retained source data.

    Use dataclasses.replace to edit group geometry, or modify binding dictionaries
    before compiling. IDs identify material ownership: copying/renaming nodes
    requires remapping bindings and ScopeOpacity owners. Preparation never
    evaluates dynamic property functions; compile uses the shared coverage exit.
    """

    document: Document
    group: ObjectGroup
    components: tuple[str, ...]
    glows: dict[str, Glow | GlowFunction]
    glow_materials: dict[str, PaintField]
    partitions: dict[str, CoveragePartition]
    scope_opacities: dict[str, tuple[ScopeOpacity, ...]]
    diagnostics: tuple[str, ...]
    owner: str

    def compile(
        self,
        *,
        settings: RasterSettings = _DEFAULT_SETTINGS,
        budget: SceneBudget = _DEFAULT_BUDGET,
    ) -> CoverageResult:
        """Compile the editable group and ID-keyed material bindings with explicit raster and Scene limits."""
        return compile_coverage(
            self.document,
            self.group,
            components=self.components,
            glows=self.glows,
            glow_materials=self.glow_materials,
            partitions=self.partitions,
            scope_opacities=self.scope_opacities,
            owner=self.owner,
            settings=settings,
            budget=budget,
        )


def prepare_track_coverage(
    document: Document,
    items: tuple[KaraokeItem, ...] | None = None,
    *,
    tracks: tuple[Track | TrackGroup, ...],
    max_glow_blur: float,
    max_glow_border: float,
    owner: str = "default",
    import_settings: ImportSettings | None = None,
    max_objects: int = 25_000,
) -> PreparedTrackCoverage:
    """Prepare editable coverage components with shared karaoke ownership rules.

    Bounds are final script pixels, including caller-added scale. Imported source
    lines become retained comments; explicit items leave dialogue unchanged.
    Unselected lines and other owners survive. Geometry/property/material binding
    happens now, callbacks only at compile. Track.sampling is not used here.
    Track sweep fronts currently require positive axis-aligned uniform scale;
    custom two-dimensional sweep ownership is not inferred from an affine edit.
    """
    finite(max_glow_blur, max_glow_border)
    if not 0 <= max_glow_blur <= 100 or max_glow_border < 0:
        raise ValueError(
            "coverage glow bounds require blur in 0..100 and nonnegative border"
        )
    if type(max_objects) is not int or max_objects < 1:
        raise ValueError("max_objects must be a positive integer")
    converted: list[CoverageTrack] = []

    def build(
        item_id: str, prepared: PreparedTrack, diagnostics: list[str]
    ) -> ObjectGroup:
        result = track_coverage(
            item_id,
            prepared,
            max_glow_blur=max_glow_blur,
            max_glow_border=max_glow_border,
        )
        converted.append(result)
        diagnostics.extend(result.diagnostics)
        return result.group

    prepared = _prepare_tracks(
        document,
        items,
        tracks=tracks,
        owner=owner,
        import_settings=import_settings,
        settings=OutputSettings(
            resolution=(document.meta.res_x, document.meta.res_y),
            max_events=max_objects,
        ),
        editable_tracks=True,
        track_builder=build,
    )
    children: list[ObjectGroup] = []
    identities: set[str] = set()

    def visit(node: SceneObject) -> None:
        identities.add(node.id)
        if isinstance(node, ObjectGroup):
            for child in node.children:
                visit(child)

    for node in prepared.scene.objects:
        assert isinstance(node, ObjectGroup)
        children.append(node)
        visit(node)
    identity = "coverage:" + owner
    while identity in identities:
        identity += ":root"
    lifetime = Lifetime(
        min((child.lifetime.start for child in children), default=0),
        max((child.lifetime.end for child in children), default=0.01),
    )
    return PreparedTrackCoverage(
        prepared.scene.document,
        ObjectGroup(id=identity, lifetime=lifetime, children=tuple(children)),
        tuple(component for item in converted for component in item.components),
        {key: glow for item in converted for key, glow in item.glows.items()},
        {},
        {key: part for item in converted for key, part in item.partitions.items()},
        {
            key: scopes
            for item in converted
            for key, scopes in item.scope_opacities.items()
        },
        prepared.diagnostics,
        prepared.scene.owner,
    )
