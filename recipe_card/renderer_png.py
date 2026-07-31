"""PNG output produced by converting the canonical SVG."""

from __future__ import annotations

import os
from pathlib import Path
import sys

from .exceptions import RenderError


def _prepare_cairo_library_path() -> None:
    """Expose common Homebrew Cairo locations to macOS dynamic loading."""

    if sys.platform != "darwin":
        return
    candidates = [path for path in (Path("/opt/homebrew/lib"), Path("/usr/local/lib")) if path.is_dir()]
    if not candidates:
        return
    variable = "DYLD_FALLBACK_LIBRARY_PATH"
    existing = [part for part in os.environ.get(variable, "").split(os.pathsep) if part]
    additions = [str(path) for path in candidates if str(path) not in existing]
    if additions:
        os.environ[variable] = os.pathsep.join(additions + existing)


def write_png(svg: str, output_path: str | Path, *, width: int, height: int, scale: float = 1.0) -> Path:
    """Convert SVG text to an opaque PNG at an explicit scale."""

    if scale <= 0:
        raise RenderError("PNG scale must be positive")
    _prepare_cairo_library_path()
    try:
        import cairosvg
    except (ImportError, OSError) as exc:
        raise RenderError(
            "PNG output requires CairoSVG and its native Cairo library; "
            "install the project dependencies and Cairo runtime"
        ) from exc
    destination = Path(output_path)
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        cairosvg.svg2png(
            bytestring=svg.encode("utf-8"),
            write_to=str(destination),
            output_width=round(width * scale),
            output_height=round(height * scale),
        )
    except (OSError, ValueError) as exc:
        raise RenderError(f"cannot write PNG '{destination}': {exc}") from exc
    return destination
