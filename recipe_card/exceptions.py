"""Public exception types raised by the renderer."""


class RecipeError(Exception):
    """Base class for expected user-facing recipe errors."""


class RecipeValidationError(RecipeError):
    """Raised when a YAML document does not match the recipe schema."""


class LayoutError(RecipeError):
    """Raised when valid recipe data cannot form a valid layout."""


class RenderError(RecipeError):
    """Raised when a computed card cannot be rendered or written."""

