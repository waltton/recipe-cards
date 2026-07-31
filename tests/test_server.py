"""Live preview server integration tests."""

from __future__ import annotations

import json
from pathlib import Path
from threading import Thread
from time import monotonic, sleep
from urllib.request import urlopen

from recipe_card.server import RecipePreviewServer


def _recipe(title: str, *, final: str = "toasted") -> str:
    return f"""version: 1
card: {{title: {title}}}
ingredients: {{bread: 1 slice bread}}
actions: {{toasted: {{from: bread, do: toast}}}}
final: {final}
"""


def _read(url: str) -> str:
    with urlopen(url, timeout=2) as response:
        return response.read().decode("utf-8")


def _wait_for_generation(server: RecipePreviewServer, previous: int, *, timeout: float = 3) -> None:
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        if server.state.snapshot().generation > previous:
            return
        sleep(0.02)
    raise AssertionError("preview server did not rebuild after the source changed")


def test_preview_server_rebuilds_and_injects_live_reload(tmp_path: Path) -> None:
    source = tmp_path / "recipes"
    source.mkdir()
    recipe = source / "toast.yaml"
    recipe.write_text(_recipe("Toast"), encoding="utf-8")
    server = RecipePreviewServer(source, port=0, poll_interval=0.02)
    thread = Thread(target=server.run, daemon=True)
    initial_generation = server.state.snapshot().generation
    thread.start()
    try:
        page = _read(server.url)
        assert "Toast" in page
        assert "/__recipe_card_status" in page

        recipe.write_text(_recipe("Golden Toast"), encoding="utf-8")
        _wait_for_generation(server, initial_generation)
        assert server.state.snapshot().error is None
        assert "Golden Toast" in _read(server.url)

        status = json.loads(_read(f"{server.url}__recipe_card_status"))
        assert status["generation"] > initial_generation
        assert status["error"] is None
    finally:
        server.shutdown()
        thread.join(timeout=3)
    assert not thread.is_alive()


def test_preview_server_recovers_from_an_initial_yaml_error(tmp_path: Path) -> None:
    source = tmp_path / "recipes"
    source.mkdir()
    recipe = source / "toast.yaml"
    recipe.write_text(_recipe("Toast", final="missing"), encoding="utf-8")
    server = RecipePreviewServer(source, port=0, poll_interval=0.02)
    thread = Thread(target=server.run, daemon=True)
    failed_generation = server.state.snapshot().generation
    thread.start()
    try:
        assert server.state.snapshot().error is not None
        assert "could not be built" in _read(server.url)

        recipe.write_text(_recipe("Recovered Toast"), encoding="utf-8")
        _wait_for_generation(server, failed_generation)
        assert server.state.snapshot().error is None
        assert "Recovered Toast" in _read(server.url)
    finally:
        server.shutdown()
        thread.join(timeout=3)
    assert not thread.is_alive()
