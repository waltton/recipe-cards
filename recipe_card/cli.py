"""Command-line interface for static site builds and optional image exports."""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import sys

from .exceptions import RecipeError, RenderError
from .layout import compute_layout
from .loader import load_recipe
from .renderer_png import write_png
from .renderer_svg import render_svg
from .server import serve_site
from .site import build_site, discover_recipe_paths
from .validation import validate_output_base, validate_recipe


def _legacy_parser() -> argparse.ArgumentParser:
    """Create the original one-recipe parser for backwards compatibility."""

    parser = argparse.ArgumentParser(description="Render a tabular recipe card from YAML.")
    parser.add_argument("recipe", type=Path, help="input YAML recipe")
    parser.add_argument("--output", type=Path, help="output path without extension")
    parser.add_argument("--format", choices=("svg", "png", "both"), default="both", help="output format (default: both)")
    parser.add_argument("--width", type=int, help="override canvas width")
    parser.add_argument("--scale", type=float, default=1.0, help="PNG scale factor (default: 1.0)")
    parser.add_argument("--debug-layout", action="store_true", help="add IDs, coordinates, and layout guides")
    parser.add_argument("--validate-only", action="store_true", help="validate YAML without rendering")
    return parser


def build_parser() -> argparse.ArgumentParser:
    """Create the command-oriented public CLI parser."""

    parser = argparse.ArgumentParser(description="Build a static website of tabular recipes from YAML.")
    commands = parser.add_subparsers(dest="command", required=True)

    build = commands.add_parser("build", help="compile recipe YAML into a static website")
    build.add_argument("source", type=Path, help="recipe YAML file or directory")
    build.add_argument("--output", "-d", type=Path, default=Path("_site"), help="destination directory (default: _site)")
    build.add_argument("--site-title", help="override the collection title")

    serve = commands.add_parser("serve", help="preview recipes locally and rebuild on save")
    serve.add_argument("source", type=Path, help="recipe YAML file or directory")
    serve.add_argument("--host", default="127.0.0.1", help="interface to bind (default: 127.0.0.1)")
    serve.add_argument("--port", type=int, default=8000, help="port to bind (default: 8000)")
    serve.add_argument("--site-title", help="override the collection title")

    validate = commands.add_parser("validate", help="validate one recipe or a directory")
    validate.add_argument("source", type=Path, help="recipe YAML file or directory")

    render = commands.add_parser("render", help="optionally export one recipe as SVG or PNG")
    render.add_argument("recipe", type=Path, help="input YAML recipe")
    render.add_argument("--output", type=Path, required=True, help="output path without extension")
    render.add_argument("--format", choices=("svg", "png", "both"), default="both", help="output format (default: both)")
    render.add_argument("--width", type=int, help="override canvas width")
    render.add_argument("--scale", type=float, default=1.0, help="PNG scale factor (default: 1.0)")
    render.add_argument("--debug-layout", action="store_true", help="add IDs, coordinates, and layout guides")
    render.set_defaults(validate_only=False)
    return parser


def run(args: argparse.Namespace) -> int:
    """Execute parsed CLI arguments and return a process exit code."""

    document = load_recipe(args.recipe)
    if args.width is not None:
        if args.width <= 0:
            raise RenderError("--width must be positive")
        document = replace(document, canvas=replace(document.canvas, width=args.width))
        validate_recipe(document)
    if args.scale <= 0:
        raise RenderError("--scale must be positive")
    if args.validate_only:
        print(f"Valid recipe: {args.recipe}")
        return 0
    if args.output is None:
        raise RenderError("--output is required unless --validate-only is used")
    output_base = validate_output_base(args.output)
    computed = compute_layout(document)
    svg = render_svg(document, layout=computed, debug=args.debug_layout)
    created: list[Path] = []
    if args.format in {"svg", "both"}:
        svg_path = output_base.with_suffix(".svg")
        try:
            svg_path.parent.mkdir(parents=True, exist_ok=True)
            svg_path.write_text(svg, encoding="utf-8")
        except OSError as exc:
            raise RenderError(f"cannot write SVG '{svg_path}': {exc}") from exc
        created.append(svg_path)
    if args.format in {"png", "both"}:
        created.append(
            write_png(
                svg,
                output_base.with_suffix(".png"),
                width=computed.canvas_width,
                height=computed.canvas_height,
                scale=args.scale,
            )
        )
    for path in created:
        print(path)
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point with concise, non-zero failures for user errors."""

    arguments = list(sys.argv[1:] if argv is None else argv)
    modern = not arguments or arguments[0] in {"build", "serve", "validate", "render", "-h", "--help"}
    parser = build_parser() if modern else _legacy_parser()
    args = parser.parse_args(arguments)
    try:
        if modern and args.command == "build":
            result = build_site(args.source, args.output, site_title=args.site_title)
            print(f"Built {len(result.recipes)} recipe(s) in {result.output_dir}")
            print(result.index_path)
            return 0
        if modern and args.command == "validate":
            paths = discover_recipe_paths(args.source)
            for path in paths:
                load_recipe(path)
            print(f"Valid recipe source: {args.source} ({len(paths)} recipe(s))")
            return 0
        if modern and args.command == "serve":
            serve_site(args.source, host=args.host, port=args.port, site_title=args.site_title)
            return 0
        return run(args)
    except RecipeError as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
