"""Deterministic conversion from validated recipe data to card geometry."""

from __future__ import annotations

from collections import defaultdict
from math import ceil

from .exceptions import LayoutError
from .models import BorderSegment, Box, CellBox, ComputedLayout, RecipeDocument
from .text import measure_text_width, natural_text
from .validation import validate_recipe


def _title_area_height(document: RecipeDocument, available_width: float) -> int:
    theme = document.theme
    spacing = document.layout.text_line_spacing
    title = natural_text(document.card.title, available_width, theme.title_size, spacing, bold=True)
    height = title.total_height
    if document.card.subtitle:
        height += 10 + natural_text(document.card.subtitle, available_width, theme.subtitle_size, spacing).total_height
    if document.card.source:
        height += 6 + natural_text(f"Source: {document.card.source}", available_width, theme.footer_size, spacing).total_height
    return max(document.layout.title_height, int(height + 18 + 0.9999))


def _footer_area_height(document: RecipeDocument, available_width: float) -> int:
    if not document.footer_notes:
        return 0
    height = 16.0
    for note in document.footer_notes:
        fitted = natural_text(f"• {note}", available_width, document.theme.footer_size, document.layout.text_line_spacing)
        height += fitted.total_height + 5
    return max(document.layout.footer_height, int(height + 0.9999))


def _merge_segments(segments: list[BorderSegment]) -> tuple[BorderSegment, ...]:
    grouped: dict[tuple[str, float], list[tuple[float, float]]] = defaultdict(list)
    for segment in segments:
        grouped[(segment.orientation, segment.fixed)].append((segment.start, segment.end))
    merged: list[BorderSegment] = []
    orientation_order = {"horizontal": 0, "vertical": 1}
    for (orientation, fixed), ranges in sorted(grouped.items(), key=lambda item: (orientation_order[item[0][0]], item[0][1])):
        ranges.sort()
        current_start, current_end = ranges[0]
        for start, end in ranges[1:]:
            if start <= current_end:
                current_end = max(current_end, end)
            else:
                merged.append(BorderSegment(orientation, fixed, current_start, current_end))  # type: ignore[arg-type]
                current_start, current_end = start, end
        merged.append(BorderSegment(orientation, fixed, current_start, current_end))  # type: ignore[arg-type]
    return tuple(merged)


def _borders(boxes: tuple[CellBox, ...], grid_box: Box) -> tuple[BorderSegment, ...]:
    segments: list[BorderSegment] = []
    for item in boxes:
        box = item.box
        segments.extend(
            (
                BorderSegment("horizontal", box.y, box.x, box.right),
                BorderSegment("horizontal", box.bottom, box.x, box.right),
                BorderSegment("vertical", box.x, box.y, box.bottom),
                BorderSegment("vertical", box.right, box.y, box.bottom),
            )
        )
    segments.extend(
        (
            BorderSegment("horizontal", grid_box.y, grid_box.x, grid_box.right),
            BorderSegment("horizontal", grid_box.bottom, grid_box.x, grid_box.right),
            BorderSegment("vertical", grid_box.x, grid_box.y, grid_box.bottom),
            BorderSegment("vertical", grid_box.right, grid_box.y, grid_box.bottom),
        )
    )
    return _merge_segments(segments)


def _ingredient_column_width(document: RecipeDocument) -> int:
    """Resolve a fixed width or measure and clamp an automatic one."""

    layout = document.layout
    if layout.ingredient_column_width is not None:
        return layout.ingredient_column_width
    widest = max(
        (measure_text_width(row.label, document.theme.cell_text_size) for row in document.rows),
        default=0.0,
    )
    natural_width = ceil(widest + 2 * layout.cell_padding)
    return min(
        layout.ingredient_column_max_width,
        max(layout.ingredient_column_min_width, natural_width),
    )


def _automatic_row_heights(document: RecipeDocument, ingredient_column_width: int) -> dict[str, int]:
    """Resolve fixed rows and grow omitted rows to fit grid text naturally."""

    layout = document.layout
    theme = document.theme
    spacing = layout.text_line_spacing
    row_index = {row.id: index for index, row in enumerate(document.rows)}
    heights: dict[str, int] = {}
    automatic: set[str] = set()

    ingredient_text_width = ingredient_column_width - 2 * layout.cell_padding
    for row in document.rows:
        if row.height is not None:
            heights[row.id] = row.height
            continue
        automatic.add(row.id)
        fitted = natural_text(row.label, ingredient_text_width, theme.cell_text_size, spacing)
        natural_height = ceil(fitted.total_height + 2 * layout.cell_padding)
        heights[row.id] = max(layout.row_height, natural_height)

    stage_widths = [
        stage.width if stage.width is not None else layout.default_stage_width
        for stage in document.stages
    ]
    stage_index = {stage.id: index for index, stage in enumerate(document.stages)}
    for cell in document.cells:
        if not cell.text:
            continue
        row_start = row_index[cell.rows.from_id]
        row_end = row_index[cell.rows.to_id]
        stage_start = stage_index[cell.stage_start]
        stage_end = stage_index[cell.stage_end]
        cell_padding = cell.padding if cell.padding is not None else layout.cell_padding
        cell_width = sum(stage_widths[stage_start : stage_end + 1]) - 2 * cell_padding
        font_size = cell.font_size if cell.font_size is not None else theme.cell_text_size
        bold = cell.font_weight == "bold" or (cell.font_weight.isdigit() and int(cell.font_weight) >= 600)
        fitted = natural_text(cell.text, cell_width, font_size, spacing, bold=bold)
        required_height = ceil(fitted.total_height + 2 * cell_padding)
        spanned_rows = document.rows[row_start : row_end + 1]
        current_height = sum(heights[row.id] for row in spanned_rows)
        deficit = required_height - current_height
        expandable = [row.id for row in spanned_rows if row.id in automatic]
        if deficit <= 0 or not expandable:
            continue
        increment, remainder = divmod(deficit, len(expandable))
        for index, row_id in enumerate(expandable):
            heights[row_id] += increment + (1 if index < remainder else 0)

    return heights


def compute_layout(document: RecipeDocument) -> ComputedLayout:
    """Compute all row, stage, cell, canvas, and border geometry."""

    validate_recipe(document)
    canvas = document.canvas
    padding = canvas.padding
    layout = document.layout
    ingredient_column_width = _ingredient_column_width(document)
    grid_width = ingredient_column_width + sum(
        stage.width if stage.width is not None else layout.default_stage_width for stage in document.stages
    )
    minimum_width = padding.left + grid_width + padding.right
    canvas_width = canvas.width if canvas.width is not None else minimum_width
    if canvas_width < minimum_width:
        raise LayoutError(f"canvas width {canvas_width} is too small; layout requires at least {minimum_width}")
    text_width = canvas_width - padding.left - padding.right
    title_height = _title_area_height(document, text_width)
    footer_height = _footer_area_height(document, text_width)
    grid_x = float(padding.left)
    grid_y = float(padding.top + title_height)
    row_heights = _automatic_row_heights(document, ingredient_column_width)

    row_tops: dict[str, float] = {}
    row_bottoms: dict[str, float] = {}
    y = grid_y
    ingredient_boxes: list[CellBox] = []
    for row in document.rows:
        height = row_heights[row.id]
        row_tops[row.id] = y
        row_bottoms[row.id] = y + height
        ingredient_boxes.append(
            CellBox(
                id=row.id,
                box=Box(grid_x, y, float(ingredient_column_width), float(height)),
                text=row.label,
                kind="ingredient",
            )
        )
        y += height
    grid_height = y - grid_y

    stage_lefts: dict[str, float] = {}
    stage_rights: dict[str, float] = {}
    x = grid_x + ingredient_column_width
    for stage in document.stages:
        width = stage.width if stage.width is not None else layout.default_stage_width
        stage_lefts[stage.id] = x
        stage_rights[stage.id] = x + width
        x += width

    process_boxes: list[CellBox] = []
    for cell in document.cells:
        left = stage_lefts[cell.stage_start]
        right = stage_rights[cell.stage_end]
        top = row_tops[cell.rows.from_id]
        bottom = row_bottoms[cell.rows.to_id]
        process_boxes.append(
            CellBox(
                id=cell.id,
                box=Box(left, top, right - left, bottom - top),
                text=cell.text,
                kind="process",
                font_size=cell.font_size,
                min_font_size=cell.min_font_size,
                font_weight=cell.font_weight,
                align=cell.align,
                valign=cell.valign,
                padding=cell.padding,
            )
        )

    required_height = padding.top + title_height + int(grid_height) + footer_height + padding.bottom
    canvas_height = canvas.height if canvas.height is not None else required_height
    if canvas_height < required_height:
        raise LayoutError(f"canvas height {canvas_height} is too small; layout requires at least {required_height}")
    all_boxes = tuple(ingredient_boxes + process_boxes)
    grid_box = Box(grid_x, grid_y, float(grid_width), grid_height)
    return ComputedLayout(
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        ingredient_column_width=ingredient_column_width,
        title_height=title_height,
        footer_height=footer_height,
        grid_box=grid_box,
        row_tops=row_tops,
        row_bottoms=row_bottoms,
        stage_lefts=stage_lefts,
        stage_rights=stage_rights,
        ingredient_boxes=tuple(ingredient_boxes),
        process_boxes=tuple(process_boxes),
        border_segments=_borders(all_boxes, grid_box),
    )
