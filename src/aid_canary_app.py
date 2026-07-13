#!/usr/bin/env python3
"""Minimal canary app for AI Delivery managed delivery."""

from __future__ import annotations

import argparse
import json

APP_NAME = "AI Delivery Canary App"
VERSION = "0.1.0"


def health() -> dict[str, str]:
    return {"app": APP_NAME, "version": VERSION, "status": "ok"}


def main() -> int:
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--smoke", action="store_true", help="run a smoke check and print JSON")
    args = parser.parse_args()
    if args.smoke:
        print(json.dumps(health(), ensure_ascii=False, sort_keys=True))
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
