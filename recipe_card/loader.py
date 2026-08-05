"""YAML loading and schema-to-dataclass conversion."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

from .dependencies import compile_dependencies
from .exceptions import RecipeValidationError
from .flow import compile_flow
from .models import (
    CanvasConfig,
    CardMetadata,
    IngredientRow,
    LayoutConfig,
    PaddingConfig,
    ProcessCell,
    RecipeDocument,
    RowRange,
    Stage,
    ThemeConfig,
)
from .validation import validate_recipe


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RecipeValidationError(f"{path} must be a mapping")
    return value


def _reject_unknown(data: Mapping[str, Any], allowed: set[str], path: str) -> None:
    unknown = sorted(set(data) - allowed)
    if unknown:
        names = ", ".join(repr(name) for name in unknown)
        raise RecipeValidationError(f"{path} contains unknown field(s): {names}")


def _required(data: Mapping[str, Any], key: str, path: str) -> Any:
    if key not in data:
        raise RecipeValidationError(f"{path}.{key} is required")
    return data[key]


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str):
        raise RecipeValidationError(f"{path} must be a string")
    return value


def _integer(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise RecipeValidationError(f"{path} must be an integer")
    return value


def _number(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RecipeValidationError(f"{path} must be a number")
    return float(value)


def _boolean(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        raise RecipeValidationError(f"{path} must be true or false")
    return value


def _strings(value: Any, path: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise RecipeValidationError(f"{path} must be a list of strings")
    return tuple(_string(item, f"{path}[{index}]") for index, item in enumerate(value))


def _card(data: Any) -> CardMetadata:
    item = _mapping(data, "card")
    _reject_unknown(item, {"title", "subtitle", "source", "footer"}, "card")
    return CardMetadata(
        title=_string(_required(item, "title", "card"), "card.title"),
        subtitle=_string(item.get("subtitle", ""), "card.subtitle"),
        source=_string(item.get("source", ""), "card.source"),
        footer=_strings(item.get("footer", []), "card.footer"),
    )


def _canvas(data: Any) -> CanvasConfig:
    item = _mapping(data, "canvas")
    _reject_unknown(item, {"width", "height", "background", "padding"}, "canvas")
    padding_data = _mapping(item.get("padding", {}), "canvas.padding")
    _reject_unknown(padding_data, {"top", "right", "bottom", "left"}, "canvas.padding")
    padding = PaddingConfig(
        top=_integer(padding_data.get("top", 32), "canvas.padding.top"),
        right=_integer(padding_data.get("right", 40), "canvas.padding.right"),
        bottom=_integer(padding_data.get("bottom", 30), "canvas.padding.bottom"),
        left=_integer(padding_data.get("left", 40), "canvas.padding.left"),
    )
    width = item.get("width")
    height = item.get("height")
    background = item.get("background")
    return CanvasConfig(
        width=None if width is None else _integer(width, "canvas.width"),
        height=None if height is None else _integer(height, "canvas.height"),
        background=None if background is None else _string(background, "canvas.background"),
        padding=padding,
    )


def _theme(data: Any) -> ThemeConfig:
    item = _mapping(data, "theme")
    allowed = {
        "border_color",
        "border_width",
        "outer_border_width",
        "cell_background",
        "background",
        "text_color",
        "secondary_text_color",
        "font_family",
        "title_size",
        "subtitle_size",
        "cell_text_size",
        "footer_size",
    }
    _reject_unknown(item, allowed, "theme")
    fonts_value = item.get("font_family", ["DejaVu Sans", "Arial", "sans-serif"])
    fonts = (_string(fonts_value, "theme.font_family"),) if isinstance(fonts_value, str) else _strings(fonts_value, "theme.font_family")
    outer = item.get("outer_border_width")
    return ThemeConfig(
        border_color=_string(item.get("border_color", "#4b9847"), "theme.border_color"),
        border_width=_number(item.get("border_width", 6), "theme.border_width"),
        outer_border_width=None if outer is None else _number(outer, "theme.outer_border_width"),
        cell_background=_string(item.get("cell_background", "#ffffff"), "theme.cell_background"),
        background=_string(item.get("background", "#fffde8"), "theme.background"),
        text_color=_string(item.get("text_color", "#111111"), "theme.text_color"),
        secondary_text_color=_string(item.get("secondary_text_color", "#4a4a4a"), "theme.secondary_text_color"),
        font_family=fonts,
        title_size=_integer(item.get("title_size", 56), "theme.title_size"),
        subtitle_size=_integer(item.get("subtitle_size", 28), "theme.subtitle_size"),
        cell_text_size=_integer(item.get("cell_text_size", 30), "theme.cell_text_size"),
        footer_size=_integer(item.get("footer_size", 23), "theme.footer_size"),
    )


def _layout(data: Any) -> LayoutConfig:
    item = _mapping(data, "layout")
    allowed = {
        "ingredient_column_width",
        "ingredient_column_min_width",
        "ingredient_column_max_width",
        "default_stage_width",
        "row_height",
        "title_height",
        "footer_height",
        "cell_padding",
        "text_line_spacing",
        "min_font_size",
    }
    _reject_unknown(item, allowed, "layout")
    ingredient_width = item.get("ingredient_column_width")
    return LayoutConfig(
        ingredient_column_width=None if ingredient_width is None else _integer(ingredient_width, "layout.ingredient_column_width"),
        ingredient_column_min_width=_integer(item.get("ingredient_column_min_width", 500), "layout.ingredient_column_min_width"),
        ingredient_column_max_width=_integer(item.get("ingredient_column_max_width", 640), "layout.ingredient_column_max_width"),
        default_stage_width=_integer(item.get("default_stage_width", 280), "layout.default_stage_width"),
        row_height=_integer(item.get("row_height", 72), "layout.row_height"),
        title_height=_integer(item.get("title_height", 145), "layout.title_height"),
        footer_height=_integer(item.get("footer_height", 75), "layout.footer_height"),
        cell_padding=_integer(item.get("cell_padding", 16), "layout.cell_padding"),
        text_line_spacing=_number(item.get("text_line_spacing", 1.12), "layout.text_line_spacing"),
        min_font_size=_integer(item.get("min_font_size", 18), "layout.min_font_size"),
    )


def _rows(data: Any) -> tuple[IngredientRow, ...]:
    if not isinstance(data, Sequence) or isinstance(data, (str, bytes)):
        raise RecipeValidationError("rows must be a list")
    rows: list[IngredientRow] = []
    for index, value in enumerate(data):
        path = f"rows[{index}]"
        item = _mapping(value, path)
        _reject_unknown(item, {"id", "label", "height"}, path)
        height = item.get("height")
        rows.append(
            IngredientRow(
                id=_string(_required(item, "id", path), f"{path}.id"),
                label=_string(_required(item, "label", path), f"{path}.label"),
                height=None if height is None else _integer(height, f"{path}.height"),
            )
        )
    return tuple(rows)


def _ingredients(data: Any) -> tuple[IngredientRow, ...]:
    """Parse compact ingredients, optionally grouped by grocery section."""

    items = _mapping(data, "ingredients")
    rows: list[IngredientRow] = []

    def append_ingredient(raw_id: Any, value: Any, path: str, category: str = "") -> None:
        row_id = _string(raw_id, f"{path} key")
        if isinstance(value, str):
            rows.append(IngredientRow(id=row_id, label=value, category=category))
            return
        item = _mapping(value, path)
        _reject_unknown(item, {"label", "height"}, path)
        height = item.get("height")
        rows.append(
            IngredientRow(
                id=row_id,
                label=_string(_required(item, "label", path), f"{path}.label"),
                height=None if height is None else _integer(height, f"{path}.height"),
                category=category,
            )
        )

    for raw_id, value in items.items():
        name = _string(raw_id, "ingredients key")
        path = f"ingredients.{name}"
        if isinstance(value, Mapping) and "label" not in value and "height" not in value:
            if not value:
                raise RecipeValidationError(f"{path} grocery section must contain at least one ingredient")
            for ingredient_id, ingredient_value in value.items():
                append_ingredient(ingredient_id, ingredient_value, f"{path}.{ingredient_id}", name)
            continue
        append_ingredient(raw_id, value, path)
    return tuple(rows)


def _stages(data: Any) -> tuple[Stage, ...]:
    if isinstance(data, Mapping):
        stages: list[Stage] = []
        for raw_id, value in data.items():
            stage_id = _string(raw_id, "stages key")
            path = f"stages.{stage_id}"
            if value is None:
                width = None
            elif isinstance(value, Mapping):
                _reject_unknown(value, {"width"}, path)
                raw_width = value.get("width")
                width = None if raw_width is None else _integer(raw_width, f"{path}.width")
            else:
                width = _integer(value, path)
            stages.append(Stage(id=stage_id, width=width))
        return tuple(stages)
    if not isinstance(data, Sequence) or isinstance(data, (str, bytes)):
        raise RecipeValidationError("stages must be a mapping or list")
    stages: list[Stage] = []
    for index, value in enumerate(data):
        path = f"stages[{index}]"
        item = _mapping(value, path)
        _reject_unknown(item, {"id", "width"}, path)
        width = item.get("width")
        stages.append(
            Stage(
                id=_string(_required(item, "id", path), f"{path}.id"),
                width=None if width is None else _integer(width, f"{path}.width"),
            )
        )
    return tuple(stages)


def _cells(data: Any) -> tuple[ProcessCell, ...]:
    if not isinstance(data, Sequence) or isinstance(data, (str, bytes)):
        raise RecipeValidationError("cells must be a list")
    cells: list[ProcessCell] = []
    allowed = {
        "id",
        "stage_start",
        "stage_end",
        "rows",
        "text",
        "font_size",
        "min_font_size",
        "font_weight",
        "align",
        "valign",
        "padding",
        "allow_overlap",
    }
    for index, value in enumerate(data):
        path = f"cells[{index}]"
        item = _mapping(value, path)
        _reject_unknown(item, allowed, path)
        range_data = _mapping(_required(item, "rows", path), f"{path}.rows")
        _reject_unknown(range_data, {"from", "to"}, f"{path}.rows")
        font_size = item.get("font_size")
        min_font_size = item.get("min_font_size")
        padding = item.get("padding")
        cells.append(
            ProcessCell(
                id=_string(_required(item, "id", path), f"{path}.id"),
                stage_start=_string(_required(item, "stage_start", path), f"{path}.stage_start"),
                stage_end=_string(_required(item, "stage_end", path), f"{path}.stage_end"),
                rows=RowRange(
                    from_id=_string(_required(range_data, "from", f"{path}.rows"), f"{path}.rows.from"),
                    to_id=_string(_required(range_data, "to", f"{path}.rows"), f"{path}.rows.to"),
                ),
                text=_string(item.get("text", ""), f"{path}.text"),
                font_size=None if font_size is None else _integer(font_size, f"{path}.font_size"),
                min_font_size=None if min_font_size is None else _integer(min_font_size, f"{path}.min_font_size"),
                font_weight=_string(item.get("font_weight", "normal"), f"{path}.font_weight"),
                align=_string(item.get("align", "center"), f"{path}.align"),  # type: ignore[arg-type]
                valign=_string(item.get("valign", "middle"), f"{path}.valign"),  # type: ignore[arg-type]
                padding=None if padding is None else _integer(padding, f"{path}.padding"),
                allow_overlap=_boolean(item.get("allow_overlap", False), f"{path}.allow_overlap"),
            )
        )
    return tuple(cells)


def _span(value: Any, path: str) -> tuple[str, str]:
    text = _string(value, path)
    parts = text.split("..")
    if len(parts) == 1 and parts[0]:
        return parts[0], parts[0]
    if len(parts) == 2 and parts[0] and parts[1]:
        return parts[0], parts[1]
    raise RecipeValidationError(f"{path} must be an ID or an inclusive 'start..end' span")


def _steps(data: Any) -> tuple[ProcessCell, ...]:
    """Parse compact steps with span strings and generated IDs."""

    if not isinstance(data, Sequence) or isinstance(data, (str, bytes)):
        raise RecipeValidationError("steps must be a list")
    cells: list[ProcessCell] = []
    allowed = {
        "id",
        "stage",
        "rows",
        "text",
        "font_size",
        "min_font_size",
        "font_weight",
        "align",
        "valign",
        "padding",
        "allow_overlap",
    }
    for index, value in enumerate(data):
        path = f"steps[{index}]"
        item = _mapping(value, path)
        _reject_unknown(item, allowed, path)
        stage_start, stage_end = _span(_required(item, "stage", path), f"{path}.stage")
        row_start, row_end = _span(_required(item, "rows", path), f"{path}.rows")
        raw_id = item.get("id", f"step_{index + 1}")
        font_size = item.get("font_size")
        min_font_size = item.get("min_font_size")
        padding = item.get("padding")
        cells.append(
            ProcessCell(
                id=_string(raw_id, f"{path}.id"),
                stage_start=stage_start,
                stage_end=stage_end,
                rows=RowRange(from_id=row_start, to_id=row_end),
                text=_string(item.get("text", ""), f"{path}.text"),
                font_size=None if font_size is None else _integer(font_size, f"{path}.font_size"),
                min_font_size=None if min_font_size is None else _integer(min_font_size, f"{path}.min_font_size"),
                font_weight=_string(item.get("font_weight", "normal"), f"{path}.font_weight"),
                align=_string(item.get("align", "center"), f"{path}.align"),  # type: ignore[arg-type]
                valign=_string(item.get("valign", "middle"), f"{path}.valign"),  # type: ignore[arg-type]
                padding=None if padding is None else _integer(padding, f"{path}.padding"),
                allow_overlap=_boolean(item.get("allow_overlap", False), f"{path}.allow_overlap"),
            )
        )
    return tuple(cells)


def _exclusive_key(root: Mapping[str, Any], primary: str, compact: str) -> str:
    if primary in root and compact in root:
        raise RecipeValidationError(f"document cannot contain both '{primary}' and '{compact}'")
    if compact in root:
        return compact
    if primary in root:
        return primary
    raise RecipeValidationError(f"document.{compact} is required (expanded alias: {primary})")


def recipe_from_mapping(data: Any, *, source_path: Path | None = None) -> RecipeDocument:
    """Convert a parsed YAML value to a validated :class:`RecipeDocument`."""

    root = _mapping(data, "document")
    _reject_unknown(
        root,
        {
            "version", "card", "canvas", "theme", "layout", "flow", "ingredients", "actions", "final",
            "rows", "stages", "steps", "cells", "notes",
        },
        "document",
    )
    card = _card(_required(root, "card", "document"))
    canvas = _canvas(root.get("canvas", {}))
    theme = _theme(root.get("theme", {}))
    layout = _layout(root.get("layout", {}))
    if "actions" in root or "final" in root:
        if "actions" not in root or "final" not in root or "ingredients" not in root:
            raise RecipeValidationError("dependency mode requires ingredients, actions, and final")
        conflicts = sorted(set(root) & {"flow", "rows", "stages", "steps", "cells"})
        if conflicts:
            raise RecipeValidationError(
                "document actions/final cannot be combined with section(s): " + ", ".join(conflicts)
            )
        declared_ingredients = _ingredients(root["ingredients"])
        rows, stages, cells = compile_dependencies(
            declared_ingredients,
            root["actions"],
            root["final"],
            layout,
            theme,
        )
    elif "flow" in root:
        conflicts = sorted(set(root) & {"ingredients", "rows", "stages", "steps", "cells"})
        if conflicts:
            raise RecipeValidationError(
                "document.flow cannot be combined with explicit geometry section(s): " + ", ".join(conflicts)
            )
        rows, stages, cells = compile_flow(root["flow"], layout, theme)
    else:
        row_key = _exclusive_key(root, "rows", "ingredients")
        cell_key = _exclusive_key(root, "cells", "steps")
        rows = _ingredients(root[row_key]) if row_key == "ingredients" else _rows(root[row_key])
        stages = _stages(_required(root, "stages", "document"))
        cells = _steps(root[cell_key]) if cell_key == "steps" else _cells(root[cell_key])
    document = RecipeDocument(
        version=_integer(_required(root, "version", "document"), "version"),
        card=card,
        canvas=canvas,
        theme=theme,
        layout=layout,
        rows=rows,
        stages=stages,
        cells=cells,
        notes=_strings(root.get("notes", []), "notes"),
        source_path=source_path,
    )
    validate_recipe(document)
    return document


def loads_recipe(text: str, *, source_path: Path | None = None) -> RecipeDocument:
    """Parse recipe YAML text and return a validated document."""

    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise RecipeValidationError(f"invalid YAML: {exc}") from exc
    if data is None:
        raise RecipeValidationError("recipe YAML is empty")
    return recipe_from_mapping(data, source_path=source_path)


def load_recipe(path: str | Path) -> RecipeDocument:
    """Load and validate a UTF-8 YAML recipe file."""

    source = Path(path)
    try:
        text = source.read_text(encoding="utf-8")
    except OSError as exc:
        raise RecipeValidationError(f"cannot read recipe '{source}': {exc}") from exc
    return loads_recipe(text, source_path=source)
