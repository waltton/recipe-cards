"""Semantic validation for parsed recipe documents."""

from __future__ import annotations

import os
import re
from pathlib import Path

from .exceptions import LayoutError, RecipeValidationError
from .models import ProcessCell, RecipeDocument

_ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
_HEX_COLOR_PATTERN = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")


def _duplicates(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return sorted(duplicates)


def _range_indices(cell: ProcessCell, row_index: dict[str, int], stage_index: dict[str, int]) -> tuple[int, int, int, int] | None:
    refs = (cell.rows.from_id, cell.rows.to_id, cell.stage_start, cell.stage_end)
    if refs[0] not in row_index or refs[1] not in row_index or refs[2] not in stage_index or refs[3] not in stage_index:
        return None
    return row_index[refs[0]], row_index[refs[1]], stage_index[refs[2]], stage_index[refs[3]]


def validate_recipe(document: RecipeDocument) -> None:
    """Validate IDs, references, dimensions, colors, ranges, and overlaps."""

    errors: list[str] = []
    if document.version != 1:
        errors.append(f"unsupported YAML version {document.version!r}; expected 1")
    if not document.card.title.strip():
        errors.append("card.title must not be empty")
    if not document.rows:
        errors.append("rows must contain at least one ingredient row")
    if not document.stages:
        errors.append("stages must contain at least one process stage")

    row_ids = [row.id for row in document.rows]
    stage_ids = [stage.id for stage in document.stages]
    cell_ids = [cell.id for cell in document.cells]
    for kind, values in (("row", row_ids), ("stage", stage_ids), ("cell", cell_ids)):
        for duplicate in _duplicates(values):
            errors.append(f"duplicate {kind} ID '{duplicate}'")
        for value in values:
            if not _ID_PATTERN.fullmatch(value):
                errors.append(f"invalid {kind} ID '{value}'; use letters, numbers, '_' or '-', starting with a letter")

    row_index = {value: index for index, value in enumerate(row_ids)}
    stage_index = {value: index for index, value in enumerate(stage_ids)}
    for row in document.rows:
        height = row.height if row.height is not None else document.layout.row_height
        if height <= 0:
            errors.append(f"row '{row.id}' height must be positive")
    for stage in document.stages:
        width = stage.width if stage.width is not None else document.layout.default_stage_width
        if width <= 0:
            errors.append(f"stage '{stage.id}' width must be positive")

    for cell in document.cells:
        if cell.rows.from_id not in row_index:
            errors.append(f"cell '{cell.id}' references unknown row '{cell.rows.from_id}'")
        if cell.rows.to_id not in row_index:
            errors.append(f"cell '{cell.id}' references unknown row '{cell.rows.to_id}'")
        if cell.stage_start not in stage_index:
            errors.append(f"cell '{cell.id}' references unknown stage '{cell.stage_start}'")
        if cell.stage_end not in stage_index:
            errors.append(f"cell '{cell.id}' references unknown stage '{cell.stage_end}'")
        indices = _range_indices(cell, row_index, stage_index)
        if indices is not None:
            row_start, row_end, stage_start, stage_end = indices
            if row_start > row_end:
                errors.append(f"cell '{cell.id}' row range is reversed: {cell.rows.from_id}..{cell.rows.to_id}")
            if stage_start > stage_end:
                errors.append(f"cell '{cell.id}' stage range is reversed: {cell.stage_start}..{cell.stage_end}")
        if cell.align not in {"left", "center", "right"}:
            errors.append(f"cell '{cell.id}' align must be left, center, or right")
        if cell.valign not in {"top", "middle", "bottom"}:
            errors.append(f"cell '{cell.id}' valign must be top, middle, or bottom")
        if cell.font_weight not in {"normal", "bold", "100", "200", "300", "400", "500", "600", "700", "800", "900"}:
            errors.append(f"cell '{cell.id}' font_weight is invalid")
        if cell.font_size is not None and cell.font_size <= 0:
            errors.append(f"cell '{cell.id}' font_size must be positive")
        if cell.min_font_size is not None and cell.min_font_size <= 0:
            errors.append(f"cell '{cell.id}' min_font_size must be positive")
        effective_font_size = cell.font_size if cell.font_size is not None else document.theme.cell_text_size
        effective_min_font_size = cell.min_font_size if cell.min_font_size is not None else document.layout.min_font_size
        if effective_min_font_size > effective_font_size:
            errors.append(
                f"cell '{cell.id}' effective min_font_size {effective_min_font_size} "
                f"cannot exceed font_size {effective_font_size}"
            )
        if cell.padding is not None and cell.padding < 0:
            errors.append(f"cell '{cell.id}' padding must be non-negative")

    layout = document.layout
    positive_layout = {
        "ingredient_column_min_width": layout.ingredient_column_min_width,
        "ingredient_column_max_width": layout.ingredient_column_max_width,
        "default_stage_width": layout.default_stage_width,
        "row_height": layout.row_height,
        "title_height": layout.title_height,
        "text_line_spacing": layout.text_line_spacing,
        "min_font_size": layout.min_font_size,
    }
    for name, value in positive_layout.items():
        if value <= 0:
            errors.append(f"layout.{name} must be positive")
    if layout.ingredient_column_width is not None and layout.ingredient_column_width <= 0:
        errors.append("layout.ingredient_column_width must be positive when set")
    if layout.ingredient_column_min_width > layout.ingredient_column_max_width:
        errors.append("layout.ingredient_column_min_width cannot exceed ingredient_column_max_width")
    for name, value in (("footer_height", layout.footer_height), ("cell_padding", layout.cell_padding)):
        if value < 0:
            errors.append(f"layout.{name} must be non-negative")

    padding = document.canvas.padding
    for name, value in (("top", padding.top), ("right", padding.right), ("bottom", padding.bottom), ("left", padding.left)):
        if value < 0:
            errors.append(f"canvas.padding.{name} must be non-negative")
    if document.canvas.width is not None and document.canvas.width <= 0:
        errors.append("canvas.width must be positive")
    if document.canvas.height is not None and document.canvas.height <= 0:
        errors.append("canvas.height must be positive")

    theme = document.theme
    colors = {
        "theme.border_color": theme.border_color,
        "theme.cell_background": theme.cell_background,
        "theme.background": theme.background,
        "theme.text_color": theme.text_color,
        "theme.secondary_text_color": theme.secondary_text_color,
    }
    if document.canvas.background is not None:
        colors["canvas.background"] = document.canvas.background
    for path, color in colors.items():
        if not _HEX_COLOR_PATTERN.fullmatch(color):
            errors.append(f"{path} must be a CSS hex color, got {color!r}")
    if theme.border_width <= 0:
        errors.append("theme.border_width must be positive")
    if theme.outer_border_width is not None and theme.outer_border_width <= 0:
        errors.append("theme.outer_border_width must be positive")
    for name, value in (("title_size", theme.title_size), ("subtitle_size", theme.subtitle_size), ("cell_text_size", theme.cell_text_size), ("footer_size", theme.footer_size)):
        if value <= 0:
            errors.append(f"theme.{name} must be positive")
    if layout.min_font_size > theme.cell_text_size:
        errors.append("layout.min_font_size cannot exceed theme.cell_text_size")
    if not theme.font_family or any(not family.strip() for family in theme.font_family):
        errors.append("theme.font_family must contain non-empty font names")

    validation_ingredient_width = (
        layout.ingredient_column_width
        if layout.ingredient_column_width is not None
        else layout.ingredient_column_min_width
    )
    minimum_width = padding.left + validation_ingredient_width + sum(
        stage.width if stage.width is not None else layout.default_stage_width for stage in document.stages
    ) + padding.right
    if document.canvas.width is not None and document.canvas.width < minimum_width:
        errors.append(f"canvas.width {document.canvas.width} is too small; layout requires at least {minimum_width}")

    valid_cells: list[tuple[ProcessCell, tuple[int, int, int, int]]] = []
    for cell in document.cells:
        indices = _range_indices(cell, row_index, stage_index)
        if indices is not None and indices[0] <= indices[1] and indices[2] <= indices[3]:
            valid_cells.append((cell, indices))
    for index, (first, a) in enumerate(valid_cells):
        for second, b in valid_cells[index + 1 :]:
            rows_overlap = max(a[0], b[0]) <= min(a[1], b[1])
            stages_overlap = max(a[2], b[2]) <= min(a[3], b[3])
            if rows_overlap and stages_overlap and not (first.allow_overlap or second.allow_overlap):
                row_start = row_ids[max(a[0], b[0])]
                row_end = row_ids[min(a[1], b[1])]
                stage_start = stage_ids[max(a[2], b[2])]
                stage_end = stage_ids[min(a[3], b[3])]
                stage_text = f"stage '{stage_start}'" if stage_start == stage_end else f"stages {stage_start}..{stage_end}"
                errors.append(
                    f"cells '{first.id}' and '{second.id}' overlap at rows {row_start}..{row_end} and {stage_text}"
                )

    if errors:
        message = "recipe validation failed:\n- " + "\n- ".join(errors)
        raise RecipeValidationError(message)


def validate_output_base(path: str | Path) -> Path:
    """Check that an output base path has a writable directory or ancestor."""

    output = Path(path)
    parent = output.parent
    probe = parent
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    if not probe.is_dir() or not os.access(probe, os.W_OK):
        raise LayoutError(f"output directory '{parent}' is not writable")
    return output
