"""Deterministic text measurement, wrapping, and fitting helpers."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from PIL import ImageFont

from .exceptions import LayoutError


@dataclass(frozen=True)
class FittedText:
    """Wrapped lines and metrics for one text block."""

    lines: tuple[str, ...]
    font_size: int
    ascent: float
    descent: float
    line_advance: float
    total_height: float


@lru_cache(maxsize=256)
def _font(size: int, bold: bool) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    filename = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    try:
        return ImageFont.truetype(filename, size=size)
    except OSError:
        return ImageFont.load_default(size=size)


def _text_width(text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont) -> float:
    if not text:
        return 0.0
    return float(font.getlength(text))


def measure_text_width(text: str, font_size: int, *, bold: bool = False) -> float:
    """Measure the widest explicit line without applying automatic wrapping."""

    font = _font(font_size, bold)
    return max((_text_width(line, font) for line in text.split("\n")), default=0.0)


def _split_long_word(word: str, max_width: float, font: ImageFont.FreeTypeFont | ImageFont.ImageFont) -> list[str]:
    parts: list[str] = []
    current = ""
    for character in word:
        candidate = current + character
        if current and _text_width(candidate, font) > max_width:
            parts.append(current)
            current = character
        else:
            current = candidate
    if current:
        parts.append(current)
    return parts or [word]


def wrap_text(text: str, max_width: float, font_size: int, *, bold: bool = False) -> tuple[str, ...]:
    """Wrap text to a measured width while preserving explicit newlines."""

    if not text:
        return ()
    if max_width <= 0:
        return (text,)
    font = _font(font_size, bold)
    result: list[str] = []
    for explicit_line in text.split("\n"):
        if explicit_line == "":
            result.append("")
            continue
        words = explicit_line.split()
        current = ""
        for word in words:
            pieces = _split_long_word(word, max_width, font) if _text_width(word, font) > max_width else [word]
            for piece in pieces:
                candidate = piece if not current else f"{current} {piece}"
                if current and _text_width(candidate, font) > max_width:
                    result.append(current)
                    current = piece
                else:
                    current = candidate
        if current:
            result.append(current)
    return tuple(result)


def text_metrics(lines: tuple[str, ...], font_size: int, line_spacing: float, *, bold: bool = False) -> FittedText:
    """Return vertical metrics for already wrapped lines."""

    # SVG/CSS line boxes are based on the requested font size rather than on
    # Pillow's full font metrics, which include invisible ascender/descender
    # reserve. Widths still use Pillow's glyph measurements in ``wrap_text``.
    line_height = float(font_size)
    ascent = line_height * 0.8
    descent = line_height - ascent
    advance = line_height * line_spacing
    total = 0.0 if not lines else line_height + advance * (len(lines) - 1)
    return FittedText(lines, font_size, float(ascent), float(descent), advance, total)


def natural_text(text: str, max_width: float, font_size: int, line_spacing: float, *, bold: bool = False) -> FittedText:
    """Wrap text at a fixed size and return its natural height."""

    lines = wrap_text(text, max_width, font_size, bold=bold)
    return text_metrics(lines, font_size, line_spacing, bold=bold)


def fit_text(
    text: str,
    max_width: float,
    max_height: float,
    font_size: int,
    min_font_size: int,
    line_spacing: float,
    *,
    bold: bool = False,
    context: str = "text",
) -> FittedText:
    """Wrap and shrink text until it fits the requested rectangle."""

    if not text:
        return text_metrics((), font_size, line_spacing, bold=bold)
    if max_width <= 0 or max_height <= 0:
        raise LayoutError(f"{context} has no space available after padding")
    for size in range(font_size, min_font_size - 1, -1):
        lines = wrap_text(text, max_width, size, bold=bold)
        fitted = text_metrics(lines, size, line_spacing, bold=bold)
        font = _font(size, bold)
        widest = max((_text_width(line, font) for line in lines), default=0.0)
        if widest <= max_width + 0.5 and fitted.total_height <= max_height + 0.5:
            return fitted
    raise LayoutError(
        f"{context} does not fit at minimum font size {min_font_size} "
        f"inside {max_width:g}x{max_height:g} user units"
    )
