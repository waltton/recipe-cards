"""YAML parsing and schema conversion tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from recipe_card.exceptions import RecipeValidationError
from recipe_card.loader import load_recipe, loads_recipe


ROOT = Path(__file__).resolve().parents[1]


def test_valid_file_loads() -> None:
    document = load_recipe(ROOT / "examples" / "hatch_chile_truffles.yaml")
    assert document.version == 1
    assert document.card.title == "Hatch Chile Infused Chocolate Truffles"
    assert len(document.rows) == 4
    assert len(document.cells) == 10


def test_missing_required_field_fails() -> None:
    with pytest.raises(RecipeValidationError, match=r"card\.title is required"):
        loads_recipe("version: 1\ncard: {}\nrows: []\nstages: []\ncells: []\n")


def test_invalid_yaml_fails() -> None:
    with pytest.raises(RecipeValidationError, match="invalid YAML"):
        loads_recipe("version: [\n")


def test_unknown_schema_field_fails() -> None:
    source = """
version: 1
card: {title: Tiny}
rows: [{id: a, label: A, typo: true}]
stages: [{id: one}]
cells: []
"""
    with pytest.raises(RecipeValidationError, match="unknown field"):
        loads_recipe(source)


def test_compact_syntax_normalizes_to_typed_models() -> None:
    document = loads_recipe("""
version: 1
card: {title: Compact}
ingredients:
  pasta: 12 oz pasta
  sauce:
    label: 2 cups sauce
    height: 88
stages:
  prep: 240
  finish:
  serve: 180
steps:
  - stage: prep..finish
    rows: pasta
    text: cook and drain
  - id: combine
    stage: serve
    rows: pasta..sauce
    text: combine
""")
    assert [(row.id, row.label, row.height) for row in document.rows] == [
        ("pasta", "12 oz pasta", None),
        ("sauce", "2 cups sauce", 88),
    ]
    assert [(stage.id, stage.width) for stage in document.stages] == [
        ("prep", 240),
        ("finish", None),
        ("serve", 180),
    ]
    assert document.cells[0].id == "step_1"
    assert document.cells[0].stage_start == "prep"
    assert document.cells[0].stage_end == "finish"
    assert document.cells[0].rows.from_id == document.cells[0].rows.to_id == "pasta"
    assert document.cells[1].id == "combine"
    assert document.cells[1].rows.from_id == "pasta"
    assert document.cells[1].rows.to_id == "sauce"


def test_grocery_sections_preserve_ingredient_categories() -> None:
    document = loads_recipe("""
version: 1
card: {title: Groceries}
ingredients:
  Pantry: {pasta: 12 oz pasta}
  Produce: {tomatoes: 2 cups tomatoes}
actions:
  cooked: {from: pasta, do: cook}
  served: {from: [cooked, tomatoes], do: serve}
final: served
""")
    assert [(row.id, row.category) for row in document.rows] == [
        ("pasta", "Pantry"),
        ("tomatoes", "Produce"),
    ]


def test_compact_and_expanded_sections_cannot_be_mixed() -> None:
    source = """
version: 1
card: {title: Mixed}
ingredients: {item: Ingredient}
rows: [{id: item, label: Ingredient}]
stages: {only: 200}
steps: []
"""
    with pytest.raises(RecipeValidationError, match="both 'rows' and 'ingredients'"):
        loads_recipe(source)


def test_reverse_flow_tree_compiles_actions_and_waits() -> None:
    document = loads_recipe("""
version: 1
card: {title: Tree}
flow:
  serve:
    do: serve
    from:
      combined:
        do: combine
        from:
          cooked:
            do: cook
            from:
              base: 1 cup base
          salt: salt
      garnish: garnish
""")
    assert [row.id for row in document.rows] == ["base", "salt", "garnish"]
    assert [stage.id for stage in document.stages] == ["flow_stage_1", "flow_stage_2", "flow_stage_3"]
    cells = {cell.id: cell for cell in document.cells}
    assert cells["cooked"].rows == cells["cooked"].rows.__class__("base", "base")
    assert cells["combined"].rows.from_id == "base"
    assert cells["combined"].rows.to_id == "salt"
    assert cells["serve"].stage_start == "flow_stage_3"
    waits = [cell for cell in document.cells if cell.id.startswith("flow_wait_")]
    assert len(waits) == 2
    assert any(wait.rows.from_id == "garnish" and wait.stage_end == "flow_stage_2" for wait in waits)


def test_flow_cannot_be_combined_with_explicit_geometry() -> None:
    source = """
version: 1
card: {title: Conflict}
flow:
  finish: {do: finish, from: {item: Ingredient}}
stages: {only: 200}
"""
    with pytest.raises(RecipeValidationError, match="flow cannot be combined"):
        loads_recipe(source)


def test_flow_root_must_be_an_action() -> None:
    with pytest.raises(RecipeValidationError, match="flow root must be a final action"):
        loads_recipe("version: 1\ncard: {title: Bad root}\nflow: {item: Ingredient}\n")


def test_flat_dependencies_compile_to_the_same_semantic_geometry() -> None:
    document = loads_recipe("""
version: 1
card: {title: Dependencies}
ingredients:
  pasta: 12 oz pasta
  salt: salt
  garnish: parsley
actions:
  cooked:
    from: pasta
    do: cook
  combined:
    from: [cooked, salt]
    do: combine
  served:
    from: [combined, garnish]
    do: serve
final: served
""")
    assert [row.id for row in document.rows] == ["pasta", "salt", "garnish"]
    assert len(document.stages) == 3
    cells = {cell.id: cell for cell in document.cells}
    assert cells["cooked"].stage_start == "flow_stage_1"
    assert cells["combined"].rows.to_id == "salt"
    assert cells["served"].rows.to_id == "garnish"
    assert any(cell.text == "" and cell.rows.from_id == "garnish" for cell in document.cells)


def test_flat_dependencies_reject_cycles() -> None:
    source = """
version: 1
card: {title: Cycle}
ingredients: {item: Ingredient}
actions:
  first: {from: second, do: first}
  second: {from: first, do: second}
final: first
"""
    with pytest.raises(RecipeValidationError, match="dependency cycle"):
        loads_recipe(source)


def test_flat_dependencies_reject_fan_out() -> None:
    source = """
version: 1
card: {title: Split}
ingredients: {item: Ingredient}
actions:
  first: {from: item, do: first}
  second: {from: item, do: second}
  finish: {from: [first, second], do: finish}
final: finish
"""
    with pytest.raises(RecipeValidationError, match="cannot split a result"):
        loads_recipe(source)
