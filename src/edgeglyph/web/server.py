"""Loopback-only HTTP server for the EdgeGlyph workbench."""

from __future__ import annotations

import base64
import json
import mimetypes
import tempfile
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from urllib.parse import urlparse

from ..modes import block, glyph
from ..outputs import palette_hex, result_metrics, result_text, save_result
from ..schema import coerce_options, mode_schema

MAX_REQUEST_BYTES = 24 * 1024 * 1024
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def available_fonts() -> list[dict[str, str]]:
    roots = (
        Path.home() / "Library/Fonts",
        Path("/Library/Fonts"),
        Path("/System/Library/Fonts"),
        Path("/System/Library/Fonts/Supplemental"),
    )
    preferred = (
        "ComicMono.ttf",
        "MapleMono-NF-Regular.ttf",
        "LXGWWenKaiMono-Regular.ttf",
        "SFNSMono.ttf",
        "Menlo.ttc",
        "PTMono.ttc",
    )
    discovered = []
    seen = set()
    for name in preferred:
        for root in roots:
            path = root / name
            if path.exists() and path not in seen:
                discovered.append({"label": path.stem, "path": str(path)})
                seen.add(path)
    return discovered


def application_schema() -> dict:
    fonts = available_fonts()
    default_font = fonts[0]["path"] if fonts else ""
    fallback = next(
        (item["path"] for item in fonts if "MapleMono-NF" in item["path"]),
        default_font,
    )
    return {
        "modes": mode_schema(),
        "fonts": fonts,
        "defaults": {"font": default_font, "fallback_font": fallback},
    }


def _decode_source(value: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise ValueError("source image is required")
    encoded = value.split(",", 1)[1] if value.startswith("data:") else value
    try:
        content = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as error:
        raise ValueError("source image is not valid base64 data") from error
    if not content:
        raise ValueError("source image is empty")
    if len(content) > MAX_REQUEST_BYTES:
        raise ValueError("source image is too large")
    return content


def _font_path(value: str | None, label: str, required: bool) -> Path | None:
    if not value:
        if required:
            raise ValueError(f"{label} is required for glyph mode")
        return None
    path = Path(value).expanduser()
    if not path.is_file():
        raise ValueError(f"{label} does not exist: {path}")
    return path


def render_payload(payload: dict) -> dict:
    """Render a JSON workbench request; kept separate for tests and integrations."""

    if not isinstance(payload, dict):
        raise ValueError("request body must be a JSON object")
    mode = payload.get("mode", "block")
    options = coerce_options(mode, payload.get("options"))
    content = _decode_source(payload.get("source"))
    font = fallback_font = None
    started = time.perf_counter()

    with tempfile.TemporaryDirectory(prefix="edgeglyph-web-") as directory:
        workdir = Path(directory)
        source = workdir / "source-image"
        source.write_bytes(content)

        if mode == "block":
            result = block.render(source, **options)
        else:
            font = _font_path(payload.get("font"), "font", required=True)
            fallback_font = _font_path(
                payload.get("fallback_font"), "fallback font", required=False
            )
            result = glyph.render(source, font, fallback_font, **options)

        preview = workdir / "preview.png"
        lua = workdir / "art.lua"
        save_result(
            result,
            lua_path=lua,
            preview_path=preview,
            mode=mode,
            font=font,
            fallback_font=fallback_font,
        )
        metrics = result_metrics(mode, result)
        metrics["render_seconds"] = round(time.perf_counter() - started, 3)
        return {
            "mode": mode,
            "preview": "data:image/png;base64,"
            + base64.b64encode(preview.read_bytes()).decode("ascii"),
            "text": result_text(result),
            "lua": lua.read_text(encoding="utf-8"),
            "palette": palette_hex(result.palette),
            "metrics": metrics,
        }


class WorkbenchHandler(BaseHTTPRequestHandler):
    server_version = "EdgeGlyph/0.4"

    def _send(self, status: int, content_type: str, content: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; "
            "style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'",
        )
        self.end_headers()
        self.wfile.write(content)

    def _json(self, status: int, value: dict) -> None:
        self._send(
            status,
            "application/json; charset=utf-8",
            json.dumps(value, separators=(",", ":")).encode("utf-8"),
        )

    def do_GET(self) -> None:  # noqa: N802
        route = urlparse(self.path).path
        if route == "/favicon.ico":
            self._send(204, "image/x-icon", b"")
            return
        if route == "/api/schema":
            self._json(200, application_schema())
            return
        filenames = {
            "/": "index.html",
            "/index.html": "index.html",
            "/app.css": "app.css",
            "/app.js": "app.js",
        }
        filename = filenames.get(route)
        if filename is None:
            self._json(404, {"error": "not found"})
            return
        content = resources.files("edgeglyph.web").joinpath("static", filename).read_bytes()
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type == "application/javascript":
            content_type += "; charset=utf-8"
        self._send(200, content_type, content)

    def do_POST(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/api/render":
            self._json(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_REQUEST_BYTES:
                raise ValueError("request body is empty or too large")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            self._json(200, render_payload(payload))
        except (ValueError, json.JSONDecodeError) as error:
            self._json(400, {"error": str(error)})
        except Exception as error:  # Keep the local UI responsive without leaking traces.
            self._json(500, {"error": f"render failed: {error}"})

    def log_message(self, message: str, *args) -> None:
        print(f"[edgeglyph:web] {self.address_string()} {message % args}")


class WorkbenchServer(ThreadingHTTPServer):
    daemon_threads = True


def serve(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True) -> None:
    if host not in LOOPBACK_HOSTS:
        raise ValueError("the workbench may only bind to a loopback address")
    if not 1 <= port <= 65535:
        raise ValueError("port must be between 1 and 65535")
    server = WorkbenchServer((host, port), WorkbenchHandler)
    display_host = f"[{host}]" if ":" in host else host
    url = f"http://{display_host}:{port}"
    print(f"EdgeGlyph workbench: {url}")
    if open_browser:
        threading.Timer(0.25, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
