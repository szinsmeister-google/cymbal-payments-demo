#!/usr/bin/env python3
"""Zero-dependency local static server for the Cymbal Payments Checkout App.

Usage:
  python3 apps/checkout-web/serve_local.py [port]
"""

from __future__ import annotations

import http.server
import os
import socketserver
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8090


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(APP_DIR), **kwargs)


def main() -> None:
    os.chdir(APP_DIR)
    with socketserver.TCPServer(("0.0.0.0", PORT), QuietHandler) as httpd:
        print(f"Cymbal Payments Checkout App running at http://localhost:{PORT}")
        print("Tip: Append ?api=https://<YOUR_CLOUD_RUN_URL> or create apps/checkout-web/config.js")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
