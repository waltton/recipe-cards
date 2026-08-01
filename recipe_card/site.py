"""Jekyll-style static site generation for YAML recipe collections."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from importlib.resources import files
from pathlib import Path
import re

import yaml

from .exceptions import RecipeValidationError, RenderError
from .loader import load_recipe
from .models import RecipeDocument
from .renderer_html import render_recipe_page

CONFIG_NAMES = {"_config.yaml", "_config.yml", "site.yaml", "site.yml"}
DEFAULT_SITE_TITLE = "Recipe Cards"
DEFAULT_SITE_DESCRIPTION = "Visual recipes, from ingredients to finished dish."


@dataclass(frozen=True)
class SiteConfig:
    """Small set of site-wide values kept separate from recipe YAML."""

    title: str = DEFAULT_SITE_TITLE
    description: str = DEFAULT_SITE_DESCRIPTION


@dataclass(frozen=True)
class SiteRecipe:
    """One compiled recipe and its stable URL slug."""

    source_path: Path
    slug: str
    document: RecipeDocument


@dataclass(frozen=True)
class BuildResult:
    """Paths and entries produced by a successful site build."""

    output_dir: Path
    index_path: Path
    recipes: tuple[SiteRecipe, ...]


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not slug:
        raise RecipeValidationError(f"cannot create a URL slug from recipe filename {value!r}")
    return slug


def discover_recipe_paths(source: str | Path, *, output_dir: str | Path | None = None) -> tuple[Path, ...]:
    """Find recipe YAML files in deterministic order, excluding site configuration."""

    source_path = Path(source)
    if source_path.is_file():
        if source_path.suffix.lower() not in {".yaml", ".yml"}:
            raise RecipeValidationError(f"recipe source '{source_path}' must be a .yaml or .yml file")
        return (source_path,)
    if not source_path.is_dir():
        raise RecipeValidationError(f"recipe source '{source_path}' is not a file or directory")

    excluded: Path | None = None
    if output_dir is not None:
        excluded = Path(output_dir).resolve()
    candidates: list[Path] = []
    for path in source_path.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".yaml", ".yml"}:
            continue
        if path.name in CONFIG_NAMES:
            continue
        if excluded is not None and (path.resolve() == excluded or excluded in path.resolve().parents):
            continue
        candidates.append(path)
    candidates.sort(key=lambda path: path.relative_to(source_path).as_posix().casefold())
    if not candidates:
        raise RecipeValidationError(f"no recipe YAML files found in '{source_path}'")
    return tuple(candidates)


def _load_site_config(source: Path, title_override: str | None) -> SiteConfig:
    if title_override is not None:
        if not title_override.strip():
            raise RecipeValidationError("--site-title must not be empty")
        title_override = title_override.strip()
    if not source.is_dir():
        return SiteConfig(title=title_override or DEFAULT_SITE_TITLE)
    config_path = next((source / name for name in sorted(CONFIG_NAMES) if (source / name).is_file()), None)
    if config_path is None:
        return SiteConfig(title=title_override or DEFAULT_SITE_TITLE)
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise RecipeValidationError(f"cannot read site config '{config_path}': {exc}") from exc
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise RecipeValidationError(f"site config '{config_path}' must be a mapping")
    unknown = sorted(set(raw) - {"title", "description"})
    if unknown:
        raise RecipeValidationError(
            f"site config '{config_path}' contains unknown field(s): " + ", ".join(repr(key) for key in unknown)
        )
    title = raw.get("title", DEFAULT_SITE_TITLE)
    description = raw.get("description", DEFAULT_SITE_DESCRIPTION)
    if not isinstance(title, str) or not title.strip():
        raise RecipeValidationError(f"site config '{config_path}' title must be a non-empty string")
    if not isinstance(description, str):
        raise RecipeValidationError(f"site config '{config_path}' description must be a string")
    return SiteConfig(title=title_override or title.strip(), description=description.strip())


def load_site_recipes(source: str | Path, *, output_dir: str | Path | None = None) -> tuple[SiteRecipe, ...]:
    """Load every source recipe and assign collision-free slugs."""

    source_path = Path(source)
    root = source_path if source_path.is_dir() else source_path.parent
    recipes: list[SiteRecipe] = []
    slugs: dict[str, Path] = {}
    for path in discover_recipe_paths(source_path, output_dir=output_dir):
        relative = path.relative_to(root).with_suffix("")
        slug = _slugify("-".join(relative.parts))
        if slug in slugs:
            raise RecipeValidationError(
                f"recipe filenames '{slugs[slug]}' and '{path}' both produce URL slug '{slug}'"
            )
        slugs[slug] = path
        recipes.append(SiteRecipe(source_path=path, slug=slug, document=load_recipe(path)))
    return tuple(recipes)


def render_index_page(config: SiteConfig, recipes: tuple[SiteRecipe, ...]) -> str:
    """Render the collection landing page."""

    cards: list[str] = []
    for recipe in recipes:
        document = recipe.document
        subtitle = document.card.subtitle or "Open the visual recipe"
        source = (
            f'\n          <p class="card-source">Source: {escape(document.card.source)}</p>'
            if document.card.source
            else ""
        )
        cards.append(f"""      <li class="recipe-card" style="--card-accent: {escape(document.theme.border_color, quote=True)}">
        <a href="recipes/{escape(recipe.slug, quote=True)}/">
          <p class="eyebrow">Recipe</p>
          <h3>{escape(document.card.title)}</h3>
          <p>{escape(subtitle)}</p>{source}
        </a>
      </li>""")
    count_label = "1 recipe" if len(recipes) == 1 else f"{len(recipes)} recipes"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="{escape(config.description, quote=True)}">
  <title>{escape(config.title)}</title>
  <link rel="icon" type="image/png" href="assets/favicon.png">
  <link rel="apple-touch-icon" href="assets/favicon.png">
  <link rel="stylesheet" href="assets/site.css">
</head>
<body>
  <header class="site-header"><a class="site-wordmark" href="index.html">{escape(config.title)}</a></header>
  <main class="page-shell">
    <section class="home-hero">
      <p class="eyebrow">From YAML to the table</p>
      <h1>{escape(config.title)}</h1>
      <p class="home-intro">{escape(config.description)}</p>
    </section>
    <section aria-labelledby="recipe-list-title">
      <div class="recipe-list-heading">
        <h2 id="recipe-list-title">Recipes</h2>
        <span class="recipe-count">{count_label}</span>
      </div>
      <ul class="recipe-list">
{chr(10).join(cards)}
      </ul>
    </section>
    <section class="site-credit" aria-labelledby="site-credit-title">
      <p class="eyebrow">Inspiration</p>
      <h2 id="site-credit-title">Inspired by Cooking for Engineers</h2>
      <p>Recipe Cards was inspired by Michael Chu&rsquo;s tabular presentation of cooking steps at <a href="https://www.cookingforengineers.com/" rel="external">Cooking for Engineers</a>. This independent project is not affiliated with or endorsed by Cooking for Engineers or CFE Enterprises, Inc., and does not reproduce its recipe content. See their <a href="https://www.cookingforengineers.com/article/190/User-Agreement" rel="external">User Agreement</a> for terms governing use of their site.</p>
    </section>
  </main>
</body>
</html>
"""


def _write_text(path: Path, content: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    except OSError as exc:
        raise RenderError(f"cannot write generated file '{path}': {exc}") from exc


def _write_bytes(path: Path, content: bytes) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    except OSError as exc:
        raise RenderError(f"cannot write generated file '{path}': {exc}") from exc


def build_site(
    source: str | Path,
    output_dir: str | Path = "_site",
    *,
    site_title: str | None = None,
) -> BuildResult:
    """Compile a recipe file or directory into a dependency-free static site."""

    source_path = Path(source)
    destination = Path(output_dir)
    if destination.exists() and not destination.is_dir():
        raise RenderError(f"site output '{destination}' exists and is not a directory")
    if source_path.is_dir() and destination.resolve() == source_path.resolve():
        raise RenderError("site output directory cannot be the recipe source directory")

    config = _load_site_config(source_path, site_title)
    recipes = load_site_recipes(source_path, output_dir=destination)
    try:
        stylesheet = files("recipe_card").joinpath("assets/site.css").read_text(encoding="utf-8")
        script = files("recipe_card").joinpath("assets/site.js").read_text(encoding="utf-8")
        favicon = files("recipe_card").joinpath("assets/favicon.png").read_bytes()
    except OSError as exc:
        raise RenderError(f"cannot load bundled site asset: {exc}") from exc
    rendered_recipes: list[tuple[SiteRecipe, str, str]] = []
    for recipe in recipes:
        try:
            yaml_source = recipe.source_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise RenderError(f"cannot copy recipe source '{recipe.source_path}': {exc}") from exc
        rendered_recipes.append(
            (recipe, render_recipe_page(recipe.document, site_title=config.title), yaml_source)
        )

    # Resolve and render every input before touching the destination. A bad
    # recipe therefore cannot leave behind a half-built site.
    _write_text(destination / "index.html", render_index_page(config, recipes))
    _write_text(destination / "assets" / "site.css", stylesheet)
    _write_text(destination / "assets" / "site.js", script)
    _write_bytes(destination / "assets" / "favicon.png", favicon)
    for recipe, page, yaml_source in rendered_recipes:
        recipe_dir = destination / "recipes" / recipe.slug
        _write_text(recipe_dir / "index.html", page)
        _write_text(recipe_dir / "recipe.yaml", yaml_source)

    return BuildResult(destination, destination / "index.html", recipes)
