#!/usr/bin/env -S mise x -E local -- uv run --script
# /// script
# requires-python = ">=3.13"
# ///
"""Validate tool output contract from stdin."""

from __future__ import annotations

import re
import sys


def main() -> int:
    data = sys.stdin.read()
    missing = []
    if "===PROMPT===" not in data:
        missing.append("===PROMPT===")
    if "===END===" not in data:
        missing.append("===END===")
    if not re.search(r"^===CSV:.+===$", data, re.MULTILINE):
        missing.append("===CSV:<name>===")

    if missing:
        print(f"Missing markers: {', '.join(missing)}", file=sys.stderr)
        return 1

    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
