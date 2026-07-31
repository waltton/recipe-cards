"""Canonical, deterministic SVG renderer for recipe cards."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

from .exceptions import RenderError
from .layout import compute_layout
from .models import Box, CellBox, ComputedLayout, RecipeDocument
from .text import FittedText, natural_text
from .typography import fit_cell_text, shared_font_size

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)


def _tag(name: str) -> str:
    return f"{{{SVG_NS}}}{name}"


def _number(value: float | int) -> str:
    numeric = float(value)
    return str(int(numeric)) if numeric.is_integer() else f"{numeric:.3f}".rstrip("0").rstrip(".")


def _add_text_lines(
    parent: ET.Element,
    fitted: FittedText,
    box: Box,
    *,
    padding: float,
    align: str,
    valign: str,
    fill: str,
    font_family: str,
    font_weight: str,
    css_class: str,
) -> None:
    if not fitted.lines:
        return
    if align == "left":
        x, anchor = box.x + padding, "start"
    elif align == "right":
        x, anchor = box.right - padding, "end"
    else:
        x, anchor = box.x + box.width / 2, "middle"
    if valign == "top":
        top = box.y + padding
    elif valign == "bottom":
        top = box.bottom - padding - fitted.total_height
    else:
        top = box.y + (box.height - fitted.total_height) / 2
    for index, line in enumerate(fitted.lines):
        baseline = top + fitted.ascent + index * fitted.line_advance
        element = ET.SubElement(
            parent,
            _tag("text"),
            {
                "class": css_class,
                "x": _number(x),
                "y": _number(baseline),
                "fill": fill,
                "font-family": font_family,
                "font-size": str(fitted.font_size),
                "font-weight": font_weight,
                "text-anchor": anchor,
            },
        )
        element.text = line or "\u00a0"


def _render_header(root: ET.Element, document: RecipeDocument, computed: ComputedLayout) -> None:
    padding = document.canvas.padding
    width = computed.canvas_width - padding.left - padding.right
    box_y = float(padding.top)
    family = ", ".join(document.theme.font_family)
    spacing = document.layout.text_line_spacing
    title = natural_text(document.card.title, width, document.theme.title_size, spacing, bold=True)
    title_box = Box(float(padding.left), box_y, float(width), title.total_height)
    _add_text_lines(
        root,
        title,
        title_box,
        padding=0,
        align="left",
        valign="top",
        fill=document.theme.text_color,
        font_family=family,
        font_weight="bold",
        css_class="card-title",
    )
    y = box_y + title.total_height
    if document.card.subtitle:
        y += 10
        subtitle = natural_text(document.card.subtitle, width, document.theme.subtitle_size, spacing)
        _add_text_lines(
            root,
            subtitle,
            Box(float(padding.left), y, float(width), subtitle.total_height),
            padding=0,
            align="left",
            valign="top",
            fill=document.theme.secondary_text_color,
            font_family=family,
            font_weight="normal",
            css_class="card-subtitle",
        )
        y += subtitle.total_height
    if document.card.source:
        y += 6
        source = natural_text(f"Source: {document.card.source}", width, document.theme.footer_size, spacing)
        _add_text_lines(
            root,
            source,
            Box(float(padding.left), y, float(width), source.total_height),
            padding=0,
            align="left",
            valign="top",
            fill=document.theme.secondary_text_color,
            font_family=family,
            font_weight="normal",
            css_class="card-source",
        )


def _render_cell_text(
    root: ET.Element,
    document: RecipeDocument,
    item: CellBox,
    *,
    shared_font_size: int,
) -> None:
    theme = document.theme
    defaults = document.layout
    padding = float(item.padding if item.padding is not None else defaults.cell_padding)
    fitted = fit_cell_text(document, item, shared_size=shared_font_size)
    _add_text_lines(
        root,
        fitted,
        item.box,
        padding=padding,
        align=item.align,
        valign=item.valign,
        fill=theme.text_color,
        font_family=", ".join(theme.font_family),
        font_weight=item.font_weight,
        css_class=f"{item.kind}-text",
    )


def _render_footer(root: ET.Element, document: RecipeDocument, computed: ComputedLayout) -> None:
    if not document.footer_notes:
        return
    padding = document.canvas.padding
    width = computed.canvas_width - padding.left - padding.right
    y = computed.grid_box.bottom + 16
    family = ", ".join(document.theme.font_family)
    for note in document.footer_notes:
        fitted = natural_text(f"• {note}", width, document.theme.footer_size, document.layout.text_line_spacing)
        _add_text_lines(
            root,
            fitted,
            Box(float(padding.left), y, float(width), fitted.total_height),
            padding=0,
            align="left",
            valign="top",
            fill=document.theme.secondary_text_color,
            font_family=family,
            font_weight="normal",
            css_class="footer-note",
        )
        y += fitted.total_height + 5


def _render_debug(root: ET.Element, document: RecipeDocument, computed: ComputedLayout) -> None:
    group = ET.SubElement(root, _tag("g"), {"id": "debug-layout", "font-family": "monospace", "font-size": "12"})
    grid = computed.grid_box
    ET.SubElement(group, _tag("rect"), {
        "x": _number(grid.x), "y": _number(grid.y), "width": _number(grid.width), "height": _number(grid.height),
        "fill": "none", "stroke": "#2b6cb0", "stroke-width": "1", "stroke-dasharray": "5 4",
    })
    for stage in document.stages:
        left = computed.stage_lefts[stage.id]
        right = computed.stage_rights[stage.id]
        label = ET.SubElement(group, _tag("text"), {
            "x": _number((left + right) / 2), "y": _number(grid.y - 7), "text-anchor": "middle", "fill": "#2b6cb0",
        })
        label.text = stage.id
    for row in document.rows:
        label = ET.SubElement(group, _tag("text"), {
            "x": "3", "y": _number((computed.row_tops[row.id] + computed.row_bottoms[row.id]) / 2 + 4), "fill": "#8b1a1a",
        })
        label.text = row.id
    for item in computed.process_boxes:
        label = ET.SubElement(group, _tag("text"), {
            "x": _number(item.box.x + 4), "y": _number(item.box.y + 13), "fill": "#8b1a1a",
        })
        label.text = f"{item.id} ({_number(item.box.x)},{_number(item.box.y)} {_number(item.box.width)}×{_number(item.box.height)})"


def render_svg(document: RecipeDocument, *, layout: ComputedLayout | None = None, debug: bool = False) -> str:
    """Render a recipe document to a deterministic standalone SVG string."""

    computed = layout if layout is not None else compute_layout(document)
    root = ET.Element(
        _tag("svg"),
        {
            "width": str(computed.canvas_width),
            "height": str(computed.canvas_height),
            "viewBox": f"0 0 {computed.canvas_width} {computed.canvas_height}",
            "role": "img",
            "aria-labelledby": "svg-title",
        },
    )
    title = ET.SubElement(root, _tag("title"), {"id": "svg-title"})
    title.text = document.card.title
    ET.SubElement(
        root,
        _tag("rect"),
        {
            "id": "page-background",
            "x": "0",
            "y": "0",
            "width": str(computed.canvas_width),
            "height": str(computed.canvas_height),
            "fill": document.canvas.background or document.theme.background,
        },
    )
    _render_header(root, document, computed)

    all_boxes = computed.ingredient_boxes + computed.process_boxes
    grid_font_size = shared_font_size(document, all_boxes, role="grid")
    fills = ET.SubElement(root, _tag("g"), {"id": "cell-backgrounds"})
    for item in all_boxes:
        ET.SubElement(
            fills,
            _tag("rect"),
            {
                "id": f"cell-{item.id}",
                "x": _number(item.box.x),
                "y": _number(item.box.y),
                "width": _number(item.box.width),
                "height": _number(item.box.height),
                "fill": document.theme.cell_background,
            },
        )

    borders = ET.SubElement(
        root,
        _tag("g"),
        {
            "id": "cell-borders",
            "fill": "none",
            "stroke": document.theme.border_color,
            "stroke-width": _number(document.theme.border_width),
            "stroke-linecap": "butt",
        },
    )
    for segment in computed.border_segments:
        if segment.orientation == "horizontal":
            attrs = {"x1": _number(segment.start), "y1": _number(segment.fixed), "x2": _number(segment.end), "y2": _number(segment.fixed)}
        else:
            attrs = {"x1": _number(segment.fixed), "y1": _number(segment.start), "x2": _number(segment.fixed), "y2": _number(segment.end)}
        ET.SubElement(borders, _tag("line"), attrs)
    if document.theme.outer_border_width is not None:
        grid = computed.grid_box
        ET.SubElement(root, _tag("rect"), {
            "x": _number(grid.x), "y": _number(grid.y), "width": _number(grid.width), "height": _number(grid.height),
            "fill": "none", "stroke": document.theme.border_color,
            "stroke-width": _number(document.theme.outer_border_width),
        })

    text_group = ET.SubElement(root, _tag("g"), {"id": "cell-text"})
    for item in computed.ingredient_boxes:
        _render_cell_text(text_group, document, item, shared_font_size=grid_font_size)
    for item in computed.process_boxes:
        _render_cell_text(text_group, document, item, shared_font_size=grid_font_size)
    _render_footer(root, document, computed)
    if debug:
        _render_debug(root, document, computed)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode", short_empty_elements=True) + "\n"


def write_svg(document: RecipeDocument, output_path: str | Path, *, layout: ComputedLayout | None = None, debug: bool = False) -> Path:
    """Render and write a UTF-8 SVG file, creating parent directories."""

    destination = Path(output_path)
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(render_svg(document, layout=layout, debug=debug), encoding="utf-8")
    except OSError as exc:
        raise RenderError(f"cannot write SVG '{destination}': {exc}") from exc
    return destination
