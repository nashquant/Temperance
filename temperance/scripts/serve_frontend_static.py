#!/usr/bin/env python3
from __future__ import annotations

import argparse
import functools
import http.server
import socketserver
from pathlib import Path


class SpaStaticHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, directory: str, **kwargs):
        super().__init__(*args, directory=directory, **kwargs)

    def _serve_with_spa_fallback(self, method_name: str) -> None:
        request_path = Path(self.translate_path(self.path))
        if request_path.exists() and request_path.is_file():
            return getattr(super(), method_name)()

        self.path = "/index.html"
        return getattr(super(), method_name)()

    def do_GET(self) -> None:
        self._serve_with_spa_fallback("do_GET")

    def do_HEAD(self) -> None:
        self._serve_with_spa_fallback("do_HEAD")

    def end_headers(self) -> None:
        if self.path == "/index.html":
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve a built SPA with index.html fallback.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=4173, type=int)
    parser.add_argument("--root", required=True)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        raise SystemExit(f"Static root does not exist: {root}")

    handler = functools.partial(SpaStaticHandler, directory=str(root))

    class ReusableTCPServer(socketserver.TCPServer):
        allow_reuse_address = True

    with ReusableTCPServer((args.host, args.port), handler) as httpd:
        httpd.serve_forever()


if __name__ == "__main__":
    main()
