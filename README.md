# Recipe Cards

Turn a directory of YAML recipes into a complete static website. Like Jekyll, the source is plain text and the output is a folder of HTML and CSS that can be served anywhere. Each recipe gets a responsive page with a Cooking for Engineers-style process diagram: ingredients begin as separate rows, actions extend to the right, and branches merge into the finished dish.

The diagrams are native HTML and CSS—not embedded SVGs—so text remains selectable, links work normally, and pages print directly from the browser. Production needs no server, database, or template runtime. A small dependency-free browser script fits each recipe into the available viewport height.

## Quick start

Python 3.11 or newer is required:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m recipe_card build examples
```

Open `_site/index.html` or serve the directory locally:

```bash
python -m http.server 8000 --directory _site
```

Then visit `http://localhost:8000`.

## Live preview while editing

Run the development server against one recipe or a directory:

```bash
recipe-card serve examples
```

Open `http://127.0.0.1:8000`. The server watches recipe YAML, `_config.yaml`, and the bundled site stylesheet. Saving a change rebuilds the site and refreshes every open page automatically. If a partially edited recipe is invalid, the last successful page stays available with an error banner; fixing and saving the YAML clears it and refreshes the page.

Choose another port when needed:

```bash
recipe-card serve examples --port 8080
```

The default host is local-only. Pass `--host 0.0.0.0` only when the preview should be reachable by other devices on the same network. Press `Ctrl+C` to stop the server. Preview files use a temporary directory and are removed when it stops; production builds still use `recipe-card build`.

The build output is ordinary static files:

```text
_site/
├── index.html
├── assets/
│   ├── site.css
│   └── site.js
└── recipes/
    ├── chicken-spinach-pasta/
    │   ├── index.html
    │   └── recipe.yaml
```

Recipe filenames become stable URL slugs, recipes are listed alphabetically, and the original YAML is copied beside each generated page for download.

Individual recipe pages are designed as one-screen workspaces: their outer page does not scroll vertically, and the recipe theme fills the complete viewport. On larger screens, the heading and controls stay compact, notes open as an overlay, and the full diagram scales proportionally up or down to use the available width and height. Diagrams that remain wider than the viewport retain horizontal scrolling.

Phones use a stage-by-stage view instead of shrinking the complete table into unreadable text. Swipe horizontally—or use the large previous/next controls—to move through process stages. Parallel actions stay grouped, ingredient inputs remain visible on each action, panels snap into place, and the current stage is announced for assistive technology. Rotating the phone switches layouts automatically when more space is available. The recipe index remains a normal vertically scrolling list.

## Deploy with GitHub Pages

Build the static site locally into `docs` and commit the generated files:

```bash
recipe-card validate examples
recipe-card build examples --output docs
git add docs
git commit -m "Update published recipe site"
git push
```

To enable the first deployment:

1. Push the repository to GitHub.
2. Open **Settings → Pages** in the repository.
3. Under **Build and deployment**, choose **Deploy from a branch** as the source.
4. Select the `main` branch and the `/docs` folder, then save.

GitHub Pages publishes the committed files without running the Python generator. Rebuild and commit `docs` whenever a recipe or site asset changes. The generated links are relative, so the same output works for both `username.github.io` and project sites such as `username.github.io/repository/`.

## Site configuration

Place `_config.yaml` (or `site.yaml`) beside the recipes:

```yaml
title: My Recipe Book
description: The dishes I make most often.
```

Then build the whole directory:

```bash
recipe-card build recipes --output public
```

`--output` defaults to `_site`. `--site-title` can override the configured title for one build. Recipe discovery is recursive, so the source directory may contain subdirectories. Configuration files are not treated as recipes.

To validate everything without writing a site:

```bash
recipe-card validate recipes
```

## Writing recipes

The recommended YAML format declares ingredients once, names the result of each action, and selects the final result. `from` accepts one input ID or an inline list:

```yaml
version: 1

card:
  title: Tomato Pasta
  subtitle: serves 4

ingredients:
  pasta: 12 oz pasta
  tomatoes: 2 cups tomatoes
  stock: 1 cup stock
  garnish: chopped parsley

actions:
  cooked_pasta:
    from: pasta
    do: cook until al dente

  sauce:
    from: [tomatoes, stock]
    do: simmer until thick

  combined:
    from: [cooked_pasta, sauce]
    do: stir together

  serve:
    from: [combined, garnish]
    do: top and serve

final: serve
```

The compiler follows dependencies backward from `final`. Each action is placed one column after its deepest input and spans all ingredients contributing to that result. Input order determines branch and ingredient order. Empty waiting cells and action widths are generated automatically.

The tabular layout cannot visually split one result into several outgoing branches, so each ingredient or intermediate result may have only one consumer. Recipes requiring fan-out, intentional overlays, or exact manual rectangles can use the compact explicit-geometry format documented in [docs/YAML_SCHEMA.md](docs/YAML_SCHEMA.md). The earlier nested `flow` format remains supported.

## Automatic layout and typography

The normal authoring format needs no IDs beyond meaningful ingredient/action keys, no labels repeated beside IDs, no stage list, and no row heights.

- Ingredient column width is measured from the ingredient text and clamped to configurable minimum and maximum widths.
- Row heights grow to fit ingredients and instructions.
- Action columns are measured from their text.
- Canvas dimensions are inferred from the complete layout.
- Ingredients and instructions use one shared grid font size, starting at `theme.cell_text_size`.
- On narrow screens, the full-size diagram scrolls horizontally rather than shrinking the text.

Optional `card`, `theme`, `layout`, and `canvas` settings can change metadata and presentation. The full field reference and defaults are in [docs/YAML_SCHEMA.md](docs/YAML_SCHEMA.md).

## Optional SVG and PNG exports

The website is now the primary output. Standalone images remain available for compatibility or sharing:

```bash
python -m pip install -e '.[export]'
recipe-card render recipe.yaml --output build/recipe --format svg
recipe-card render recipe.yaml --output build/recipe --format png --scale 2
```

SVG export has no extra native requirement. PNG conversion uses CairoSVG and requires the native Cairo runtime; on macOS it can be installed with `brew install cairo`.

The original command form still works:

```bash
recipe-card recipe.yaml --output build/recipe --format both
recipe-card recipe.yaml --validate-only
```

## Development

Install test dependencies and run the suite:

```bash
python -m pip install -e '.[test]'
pytest
```

Build the checked examples for a manual inspection:

```bash
recipe-card build examples --output build/site
```

The loader, dependency compiler, automatic layout, typography, HTML renderer, site builder, SVG renderer, and PNG adapter are separate modules. Tests cover YAML modes and errors, dependency references, geometry, shared type sizing, deduplicated borders, HTML/XML escaping, deterministic output, full site generation, CLI behavior, and optional image exports.
