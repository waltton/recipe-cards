"""Cumulative row/stage layout and border tests."""

from __future__ import annotations

from recipe_card.layout import compute_layout
from recipe_card.loader import loads_recipe


def test_row_positions_are_cumulative(hatch_recipe) -> None:
    layout = compute_layout(hatch_recipe)
    grid_top = hatch_recipe.canvas.padding.top + layout.title_height
    assert layout.row_tops["chocolate"] == grid_top
    assert layout.row_tops["cream"] == grid_top + 96
    assert layout.row_tops["chiles"] == grid_top + 96 + 72
    assert layout.row_bottoms["cocoa"] == grid_top + 96 + 72 + 72 + 72


def test_stage_positions_are_cumulative(hatch_recipe) -> None:
    layout = compute_layout(hatch_recipe)
    process_left = hatch_recipe.canvas.padding.left + layout.ingredient_column_width
    first, second, third = hatch_recipe.stages[:3]
    assert layout.stage_lefts[first.id] == process_left
    assert layout.stage_rights[first.id] == process_left + first.width
    assert layout.stage_lefts[third.id] == process_left + first.width + second.width


def test_multi_row_and_multi_stage_cell_geometry(hatch_recipe) -> None:
    layout = compute_layout(hatch_recipe)
    boxes = {item.id: item.box for item in layout.process_boxes}
    melt = boxes["melted_chocolate"]
    assert melt.width == hatch_recipe.stages[0].width
    assert melt.height == 96
    puree = boxes["chile_cream"]
    assert puree.width == hatch_recipe.stages[1].width
    assert puree.height == 72 + 72
    dust = boxes["dust"]
    assert dust.height == 96 + 72 + 72 + 72


def test_automatic_canvas_size_matches_grid(hatch_recipe) -> None:
    layout = compute_layout(hatch_recipe)
    expected_width = 40 + layout.ingredient_column_width + sum(stage.width for stage in hatch_recipe.stages) + 40
    assert layout.canvas_width == expected_width
    assert layout.grid_box.right == expected_width - 40


def test_ingredient_column_width_is_measured_and_clamped() -> None:
    short = loads_recipe("""
version: 1
card: {title: Short}
rows: [{id: item, label: Salt}]
stages: [{id: only}]
cells: []
""")
    long = loads_recipe("""
version: 1
card: {title: Long}
rows: [{id: item, label: A substantially longer ingredient label for measurement}]
stages: [{id: only}]
cells: []
""")
    short_layout = compute_layout(short)
    long_layout = compute_layout(long)
    assert short_layout.ingredient_column_width == short.layout.ingredient_column_min_width
    assert long_layout.ingredient_column_width > short_layout.ingredient_column_width
    assert long_layout.ingredient_column_width <= long.layout.ingredient_column_max_width


def test_explicit_ingredient_column_width_remains_fixed() -> None:
    document = loads_recipe("""
version: 1
card: {title: Fixed width}
layout: {ingredient_column_width: 444}
rows: [{id: item, label: Ingredient}]
stages: [{id: only}]
cells: []
""")
    assert compute_layout(document).ingredient_column_width == 444


def test_shared_borders_are_deduplicated(hatch_recipe) -> None:
    layout = compute_layout(hatch_recipe)
    # The melted chocolate action ends exactly where its inferred wait cell starts.
    boundary_x = layout.stage_rights["flow_stage_1"]
    chocolate_top = layout.row_tops["chocolate"]
    chocolate_bottom = layout.row_bottoms["chocolate"]
    matching = [
        segment
        for segment in layout.border_segments
        if segment.orientation == "vertical"
        and segment.fixed == boundary_x
        and segment.start <= chocolate_top
        and segment.end >= chocolate_bottom
    ]
    assert len(matching) == 1


def test_grid_has_complete_outer_boundary(hatch_recipe) -> None:
    layout = compute_layout(hatch_recipe)
    grid = layout.grid_box
    assert any(
        segment.orientation == "horizontal"
        and segment.fixed == grid.y
        and segment.start == grid.x
        and segment.end == grid.right
        for segment in layout.border_segments
    )
    assert any(
        segment.orientation == "vertical"
        and segment.fixed == grid.right
        and segment.start == grid.y
        and segment.end == grid.bottom
        for segment in layout.border_segments
    )


def test_process_text_expands_automatic_rows() -> None:
    document = loads_recipe("""
version: 1
card: {title: Auto rows}
layout: {row_height: 40, cell_padding: 10}
rows:
  - {id: first, label: First}
  - {id: second, label: Second}
stages: [{id: narrow, width: 100}]
cells:
  - id: tall_action
    stage_start: narrow
    stage_end: narrow
    rows: {from: first, to: second}
    text: "one\ntwo\nthree\nfour"
""")
    computed = compute_layout(document)
    total = computed.row_bottoms["second"] - computed.row_tops["first"]
    assert total >= 151
    first_height = computed.row_bottoms["first"] - computed.row_tops["first"]
    second_height = computed.row_bottoms["second"] - computed.row_tops["second"]
    assert abs(first_height - second_height) <= 1


def test_explicit_row_height_remains_fixed() -> None:
    document = loads_recipe("""
version: 1
card: {title: Fixed row}
rows: [{id: fixed, label: "several words that may wrap", height: 55}]
stages: [{id: only}]
cells: []
""")
    computed = compute_layout(document)
    assert computed.row_bottoms["fixed"] - computed.row_tops["fixed"] == 55
