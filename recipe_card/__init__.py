"""Recipe Cards website generator and renderer."""

from .exceptions import LayoutError, RecipeValidationError, RenderError
from .layout import compute_layout
from .loader import load_recipe
from .renderer_html import render_diagram_html, render_recipe_page
from .renderer_svg import render_svg
from .server import RecipePreviewServer, serve_site
from .site import build_site

__all__ = [
    "LayoutError",
    "RecipeValidationError",
    "RenderError",
    "compute_layout",
    "load_recipe",
    "build_site",
    "render_diagram_html",
    "render_recipe_page",
    "render_svg",
    "RecipePreviewServer",
    "serve_site",
]

__version__ = "0.1.0"
