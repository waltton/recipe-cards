"""SVG correctness and determinism tests."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from recipe_card.loader import loads_recipe
from recipe_card.renderer_svg import SVG_NS, render_svg


def test_output_contains_valid_root_svg(hatch_recipe) -> None:
    root = ET.fromstring(render_svg(hatch_recipe))
    assert root.tag == f"{{{SVG_NS}}}svg"
    assert root.attrib["viewBox"].startswith("0 0 ")


def test_title_and_special_characters_are_xml_escaped() -> None:
    recipe = loads_recipe("""
version: 1
card: {title: "Fish & Chips <Fast>"}
rows: [{id: fish, label: "salt & pepper <optional>"}]
stages: [{id: cook, width: 300}]
cells:
  - id: fry
    stage_start: cook
    stage_end: cook
    rows: {from: fish, to: fish}
    text: "heat < oil & fry"
""")
    svg = render_svg(recipe)
    assert "Fish &amp; Chips &lt;Fast&gt;" in svg
    assert "salt &amp; pepper &lt;optional&gt;" in svg
    assert "heat &lt; oil &amp; fry" in svg
    ET.fromstring(svg)


def test_empty_cells_render_and_border_color_is_present(hatch_recipe) -> None:
    svg = render_svg(hatch_recipe)
    assert 'id="cell-flow_wait_1"' in svg
    assert 'stroke="#4b9847"' in svg


def test_same_document_renders_identically(hatch_recipe) -> None:
    assert render_svg(hatch_recipe) == render_svg(hatch_recipe)


def test_debug_layout_adds_ids_without_changing_dimensions(hatch_recipe) -> None:
    normal = ET.fromstring(render_svg(hatch_recipe))
    debug_svg = render_svg(hatch_recipe, debug=True)
    debug = ET.fromstring(debug_svg)
    assert normal.attrib["viewBox"] == debug.attrib["viewBox"]
    assert 'id="debug-layout"' in debug_svg
    assert "melted_chocolate (" in debug_svg


def test_font_size_is_consistent_across_the_grid(chicken_recipe) -> None:
    root = ET.fromstring(render_svg(chicken_recipe))
    ingredient_sizes = {
        element.attrib["font-size"]
        for element in root.iter(f"{{{SVG_NS}}}text")
        if element.attrib.get("class") == "ingredient-text"
    }
    process_sizes = {
        element.attrib["font-size"]
        for element in root.iter(f"{{{SVG_NS}}}text")
        if element.attrib.get("class") == "process-text"
    }
    assert ingredient_sizes == {"30"}
    assert process_sizes == {"30"}
    assert ingredient_sizes == process_sizes
