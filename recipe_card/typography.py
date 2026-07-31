"""Typography decisions shared by visual renderers."""

from __future__ import annotations

from .exceptions import LayoutError
from .models import CellBox, RecipeDocument
from .text import FittedText, fit_text


def is_bold(font_weight: str) -> bool:
    """Return whether a supported CSS font weight should use bold metrics."""

    return font_weight == "bold" or (font_weight.isdigit() and int(font_weight) >= 600)


def shared_font_size(document: RecipeDocument, items: tuple[CellBox, ...], *, role: str) -> int:
    """Choose the largest font size that fits every non-overridden cell."""

    theme = document.theme
    defaults = document.layout
    candidates = tuple(item for item in items if item.text and item.font_size is None)
    if not candidates:
        return theme.cell_text_size
    minimum = max(
        item.min_font_size if item.min_font_size is not None else defaults.min_font_size
        for item in candidates
    )
    for size in range(theme.cell_text_size, minimum - 1, -1):
        for item in candidates:
            padding = float(item.padding if item.padding is not None else defaults.cell_padding)
            try:
                fit_text(
                    item.text,
                    item.box.width - 2 * padding,
                    item.box.height - 2 * padding,
                    size,
                    size,
                    defaults.text_line_spacing,
                    bold=is_bold(item.font_weight),
                    context=f"{item.kind} cell '{item.id}' text",
                )
            except LayoutError:
                break
        else:
            return size
    raise LayoutError(f"{role} text cannot fit consistently at minimum font size {minimum}")


def fit_cell_text(document: RecipeDocument, item: CellBox, *, shared_size: int) -> FittedText:
    """Wrap one cell using the shared size or its explicit override."""

    defaults = document.layout
    padding = float(item.padding if item.padding is not None else defaults.cell_padding)
    has_override = item.font_size is not None
    font_size = item.font_size if has_override else shared_size
    min_size = item.min_font_size if has_override and item.min_font_size is not None else font_size
    return fit_text(
        item.text,
        item.box.width - 2 * padding,
        item.box.height - 2 * padding,
        font_size,
        min_size,
        defaults.text_line_spacing,
        bold=is_bold(item.font_weight),
        context=f"{item.kind} cell '{item.id}' text",
    )
