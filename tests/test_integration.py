"""End-to-end file output tests for both examples."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from recipe_card.cli import main
from recipe_card.layout import compute_layout
from recipe_card.loader import load_recipe


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("name", ["hatch_chile_truffles", "chicken_spinach_pasta"])
def test_cli_renders_svg(name: str, tmp_path: Path) -> None:
    source = ROOT / "examples" / f"{name}.yaml"
    output = tmp_path / name
    assert main([str(source), "--output", str(output), "--format", "svg"]) == 0
    assert output.with_suffix(".svg").is_file()


@pytest.mark.parametrize("name", ["hatch_chile_truffles", "chicken_spinach_pasta"])
def test_cli_renders_png_at_scaled_svg_dimensions(name: str, tmp_path: Path) -> None:
    source = ROOT / "examples" / f"{name}.yaml"
    output = tmp_path / name
    scale = 1.25
    assert main([str(source), "--output", str(output), "--format", "both", "--scale", str(scale)]) == 0
    document = load_recipe(source)
    layout = compute_layout(document)
    with Image.open(output.with_suffix(".png")) as image:
        assert image.size == (round(layout.canvas_width * scale), round(layout.canvas_height * scale))
    assert output.with_suffix(".svg").is_file()


def test_validate_only_needs_no_output() -> None:
    source = ROOT / "examples" / "hatch_chile_truffles.yaml"
    assert main([str(source), "--validate-only"]) == 0
