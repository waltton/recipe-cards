"""Compile semantic reverse recipe trees into explicit grid geometry models."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import ceil
from typing import Any

from .exceptions import RecipeValidationError
from .models import IngredientRow, LayoutConfig, ProcessCell, RowRange, Stage, ThemeConfig
from .text import measure_text_width


@dataclass(frozen=True)
class _FlowNode:
    id: str
    ingredient: str | None = None
    height: int | None = None
    text: str | None = None
    children: tuple["_FlowNode", ...] = ()
    stage_width: int | None = None
    font_size: int | None = None
    min_font_size: int | None = None
    font_weight: str = "normal"
    align: str = "center"
    valign: str = "middle"
    padding: int | None = None

    @property
    def is_ingredient(self) -> bool:
        return self.ingredient is not None


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str):
        raise RecipeValidationError(f"{path} must be a string")
    return value


def _integer(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise RecipeValidationError(f"{path} must be an integer")
    return value


def _parse_node(
    node_id: Any,
    value: Any,
    *,
    path: str,
    seen_ids: set[str],
    active_mappings: set[int],
) -> _FlowNode:
    identifier = _string(node_id, f"{path} key")
    if identifier in seen_ids:
        raise RecipeValidationError(f"flow node ID '{identifier}' is used more than once")
    seen_ids.add(identifier)
    node_path = f"{path}.{identifier}"
    if isinstance(value, str):
        return _FlowNode(id=identifier, ingredient=value)
    if not isinstance(value, Mapping):
        raise RecipeValidationError(f"{node_path} must be an ingredient string or action mapping")
    object_id = id(value)
    if object_id in active_mappings:
        raise RecipeValidationError(f"{node_path} contains a recursive YAML alias")
    active_mappings.add(object_id)
    try:
        if "ingredient" in value:
            unknown = sorted(set(value) - {"ingredient", "height"})
            if unknown:
                raise RecipeValidationError(f"{node_path} contains unknown field(s): {', '.join(map(repr, unknown))}")
            raw_height = value.get("height")
            return _FlowNode(
                id=identifier,
                ingredient=_string(value["ingredient"], f"{node_path}.ingredient"),
                height=None if raw_height is None else _integer(raw_height, f"{node_path}.height"),
            )

        allowed = {
            "do",
            "from",
            "stage_width",
            "font_size",
            "min_font_size",
            "font_weight",
            "align",
            "valign",
            "padding",
        }
        unknown = sorted(set(value) - allowed)
        if unknown:
            raise RecipeValidationError(f"{node_path} contains unknown field(s): {', '.join(map(repr, unknown))}")
        if "do" not in value:
            raise RecipeValidationError(f"{node_path}.do is required for an action node")
        if "from" not in value:
            raise RecipeValidationError(f"{node_path}.from is required for an action node")
        raw_children = value["from"]
        if not isinstance(raw_children, Mapping) or not raw_children:
            raise RecipeValidationError(f"{node_path}.from must be a non-empty mapping")
        children = tuple(
            _parse_node(
                child_id,
                child_value,
                path=f"{node_path}.from",
                seen_ids=seen_ids,
                active_mappings=active_mappings,
            )
            for child_id, child_value in raw_children.items()
        )
        raw_stage_width = value.get("stage_width")
        raw_font_size = value.get("font_size")
        raw_min_font_size = value.get("min_font_size")
        raw_padding = value.get("padding")
        return _FlowNode(
            id=identifier,
            text=_string(value["do"], f"{node_path}.do"),
            children=children,
            stage_width=None if raw_stage_width is None else _integer(raw_stage_width, f"{node_path}.stage_width"),
            font_size=None if raw_font_size is None else _integer(raw_font_size, f"{node_path}.font_size"),
            min_font_size=None if raw_min_font_size is None else _integer(raw_min_font_size, f"{node_path}.min_font_size"),
            font_weight=_string(value.get("font_weight", "normal"), f"{node_path}.font_weight"),
            align=_string(value.get("align", "center"), f"{node_path}.align"),
            valign=_string(value.get("valign", "middle"), f"{node_path}.valign"),
            padding=None if raw_padding is None else _integer(raw_padding, f"{node_path}.padding"),
        )
    finally:
        active_mappings.remove(object_id)


def _walk(node: _FlowNode) -> tuple[_FlowNode, ...]:
    result = [node]
    for child in node.children:
        result.extend(_walk(child))
    return tuple(result)


def compile_flow(
    data: Any,
    layout: LayoutConfig,
    theme: ThemeConfig,
) -> tuple[tuple[IngredientRow, ...], tuple[Stage, ...], tuple[ProcessCell, ...]]:
    """Compile one final-action-rooted tree into rows, stages, actions, and waits."""

    if not isinstance(data, Mapping) or len(data) != 1:
        raise RecipeValidationError("flow must be a mapping containing exactly one final action root")
    root_id, root_value = next(iter(data.items()))
    root = _parse_node(root_id, root_value, path="flow", seen_ids=set(), active_mappings=set())
    if root.is_ingredient:
        raise RecipeValidationError("flow root must be a final action, not an ingredient")

    all_nodes = _walk(root)
    leaves = tuple(node for node in all_nodes if node.is_ingredient)
    actions = tuple(node for node in all_nodes if not node.is_ingredient)
    rows = tuple(IngredientRow(id=node.id, label=node.ingredient or "", height=node.height) for node in leaves)
    row_index = {row.id: index for index, row in enumerate(rows)}

    depths: dict[str, int] = {}

    def depth(node: _FlowNode) -> int:
        if node.is_ingredient:
            depths[node.id] = 0
            return 0
        value = max(depth(child) for child in node.children) + 1
        depths[node.id] = value
        return value

    maximum_depth = depth(root)
    explicit_widths: dict[int, int] = {}
    for action in actions:
        if action.stage_width is not None:
            stage_number = depths[action.id]
            explicit_widths[stage_number] = max(explicit_widths.get(stage_number, 0), action.stage_width)
    automatic_widths: dict[int, int] = {}
    minimum_stage_width = max(1, layout.default_stage_width // 2)
    for number in range(1, maximum_depth + 1):
        actions_at_depth = tuple(action for action in actions if depths[action.id] == number)
        natural_width = max(
            (
                ceil(
                    measure_text_width(
                        action.text or "",
                        action.font_size if action.font_size is not None else theme.cell_text_size,
                        bold=action.font_weight == "bold"
                        or (action.font_weight.isdigit() and int(action.font_weight) >= 600),
                    )
                    + 2 * (action.padding if action.padding is not None else layout.cell_padding)
                )
                for action in actions_at_depth
            ),
            default=minimum_stage_width,
        )
        automatic_widths[number] = min(
            layout.default_stage_width,
            max(minimum_stage_width, natural_width),
        )
    stages = tuple(
        Stage(
            id=f"flow_stage_{number}",
            width=explicit_widths.get(number, automatic_widths[number]),
        )
        for number in range(1, maximum_depth + 1)
    )

    descendants: dict[str, tuple[str, ...]] = {}

    def descendant_rows(node: _FlowNode) -> tuple[str, ...]:
        if node.is_ingredient:
            result = (node.id,)
        else:
            result = tuple(row_id for child in node.children for row_id in descendant_rows(child))
        descendants[node.id] = result
        return result

    descendant_rows(root)
    cells: list[ProcessCell] = []
    for action in actions:
        action_rows = descendants[action.id]
        stage_id = f"flow_stage_{depths[action.id]}"
        cells.append(
            ProcessCell(
                id=action.id,
                stage_start=stage_id,
                stage_end=stage_id,
                rows=RowRange(from_id=action_rows[0], to_id=action_rows[-1]),
                text=action.text or "",
                font_size=action.font_size,
                min_font_size=action.min_font_size,
                font_weight=action.font_weight,
                align=action.align,  # type: ignore[arg-type]
                valign=action.valign,  # type: ignore[arg-type]
                padding=action.padding,
            )
        )

    used_cell_ids = {cell.id for cell in cells}
    wait_number = 1

    def next_wait_id() -> str:
        nonlocal wait_number
        while f"flow_wait_{wait_number}" in used_cell_ids:
            wait_number += 1
        result = f"flow_wait_{wait_number}"
        used_cell_ids.add(result)
        wait_number += 1
        return result

    for parent in actions:
        parent_depth = depths[parent.id]
        for child in parent.children:
            child_depth = depths[child.id]
            if parent_depth - child_depth <= 1:
                continue
            child_rows = descendants[child.id]
            cells.append(
                ProcessCell(
                    id=next_wait_id(),
                    stage_start=f"flow_stage_{child_depth + 1}",
                    stage_end=f"flow_stage_{parent_depth - 1}",
                    rows=RowRange(from_id=child_rows[0], to_id=child_rows[-1]),
                    text="",
                )
            )

    stage_index = {stage.id: index for index, stage in enumerate(stages)}
    cells.sort(
        key=lambda cell: (
            stage_index[cell.stage_start],
            row_index[cell.rows.from_id],
            stage_index[cell.stage_end],
            cell.id,
        )
    )
    return rows, stages, tuple(cells)
