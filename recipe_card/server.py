"""Local development server with automatic recipe rebuilds and live reload."""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from html import escape
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Lock, Thread
from urllib.parse import urlsplit

from .exceptions import RecipeError, RenderError
from .site import build_site

STATUS_PATH = "/__recipe_card_status"
LIVE_RELOAD_SCRIPT = """<script>
(() => {
  let generation = null;
  let banner = null;

  function showError(message) {
    if (!banner) {
      banner = document.createElement("pre");
      banner.setAttribute("role", "alert");
      Object.assign(banner.style, {
        position: "fixed", inset: "auto 1rem 1rem 1rem", zIndex: "9999",
        maxHeight: "45vh", overflow: "auto", margin: "0", padding: "1rem",
        color: "#fff", background: "#8b1e1e", border: "2px solid #fff",
        boxShadow: "0 10px 35px rgba(0,0,0,.3)", whiteSpace: "pre-wrap"
      });
      document.body.appendChild(banner);
    }
    banner.textContent = "Recipe build failed\n\n" + message;
  }

  async function check() {
    try {
      const response = await fetch("/__recipe_card_status", {cache: "no-store"});
      const status = await response.json();
      if (generation === null) generation = status.generation;
      if (status.error) {
        showError(status.error);
      } else {
        if (banner) banner.remove();
        banner = null;
        if (status.generation !== generation) location.reload();
      }
    } catch (_) {
      // A save may briefly overlap a server response. The next poll retries.
    }
  }

  check();
  setInterval(check, 500);
})();
</script>"""


@dataclass(frozen=True)
class PreviewStatus:
    """One immutable snapshot exposed to the live-reload client."""

    generation: int
    error: str | None


class PreviewState:
    """Thread-safe build state shared by the watcher and request handlers."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._generation = 0
        self._error: str | None = None

    def update(self, error: str | None) -> PreviewStatus:
        with self._lock:
            self._generation += 1
            self._error = error
            return PreviewStatus(self._generation, self._error)

    def snapshot(self) -> PreviewStatus:
        with self._lock:
            return PreviewStatus(self._generation, self._error)


class PreviewRequestHandler(SimpleHTTPRequestHandler):
    """Serve generated files and inject the development reload client."""

    def __init__(self, *args, preview_state: PreviewState, **kwargs) -> None:
        self.preview_state = preview_state
        super().__init__(*args, **kwargs)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self) -> None:  # noqa: N802 - inherited HTTP method name
        request_path = urlsplit(self.path).path
        if request_path == STATUS_PATH:
            self._send_status()
            return
        local_path = Path(self.translate_path(request_path))
        if local_path.is_dir():
            if not request_path.endswith("/"):
                super().do_GET()
                return
            local_path /= "index.html"
        if local_path.is_file() and local_path.suffix.lower() == ".html":
            self._send_html(local_path)
            return
        super().do_GET()

    def _send_status(self) -> None:
        status = self.preview_state.snapshot()
        body = json.dumps({"generation": status.generation, "error": status.error}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, path: Path) -> None:
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            self.send_error(404, "Generated page is unavailable")
            return
        marker = "</body>"
        content = content.replace(marker, f"{LIVE_RELOAD_SCRIPT}\n{marker}", 1)
        body = content.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        if urlsplit(self.path).path != STATUS_PATH:
            super().log_message(format, *args)


def _source_snapshot(source: Path, output_dir: Path) -> tuple[tuple[str, int, int], ...]:
    """Return stable path, modification-time, and size tuples for watched files."""

    candidates: set[Path] = set()
    if source.is_file():
        candidates.add(source)
    elif source.is_dir():
        for pattern in ("*.yaml", "*.yml"):
            candidates.update(source.rglob(pattern))
    asset_dir = Path(__file__).with_name("assets")
    for pattern in ("*.css", "*.js"):
        candidates.update(asset_dir.glob(pattern))

    output = output_dir.resolve()
    snapshot: list[tuple[str, int, int]] = []
    for path in candidates:
        try:
            resolved = path.resolve()
            if resolved == output or output in resolved.parents:
                continue
            stat = resolved.stat()
        except OSError:
            continue
        snapshot.append((str(resolved), stat.st_mtime_ns, stat.st_size))
    snapshot.sort()
    return tuple(snapshot)


def _initial_error_page(message: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Recipe preview build error</title>
  <style>
    body {{ margin: 0; padding: 3rem; color: #fff; background: #5d1717; font: 18px/1.5 system-ui, sans-serif; }}
    main {{ margin: 0 auto; max-width: 900px; }}
    pre {{ overflow: auto; padding: 1.25rem; color: #2a1111; background: #fff7ed; white-space: pre-wrap; }}
  </style>
</head>
<body>
  <main>
    <h1>The recipe could not be built</h1>
    <p>Fix the source file and save it. This page will refresh automatically.</p>
    <pre>{escape(message)}</pre>
  </main>
</body>
</html>
"""


class RecipePreviewServer:
    """Build, watch, and serve a recipe collection until shut down."""

    def __init__(
        self,
        source: str | Path,
        *,
        host: str = "127.0.0.1",
        port: int = 8000,
        site_title: str | None = None,
        poll_interval: float = 0.35,
        output_dir: str | Path | None = None,
    ) -> None:
        if not 0 <= port <= 65535:
            raise RenderError("preview server port must be between 0 and 65535")
        if poll_interval <= 0:
            raise RenderError("preview poll interval must be positive")
        self.source = Path(source)
        self.site_title = site_title
        self.poll_interval = poll_interval
        self.state = PreviewState()
        self._stop = Event()
        self._temporary = TemporaryDirectory(prefix="recipe-card-preview-") if output_dir is None else None
        if self._temporary is not None:
            self.output_dir = Path(self._temporary.name)
        else:
            assert output_dir is not None
            self.output_dir = Path(output_dir)
        if self.source.is_dir() and self.output_dir.resolve() == self.source.resolve():
            self._cleanup_temporary()
            raise RenderError("preview output directory cannot be the recipe source directory")

        self._rebuild(initial=True)
        self._snapshot = _source_snapshot(self.source, self.output_dir)
        handler = partial(
            PreviewRequestHandler,
            directory=str(self.output_dir),
            preview_state=self.state,
        )
        try:
            self.httpd = ThreadingHTTPServer((host, port), handler)
        except OSError as exc:
            self._cleanup_temporary()
            raise RenderError(f"cannot start preview server on {host}:{port}: {exc}") from exc
        self.httpd.daemon_threads = True
        self._watcher = Thread(target=self._watch, name="recipe-card-watcher", daemon=True)

    @property
    def url(self) -> str:
        """Return a browser-friendly URL for the bound address."""

        host, port = self.httpd.server_address[:2]
        visible_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
        return f"http://{visible_host}:{port}/"

    def _cleanup_temporary(self) -> None:
        if self._temporary is not None:
            self._temporary.cleanup()
            self._temporary = None

    def _rebuild(self, *, initial: bool = False) -> None:
        try:
            result = build_site(self.source, self.output_dir, site_title=self.site_title)
        except RecipeError as exc:
            message = str(exc)
            status = self.state.update(message)
            if initial and not (self.output_dir / "index.html").is_file():
                try:
                    self.output_dir.mkdir(parents=True, exist_ok=True)
                    (self.output_dir / "index.html").write_text(_initial_error_page(message), encoding="utf-8")
                except OSError as write_error:
                    raise RenderError(f"cannot write preview error page: {write_error}") from write_error
            print(f"Build {status.generation} failed: {message}", flush=True)
            return
        status = self.state.update(None)
        print(f"Build {status.generation}: {len(result.recipes)} recipe(s)", flush=True)

    def _watch(self) -> None:
        while not self._stop.wait(self.poll_interval):
            current = _source_snapshot(self.source, self.output_dir)
            if current == self._snapshot:
                continue
            self._snapshot = current
            self._rebuild()

    def run(self) -> None:
        """Run until interrupted or :meth:`shutdown` is called from another thread."""

        self._watcher.start()
        try:
            self.httpd.serve_forever(poll_interval=0.2)
        finally:
            self._stop.set()
            self._watcher.join(timeout=2)
            self.httpd.server_close()
            self._cleanup_temporary()

    def shutdown(self) -> None:
        """Stop a server whose :meth:`run` method is active in another thread."""

        self._stop.set()
        self.httpd.shutdown()


def serve_site(
    source: str | Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8000,
    site_title: str | None = None,
) -> None:
    """Build and serve a live-reloading local preview until Ctrl+C."""

    preview = RecipePreviewServer(source, host=host, port=port, site_title=site_title)
    print(f"Serving recipe preview at {preview.url}", flush=True)
    print("Watching recipe YAML and site configuration. Press Ctrl+C to stop.", flush=True)
    try:
        preview.run()
    except KeyboardInterrupt:
        print("\nPreview server stopped.", flush=True)
