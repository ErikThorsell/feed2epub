"""OPDS server: publishes the library folder as an OPDS acquisition catalog for an e-reader to pull from.

Sized for the actual workload -- a single Xteink X4 (and the occasional phone) pulling a handful of daily EPUBs over
the LAN, with TLS terminated upstream by HAProxy. A threaded stdlib server is ample for that; it regenerates the
catalog on every request, so freshly fetched EPUBs appear without a restart. If this ever needs to serve many
concurrent clients, swap it for a static catalog written to disk and fronted by nginx/caddy -- ``opds.build_catalog``
already produces exactly that document. Run with ``python -m feed2epub.serve`` and point an OPDS reader at the URL.
"""

from __future__ import annotations

import argparse
import http.server
import socket
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from .config import ConfigError, load_config
from .opds import build_catalog, scan_library

log = structlog.get_logger()

_CATALOG_PATH = "/catalog.xml"
_CATALOG_TYPE = "application/atom+xml;profile=opds-catalog;kind=acquisition"


def _configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ]
    )


def _lan_ip() -> str:
    """Best-effort local LAN address, so we can print a URL the phone can actually reach. Sends no packets."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("192.0.2.1", 1))  # TEST-NET-1: never routed, just makes the OS pick our source interface
        return str(sock.getsockname()[0])
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def _make_handler(library_dir: Path) -> type[http.server.BaseHTTPRequestHandler]:
    class _Handler(http.server.SimpleHTTPRequestHandler):
        extensions_map = {
            **http.server.SimpleHTTPRequestHandler.extensions_map,
            ".epub": "application/epub+zip",
        }

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            # ``directory`` scopes file serving (and translate_path's traversal guard) to the library folder.
            super().__init__(*args, directory=str(library_dir), **kwargs)

        def _serve_catalog(self, *, include_body: bool) -> None:
            body = build_catalog(scan_library(library_dir), updated=datetime.now(UTC)).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", f"{_CATALOG_TYPE}; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if include_body:
                self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path in ("/", _CATALOG_PATH):
                self._serve_catalog(include_body=True)
                return
            super().do_GET()

        def do_HEAD(self) -> None:
            if self.path in ("/", _CATALOG_PATH):
                self._serve_catalog(include_body=False)
                return
            super().do_HEAD()

        def log_message(self, format: str, *args: Any) -> None:
            log.info("serve.request", client=self.address_string(), message=format % args)

    return _Handler


def main(argv: list[str] | None = None) -> int:
    _configure_logging()
    parser = argparse.ArgumentParser(prog="feed2epub-serve", description="Dev-only OPDS server. Not for production.")
    parser.add_argument("--config", type=Path, default=Path("/config/feeds.yaml"))
    parser.add_argument("--library", type=Path, default=None, help="serve this folder instead of the config output_dir")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)

    library: Path = args.library
    if library is None:
        try:
            library = load_config(args.config).output_dir
        except ConfigError as exc:
            log.error("config.invalid", error=str(exc))
            return 2
    if not library.is_dir():
        log.error("serve.library_missing", library=str(library))
        return 2

    server = http.server.ThreadingHTTPServer((args.host, args.port), _make_handler(library))
    log.info(
        "serve.listening",
        catalog_url=f"http://{_lan_ip()}:{args.port}{_CATALOG_PATH}",
        library=str(library),
        host=args.host,
        port=args.port,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("serve.stopped")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
