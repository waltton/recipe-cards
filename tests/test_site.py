"""Static collection build tests."""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path

from recipe_card.cli import main
from recipe_card.site import build_site


ROOT = Path(__file__).resolve().parents[1]


class _Parser(HTMLParser):
    pass


def test_build_site_writes_index_pages_stylesheet_and_sources(tmp_path: Path) -> None:
    destination = tmp_path / "_site"
    result = build_site(ROOT / "examples", destination, site_title="Kitchen Notebook")

    assert len(result.recipes) == 2
    expected = {
        Path("index.html"),
        Path("assets/site.css"),
        Path("assets/site.js"),
        Path("recipes/chicken-spinach-pasta/index.html"),
        Path("recipes/chicken-spinach-pasta/recipe.yaml"),
        Path("recipes/hatch-chile-truffles/index.html"),
        Path("recipes/hatch-chile-truffles/recipe.yaml"),
    }
    assert {path.relative_to(destination) for path in destination.rglob("*") if path.is_file()} == expected

    for path in destination.rglob("*.html"):
        content = path.read_text(encoding="utf-8")
        _Parser().feed(content)
        assert "<svg" not in content

    index = (destination / "index.html").read_text(encoding="utf-8")
    assert "Kitchen Notebook" in index
    assert 'href="recipes/chicken-spinach-pasta/"' in index
    recipe_page = (destination / "recipes/chicken-spinach-pasta/index.html").read_text(encoding="utf-8")
    assert 'href="../../assets/site.css"' in recipe_page
    assert 'src="../../assets/site.js"' in recipe_page
    assert 'href="../../index.html"' in recipe_page
    assert 'href="recipe.yaml" download' in recipe_page
    assert '<body class="recipe-body has-mobile-process" style="--recipe-background:' in recipe_page


def test_build_site_reads_jekyll_style_config(tmp_path: Path) -> None:
    source = tmp_path / "recipes"
    source.mkdir()
    (source / "_config.yaml").write_text(
        "title: Weeknight Food\ndescription: Fast visual recipes.\n",
        encoding="utf-8",
    )
    (source / "one.yaml").write_text(
        """version: 1
card: {title: Toast}
ingredients: {bread: 1 slice bread}
actions: {toasted: {from: bread, do: toast}}
final: toasted
""",
        encoding="utf-8",
    )
    destination = tmp_path / "public"
    build_site(source, destination)
    index = (destination / "index.html").read_text(encoding="utf-8")
    assert "Weeknight Food" in index
    assert "Fast visual recipes." in index
    assert not (destination / "recipes/config").exists()


def test_cli_builds_a_site(tmp_path: Path, capsys) -> None:
    destination = tmp_path / "public"
    assert main(["build", str(ROOT / "examples"), "--output", str(destination)]) == 0
    assert (destination / "index.html").is_file()
    assert "Built 2 recipe(s)" in capsys.readouterr().out
