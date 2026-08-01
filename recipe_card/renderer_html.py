"""Accessible HTML renderer for Recipe Cards diagrams and pages."""

from __future__ import annotations

from html import escape

from .layout import compute_layout
from .models import CellBox, ComputedLayout, RecipeDocument
from .typography import fit_cell_text, shared_font_size


def _number(value: float | int) -> str:
    numeric = float(value)
    return str(int(numeric)) if numeric.is_integer() else f"{numeric:.3f}".rstrip("0").rstrip(".")


def _css_font_family(families: tuple[str, ...]) -> str:
    """Serialize font names without allowing them to escape the declaration."""

    generic = {"serif", "sans-serif", "monospace", "cursive", "fantasy", "system-ui"}
    values: list[str] = []
    for family in families:
        if family.lower() in generic:
            values.append(family.lower())
            continue
        safe = family.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").replace("\r", " ")
        values.append(f'"{safe}"')
    return ", ".join(values)


def _style(**values: str | int | float) -> str:
    return "; ".join(f"--{name.replace('_', '-')}: {_number(value) if isinstance(value, (int, float)) else value}" for name, value in values.items())


def _cell_html(
    document: RecipeDocument,
    item: CellBox,
    computed: ComputedLayout,
    *,
    grid_font_size: int,
) -> str:
    box = item.box
    padding = item.padding if item.padding is not None else document.layout.cell_padding
    classes = f"diagram-cell {item.kind}-cell align-{item.align} valign-{item.valign}"
    style = _style(
        cell_left=f"{_number(box.x - computed.grid_box.x)}px",
        cell_top=f"{_number(box.y - computed.grid_box.y)}px",
        cell_width=f"{_number(box.width)}px",
        cell_height=f"{_number(box.height)}px",
        cell_padding=f"{padding}px",
    )
    attributes = (
        f'class="{classes}" id="cell-{escape(item.id, quote=True)}" '
        f'data-cell-id="{escape(item.id, quote=True)}" style="{escape(style, quote=True)}"'
    )
    if not item.text:
        return f"      <div {attributes} aria-hidden=\"true\"></div>"

    fitted = fit_cell_text(document, item, shared_size=grid_font_size)
    text_style = _style(
        cell_font_size=f"{fitted.font_size}px",
        cell_line_height=f"{fitted.font_size}px",
        cell_line_gap=f"{_number(fitted.line_advance - fitted.font_size)}px",
        cell_weight=item.font_weight,
    )
    lines = "\n".join(
        f'          <span class="diagram-line">{escape(line) or "&nbsp;"}</span>'
        for line in fitted.lines
    )
    return (
        f"      <div {attributes}>\n"
        f'        <div class="cell-text" style="{escape(text_style, quote=True)}">\n'
        f"{lines}\n"
        "        </div>\n"
        "      </div>"
    )


def render_diagram_html(document: RecipeDocument, *, layout: ComputedLayout | None = None) -> str:
    """Render the process grid as HTML elements with deterministic CSS geometry."""

    computed = layout if layout is not None else compute_layout(document)
    all_boxes = computed.ingredient_boxes + computed.process_boxes
    grid_font_size = shared_font_size(document, all_boxes, role="grid")
    grid = computed.grid_box
    diagram_style = _style(
        diagram_width=f"{_number(grid.width)}px",
        diagram_height=f"{_number(grid.height)}px",
        border_color=document.theme.border_color,
        border_width=f"{_number(document.theme.border_width)}px",
        cell_background=document.theme.cell_background,
        diagram_text=document.theme.text_color,
        diagram_font=_css_font_family(document.theme.font_family),
    )
    cells = "\n".join(
        _cell_html(document, item, computed, grid_font_size=grid_font_size)
        for item in all_boxes
    )
    borders: list[str] = []
    for segment in computed.border_segments:
        if segment.orientation == "horizontal":
            segment_style = _style(
                border_left=f"{_number(segment.start - grid.x)}px",
                border_top=f"{_number(segment.fixed - grid.y)}px",
                border_length=f"{_number(segment.end - segment.start)}px",
            )
        else:
            segment_style = _style(
                border_left=f"{_number(segment.fixed - grid.x)}px",
                border_top=f"{_number(segment.start - grid.y)}px",
                border_length=f"{_number(segment.end - segment.start)}px",
            )
        borders.append(
            f'      <span class="diagram-border {segment.orientation}" '
            f'style="{escape(segment_style, quote=True)}" aria-hidden="true"></span>'
        )
    outer = ""
    if document.theme.outer_border_width is not None:
        outer_style = _style(outer_border_width=f"{_number(document.theme.outer_border_width)}px")
        outer = f'\n      <span class="diagram-outer-border" style="{escape(outer_style, quote=True)}" aria-hidden="true"></span>'
    label = escape(f"Process diagram for {document.card.title}", quote=True)
    return (
        '<figure class="recipe-figure">\n'
        f'  <figcaption class="visually-hidden">{escape(f"Process diagram for {document.card.title}")}</figcaption>\n'
        '  <div class="diagram-scroller" tabindex="0">\n'
        f'    <div class="diagram-scaler" style="{escape(diagram_style, quote=True)}">\n'
        f'      <div class="recipe-diagram" role="group" aria-label="{label}">\n'
        f"{cells}\n"
        f"{chr(10).join(borders)}{outer}\n"
        "      </div>\n"
        "    </div>\n"
        "  </div>\n"
        "</figure>"
    )


def _humanize_id(identifier: str) -> str:
    return identifier.replace("_", " ").replace("-", " ").strip().capitalize()


def _render_mobile_process(document: RecipeDocument) -> str:
    """Render readable, swipeable process stages for narrow screens."""

    row_index = {row.id: index for index, row in enumerate(document.rows)}
    panels: list[str] = []
    for stage in document.stages:
        cells = [
            cell
            for cell in document.cells
            if cell.stage_start == stage.id and cell.text
        ]
        cells.sort(key=lambda cell: (row_index[cell.rows.from_id], row_index[cell.rows.to_id], cell.id))
        if not cells:
            continue
        actions: list[str] = []
        for cell in cells:
            start = row_index[cell.rows.from_id]
            end = row_index[cell.rows.to_id]
            labels = [row.label for row in document.rows[start : end + 1]]
            if len(labels) <= 4:
                inputs = "".join(f"<span>{escape(label)}</span>" for label in labels)
            else:
                inputs = f"<span>{len(labels)} ingredient lanes</span>"
            name = "" if cell.id.startswith("step_") else f'<h3>{escape(_humanize_id(cell.id))}</h3>'
            actions.append(
                f"""          <article class="mobile-action">
            <div class="mobile-inputs" aria-label="Inputs">{inputs}</div>
            {name}
            <p class="mobile-instruction">{escape(cell.text)}</p>
          </article>"""
            )
        panels.append(
            f"""      <section class="mobile-stage" role="listitem">
        <header class="mobile-stage-heading">
          <h2 class="mobile-stage-number">Stage {len(panels) + 1}</h2>
          <span>{len(cells)} {"action" if len(cells) == 1 else "actions"}</span>
        </header>
        <div class="mobile-action-list">
{chr(10).join(actions)}
        </div>
      </section>"""
        )
    if not panels:
        return ""
    count = len(panels)
    return f"""      <section class="mobile-process" data-mobile-process aria-label="Recipe stages">
        <header class="mobile-process-bar">
          <p>Swipe through the recipe</p>
          <div class="mobile-stage-controls">
            <button type="button" data-stage-previous aria-label="Previous stage" disabled>←</button>
            <span data-stage-position aria-live="polite">Stage 1 of {count}</span>
            <button type="button" data-stage-next aria-label="Next stage">→</button>
          </div>
        </header>
        <div class="mobile-stage-track" data-stage-track role="list" tabindex="0">
{chr(10).join(panels)}
        </div>
      </section>"""


def render_recipe_page(
    document: RecipeDocument,
    *,
    site_title: str,
    stylesheet_href: str = "../../assets/site.css",
    script_href: str = "../../assets/site.js",
    favicon_href: str = "../../assets/favicon.png",
    home_href: str = "../../index.html",
    source_href: str = "recipe.yaml",
) -> str:
    """Render one complete, standalone recipe page for the generated site."""

    computed = compute_layout(document)
    diagram = render_diagram_html(document, layout=computed)
    mobile_process = _render_mobile_process(document)
    theme = document.theme
    page_style = _style(
        recipe_background=document.canvas.background or theme.background,
        recipe_text=theme.text_color,
        recipe_secondary=theme.secondary_text_color,
        recipe_accent=theme.border_color,
        recipe_title_size=f"{theme.title_size}px",
        recipe_subtitle_size=f"{theme.subtitle_size}px",
        recipe_footer_size=f"{theme.footer_size}px",
    )
    subtitle = f'\n        <p class="recipe-subtitle">{escape(document.card.subtitle)}</p>' if document.card.subtitle else ""
    source = f'\n        <p class="recipe-source">Source: {escape(document.card.source)}</p>' if document.card.source else ""
    notes = ""
    if document.footer_notes:
        items = "\n".join(f"        <li>{escape(note)}</li>" for note in document.footer_notes)
        notes = f"""
      <section class="recipe-notes" aria-labelledby="recipe-notes-title">
        <h2 id="recipe-notes-title">Notes</h2>
        <ul>
{items}
        </ul>
      </section>"""
    description = document.card.subtitle or f"A tabular process diagram for {document.card.title}."
    body_class = "recipe-body has-mobile-process" if mobile_process else "recipe-body"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="{escape(description, quote=True)}">
  <title>{escape(document.card.title)} · {escape(site_title)}</title>
  <link rel="icon" type="image/png" href="{escape(favicon_href, quote=True)}">
  <link rel="apple-touch-icon" href="{escape(favicon_href, quote=True)}">
  <link rel="stylesheet" href="{escape(stylesheet_href, quote=True)}">
</head>
<body class="{body_class}" style="{escape(page_style, quote=True)}">
  <header class="site-header">
    <a class="site-wordmark" href="{escape(home_href, quote=True)}">{escape(site_title)}</a>
  </header>
  <main class="page-shell">
    <article class="recipe-page">
      <div class="recipe-toolbar">
        <nav class="breadcrumbs" aria-label="Breadcrumb"><a href="{escape(home_href, quote=True)}">All recipes</a><span aria-hidden="true">/</span><span>{escape(document.card.title)}</span></nav>
        <div class="recipe-tools">
          <a class="text-link" href="{escape(source_href, quote=True)}" download>Download YAML</a>
        </div>
      </div>
      <header class="recipe-heading">
        <p class="eyebrow">Recipe Cards</p>
        <h1>{escape(document.card.title)}</h1>{subtitle}{source}
      </header>
      <section class="diagram-section" aria-label="Recipe process">
{diagram}
      </section>
{mobile_process}
{notes}
    </article>
  </main>
  <script src="{escape(script_href, quote=True)}"></script>
</body>
</html>
"""
