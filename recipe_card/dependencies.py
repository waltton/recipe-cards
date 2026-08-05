"""Compile flat named-result dependencies through the semantic flow compiler."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Any

from .exceptions import RecipeValidationError
from .flow import compile_flow
from .models import IngredientRow, LayoutConfig, ProcessCell, Stage, ThemeConfig

_ACTION_FIELDS = {
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


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str):
        raise RecipeValidationError(f"{path} must be a string")
    return value


def _references(value: Any, path: str) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or not value:
        raise RecipeValidationError(f"{path} must be an input ID or a non-empty list of input IDs")
    return tuple(_string(item, f"{path}[{index}]") for index, item in enumerate(value))


def compile_dependencies(
    ingredients: tuple[IngredientRow, ...],
    data: Any,
    final: Any,
    layout: LayoutConfig,
    theme: ThemeConfig,
) -> tuple[tuple[IngredientRow, ...], tuple[Stage, ...], tuple[ProcessCell, ...]]:
    """Validate a flat dependency map and compile its final result as a flow tree."""

    if not isinstance(data, Mapping) or not data:
        raise RecipeValidationError("actions must be a non-empty mapping")
    final_id = _string(final, "final")
    ingredient_by_id = {ingredient.id: ingredient for ingredient in ingredients}
    action_data: dict[str, dict[str, Any]] = {}
    action_refs: dict[str, tuple[str, ...]] = {}
    for raw_id, raw_value in data.items():
        action_id = _string(raw_id, "actions key")
        path = f"actions.{action_id}"
        if action_id in ingredient_by_id:
            raise RecipeValidationError(f"ID '{action_id}' cannot be both an ingredient and an action")
        if not isinstance(raw_value, Mapping):
            raise RecipeValidationError(f"{path} must be a mapping")
        unknown = sorted(set(raw_value) - _ACTION_FIELDS)
        if unknown:
            raise RecipeValidationError(f"{path} contains unknown field(s): {', '.join(map(repr, unknown))}")
        if "do" not in raw_value:
            raise RecipeValidationError(f"{path}.do is required")
        if "from" not in raw_value:
            raise RecipeValidationError(f"{path}.from is required")
        action_data[action_id] = dict(raw_value)
        action_refs[action_id] = _references(raw_value["from"], f"{path}.from")

    if final_id not in action_data:
        raise RecipeValidationError(f"final references unknown action '{final_id}'")
    known_ids = set(ingredient_by_id) | set(action_data)
    for action_id, references in action_refs.items():
        for reference in references:
            if reference not in known_ids:
                raise RecipeValidationError(f"action '{action_id}' references unknown input '{reference}'")

    state: dict[str, int] = {}
    reachable_actions: set[str] = set()
    reachable_ingredients: set[str] = set()

    def visit(action_id: str, trail: tuple[str, ...]) -> None:
        if state.get(action_id) == 1:
            cycle = " -> ".join(trail + (action_id,))
            raise RecipeValidationError(f"action dependency cycle: {cycle}")
        if state.get(action_id) == 2:
            reachable_actions.add(action_id)
            return
        state[action_id] = 1
        reachable_actions.add(action_id)
        for reference in action_refs[action_id]:
            if reference in action_data:
                visit(reference, trail + (action_id,))
            else:
                reachable_ingredients.add(reference)
        state[action_id] = 2

    visit(final_id, ())
    unused_actions = sorted(set(action_data) - reachable_actions)
    unused_ingredients = sorted(set(ingredient_by_id) - reachable_ingredients)
    if unused_actions or unused_ingredients:
        details: list[str] = []
        if unused_actions:
            details.append("actions " + ", ".join(unused_actions))
        if unused_ingredients:
            details.append("ingredients " + ", ".join(unused_ingredients))
        raise RecipeValidationError("not connected to final result: " + "; ".join(details))

    consumers = Counter(
        reference
        for action_id in reachable_actions
        for reference in action_refs[action_id]
    )
    shared = sorted(reference for reference, count in consumers.items() if count > 1)
    if shared:
        raise RecipeValidationError(
            "automatic tabular layout cannot split a result into multiple branches; "
            "shared input(s): " + ", ".join(shared)
        )

    def nested_value(identifier: str) -> Any:
        if identifier in ingredient_by_id:
            ingredient = ingredient_by_id[identifier]
            if ingredient.height is None:
                return ingredient.label
            return {"ingredient": ingredient.label, "height": ingredient.height}
        source = action_data[identifier]
        result = {key: value for key, value in source.items() if key != "from"}
        result["from"] = {
            reference: nested_value(reference)
            for reference in action_refs[identifier]
        }
        return result

    rows, stages, cells = compile_flow({final_id: nested_value(final_id)}, layout, theme)
    return tuple(replace(row, category=ingredient_by_id[row.id].category) for row in rows), stages, cells
