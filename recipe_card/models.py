"""Typed data models for source documents and computed geometry."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

HorizontalAlign = Literal["left", "center", "right"]
VerticalAlign = Literal["top", "middle", "bottom"]


@dataclass(frozen=True)
class CardMetadata:
    """Human-readable information shown above and below the grid."""

    title: str
    subtitle: str = ""
    source: str = ""
    footer: tuple[str, ...] = ()


@dataclass(frozen=True)
class PaddingConfig:
    """Canvas padding in SVG user units."""

    top: int = 32
    right: int = 40
    bottom: int = 30
    left: int = 40


@dataclass(frozen=True)
class CanvasConfig:
    """Optional fixed canvas dimensions and page appearance."""

    width: int | None = None
    height: int | None = None
    background: str | None = None
    padding: PaddingConfig = field(default_factory=PaddingConfig)


@dataclass(frozen=True)
class ThemeConfig:
    """Colors and typography shared by the card."""

    border_color: str = "#4b9847"
    border_width: float = 6.0
    outer_border_width: float | None = None
    cell_background: str = "#ffffff"
    background: str = "#fffde8"
    text_color: str = "#111111"
    secondary_text_color: str = "#4a4a4a"
    font_family: tuple[str, ...] = ("DejaVu Sans", "Arial", "sans-serif")
    title_size: int = 56
    subtitle_size: int = 28
    cell_text_size: int = 30
    footer_size: int = 23


@dataclass(frozen=True)
class LayoutConfig:
    """Grid dimensions and text-fitting defaults."""

    ingredient_column_width: int | None = None
    ingredient_column_min_width: int = 500
    ingredient_column_max_width: int = 640
    default_stage_width: int = 280
    row_height: int = 72
    title_height: int = 145
    footer_height: int = 75
    cell_padding: int = 16
    text_line_spacing: float = 1.12
    min_font_size: int = 18


@dataclass(frozen=True)
class IngredientRow:
    """One ingredient lane in the left-hand column."""

    id: str
    label: str
    height: int | None = None


@dataclass(frozen=True)
class Stage:
    """One horizontal process column."""

    id: str
    width: int | None = None


@dataclass(frozen=True)
class RowRange:
    """Inclusive range of ingredient row IDs."""

    from_id: str
    to_id: str


@dataclass(frozen=True)
class ProcessCell:
    """A process rectangle spanning inclusive stage and row ranges."""

    id: str
    stage_start: str
    stage_end: str
    rows: RowRange
    text: str = ""
    font_size: int | None = None
    min_font_size: int | None = None
    font_weight: str = "normal"
    align: HorizontalAlign = "center"
    valign: VerticalAlign = "middle"
    padding: int | None = None
    allow_overlap: bool = False


@dataclass(frozen=True)
class RecipeDocument:
    """Complete, validated recipe source model."""

    version: int
    card: CardMetadata
    canvas: CanvasConfig
    theme: ThemeConfig
    layout: LayoutConfig
    rows: tuple[IngredientRow, ...]
    stages: tuple[Stage, ...]
    cells: tuple[ProcessCell, ...]
    notes: tuple[str, ...] = ()
    source_path: Path | None = None

    @property
    def footer_notes(self) -> tuple[str, ...]:
        """Return metadata footer entries followed by top-level notes."""

        return self.card.footer + self.notes


@dataclass(frozen=True)
class Box:
    """Axis-aligned rectangle in SVG user units."""

    x: float
    y: float
    width: float
    height: float

    @property
    def right(self) -> float:
        """Right edge coordinate."""

        return self.x + self.width

    @property
    def bottom(self) -> float:
        """Bottom edge coordinate."""

        return self.y + self.height


@dataclass(frozen=True)
class CellBox:
    """Computed rectangle paired with its source row or process cell."""

    id: str
    box: Box
    text: str
    kind: Literal["ingredient", "process"]
    font_size: int | None = None
    min_font_size: int | None = None
    font_weight: str = "normal"
    align: HorizontalAlign = "center"
    valign: VerticalAlign = "middle"
    padding: int | None = None


@dataclass(frozen=True)
class BorderSegment:
    """One horizontal or vertical border segment."""

    orientation: Literal["horizontal", "vertical"]
    fixed: float
    start: float
    end: float


@dataclass(frozen=True)
class ComputedLayout:
    """All deterministic geometry required by output renderers."""

    canvas_width: int
    canvas_height: int
    ingredient_column_width: int
    title_height: int
    footer_height: int
    grid_box: Box
    row_tops: dict[str, float]
    row_bottoms: dict[str, float]
    stage_lefts: dict[str, float]
    stage_rights: dict[str, float]
    ingredient_boxes: tuple[CellBox, ...]
    process_boxes: tuple[CellBox, ...]
    border_segments: tuple[BorderSegment, ...]
