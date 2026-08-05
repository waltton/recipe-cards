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
    assert '<link rel="icon" type="image/png" href="../../assets/favicon.png">' in html
    assert '<script src="../../assets/site.js"></script>' in html
    assert "<svg" not in html


def test_same_recipe_page_renders_identically(hatch_recipe) -> None:
    first = render_recipe_page(hatch_recipe, site_title="Recipe Cards")
    second = render_recipe_page(hatch_recipe, site_title="Recipe Cards")
    assert first == second


def test_phone_view_groups_actions_into_swipeable_stages(chicken_recipe) -> None:
    html = render_recipe_page(chicken_recipe, site_title="Recipe Cards")
    assert 'data-mobile-process' in html
    assert 'data-stage-position aria-live="polite">Stage 0 of 5' in html
    assert '<section class="mobile-stage mobile-grocery-stage" data-stage-number="0" role="listitem">' in html
    assert html.count('role="listitem">') == 6
    assert html.count('type="checkbox" data-grocery-id=') == 12
    assert "Check off ingredients as you shop." in html
    assert 'class="mobile-grocery-section" aria-label="Pantry"' in html
    assert '<h3>Produce</h3>' in html
    assert "340g pasta" in html
    assert "Swipe through the recipe" in html
    assert "cook in salted water\nuntil al dente;\nreserve 120 mL water" in html
    assert 'data-action-id="pasta_cooked"' in html
    assert html.count('class="mobile-action"') == 11
    assert 'data-action-id="sauce"' in html
    assert 'data-action-id="serve"' in html
    assert 'class="mobile-flow-parent"' not in html
    assert '<span>Roux</span><span>2 cups (475 mL) milk</span><span>1 cup grated Parmesan</span><span>2 cups fresh spinach</span>' in html
    assert 'class="mobile-flow-lane' not in html
    assert 'class="mobile-flow-out' not in html


def test_notes_render_after_the_card_without_a_dropdown(chicken_recipe) -> None:
    html = render_recipe_page(chicken_recipe, site_title="Recipe Cards")
    notes = '<section class="recipe-notes" aria-labelledby="recipe-notes-title">'
    assert notes in html
    assert html.index(notes) > html.index('<section class="diagram-section"')
    assert html.index(notes) > html.index('<section class="mobile-process"')
    assert "Cook pasta according to its package directions." in html
    assert "<details" not in html
    assert "<summary" not in html
    assert "notes-panel" not in html
