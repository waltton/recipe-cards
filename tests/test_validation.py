"""Semantic recipe validation tests."""

from __future__ import annotations

import pytest

from recipe_card.exceptions import RecipeValidationError
from recipe_card.loader import loads_recipe


def _recipe(*, rows: str = "[{id: a, label: A}, {id: b, label: B}]", stages: str = "[{id: one}, {id: two}]", cells: str = "[]", extra: str = "") -> str:
    return f"""
version: 1
card: {{title: Test}}
rows: {rows}
stages: {stages}
cells: {cells}
{extra}
"""


def test_duplicate_row_id_fails() -> None:
    with pytest.raises(RecipeValidationError, match="duplicate row ID 'a'"):
        loads_recipe(_recipe(rows="[{id: a, label: A}, {id: a, label: B}]"))


def test_duplicate_stage_id_fails() -> None:
    with pytest.raises(RecipeValidationError, match="duplicate stage ID 'one'"):
        loads_recipe(_recipe(stages="[{id: one}, {id: one}]"))


def test_unknown_cell_row_reference_fails() -> None:
    cells = "[{id: action, stage_start: one, stage_end: one, rows: {from: missing, to: b}}]"
    with pytest.raises(RecipeValidationError, match="unknown row 'missing'"):
        loads_recipe(_recipe(cells=cells))


def test_unknown_cell_stage_reference_fails() -> None:
    cells = "[{id: action, stage_start: missing, stage_end: one, rows: {from: a, to: a}}]"
    with pytest.raises(RecipeValidationError, match="unknown stage 'missing'"):
        loads_recipe(_recipe(cells=cells))


def test_reversed_ranges_fail() -> None:
    cells = "[{id: action, stage_start: two, stage_end: one, rows: {from: b, to: a}}]"
    with pytest.raises(RecipeValidationError) as raised:
        loads_recipe(_recipe(cells=cells))
    assert "row range is reversed" in str(raised.value)
    assert "stage range is reversed" in str(raised.value)


def test_touching_cells_do_not_overlap() -> None:
    cells = """[
      {id: first, stage_start: one, stage_end: one, rows: {from: a, to: a}},
      {id: second, stage_start: two, stage_end: two, rows: {from: a, to: a}},
      {id: third, stage_start: one, stage_end: one, rows: {from: b, to: b}}
    ]"""
    document = loads_recipe(_recipe(cells=cells))
    assert len(document.cells) == 3


def test_intersecting_cells_fail_with_ranges() -> None:
    cells = """[
      {id: broad, stage_start: one, stage_end: two, rows: {from: a, to: b}},
      {id: collision, stage_start: two, stage_end: two, rows: {from: b, to: b}}
    ]"""
    with pytest.raises(RecipeValidationError) as raised:
        loads_recipe(_recipe(cells=cells))
    message = str(raised.value)
    assert "cells 'broad' and 'collision' overlap" in message
    assert "rows b..b" in message
    assert "stage 'two'" in message


def test_explicitly_allowed_overlap_loads() -> None:
    cells = """[
      {id: broad, stage_start: one, stage_end: two, rows: {from: a, to: b}, allow_overlap: true},
      {id: collision, stage_start: two, stage_end: two, rows: {from: b, to: b}}
    ]"""
    assert len(loads_recipe(_recipe(cells=cells)).cells) == 2


def test_invalid_color_and_small_canvas_fail() -> None:
    extra = "canvas: {width: 10}\ntheme: {border_color: green}"
    with pytest.raises(RecipeValidationError) as raised:
        loads_recipe(_recipe(extra=extra))
    assert "CSS hex color" in str(raised.value)
    assert "too small" in str(raised.value)


def test_effective_minimum_font_size_cannot_exceed_start_size() -> None:
    cells = "[{id: action, stage_start: one, stage_end: one, rows: {from: a, to: a}, font_size: 12}]"
    with pytest.raises(RecipeValidationError, match="effective min_font_size 18 cannot exceed font_size 12"):
        loads_recipe(_recipe(cells=cells))
