#!/usr/bin/env python3
"""Delivery Operations Console entrypoint."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from delivery_ops import server

APP_NAME = "AI Delivery Canary App"
VERSION = "0.3.0"
DEFAULT_HOST = "127.0.0.1"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_data_dir() -> Path:
    return repo_root() / ".ai-delivery" / "runtime" / "delivery-ops-data"


def default_web_root() -> Path:
    return repo_root() / "web"


def health() -> dict[str, str]:
    return {
        "app": APP_NAME,
        "version": VERSION,
        "status": "ok",
        "managed_delivery": "enabled",
        "host": DEFAULT_HOST,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Delivery Operations Console")
    parser.add_argument("--smoke", action="store_true", help="print health JSON and exit")
    parser.add_argument("--host", default=DEFAULT_HOST, help="bind host, loopback only")
    parser.add_argument("--port", default=8000, type=int, help="bind port")
    parser.add_argument("--data-dir", default=str(default_data_dir()), help="state directory")
    parser.add_argument("--web-root", default=str(default_web_root()), help="static asset directory")
    return parser.parse_args(argv)


def resolve_token() -> str | None:
    token = os.environ.get("DELIVERY_OPS_TOKEN")
    if token is None:
        return None
    token = token.strip()
    return token or None


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.smoke:
        print(json.dumps(health(), ensure_ascii=False, sort_keys=True))
        return 0
    if args.host != DEFAULT_HOST:
        raise SystemExit("Delivery Operations Console must bind to 127.0.0.1")
    token = resolve_token()
    httpd = server.create_server(
        host=args.host,
        port=args.port,
        token=token,
        data_dir=args.data_dir,
        web_root=args.web_root,
    )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
