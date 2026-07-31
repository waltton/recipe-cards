"""Shared test helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from recipe_card.loader import load_recipe


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def hatch_recipe():
    """Return the smaller irregular-merge example document."""

    return load_recipe(ROOT / "examples" / "hatch_chile_truffles.yaml")


@pytest.fixture
def chicken_recipe():
    """Return the full pasta example document."""

    return load_recipe(ROOT / "examples" / "chicken_spinach_pasta.yaml")

