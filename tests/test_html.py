"""HTML diagram and recipe-page rendering tests."""

from __future__ import annotations

from html.parser import HTMLParser

from recipe_card.loader import loads_recipe
from recipe_card.renderer_html import render_diagram_html, render_recipe_page


class _Parser(HTMLParser):
    pass


def test_diagram_is_html_not_an_embedded_svg(hatch_recipe) -> None:
    html = render_diagram_html(hatch_recipe)
    assert '<div class="diagram-scaler"' in html
    assert '<div class="recipe-diagram"' in html
    assert '<div class="diagram-cell ingredient-cell' in html
    assert '<span class="diagram-border horizontal"' in html
    assert "<svg" not in html


def test_html_grid_keeps_one_shared_font_size(chicken_recipe) -> None:
    html = render_diagram_html(chicken_recipe)
    assert "--cell-font-size: 30px" in html
    assert "--cell-font-size: 29px" not in html


def test_page_escapes_recipe_content() -> None:
    recipe = loads_recipe("""
version: 1
card: {title: "Fish & Chips <Fast>", subtitle: 'A \"quick\" dish'}
ingredients:
  fish: "salt & pepper <optional>"
actions:
  fry:
    from: fish
    do: "heat < oil & fry"
final: fry
""")
    html = render_recipe_page(recipe, site_title="Test & Kitchen")
    _Parser().feed(html)
    assert "Fish &amp; Chips &lt;Fast&gt;" in html
    assert "salt &amp; pepper &lt;optional&gt;" in html
    assert "heat &lt; oil &amp; fry" in html
    assert '<body class="recipe-body has-mobile-process" style="--recipe-background:' in html
    assert '<script src="../../assets/site.js"></script>' in html
    assert "<svg" not in html


def test_same_recipe_page_renders_identically(hatch_recipe) -> None:
    first = render_recipe_page(hatch_recipe, site_title="Recipe Cards")
    second = render_recipe_page(hatch_recipe, site_title="Recipe Cards")
    assert first == second


def test_phone_view_groups_actions_into_swipeable_stages(chicken_recipe) -> None:
    html = render_recipe_page(chicken_recipe, site_title="Recipe Cards")
    assert 'data-mobile-process' in html
    assert 'data-stage-position aria-live="polite">Stage 1 of 5' in html
    assert html.count('<section class="mobile-stage" role="listitem">') == 5
    assert "Swipe through the recipe" in html
    assert "cook until\nal dente" in html
