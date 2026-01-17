"""Structured stdout helpers for Linear analysis tools."""

from __future__ import annotations

import csv
import sys
from collections.abc import Iterable, Sequence

MetaValue = str | int | float | bool
RowValue = str | int | float | bool | None


def emit_meta(meta: dict[str, MetaValue]) -> None:
    for key, value in meta.items():
        print(f"@{key}: {value}")


def emit_prompt(prompt: str) -> None:
    print("===PROMPT===")
    print(prompt.rstrip())


def emit_csv(name: str, headers: list[str], rows: Iterable[Sequence[RowValue]]) -> None:
    print(f"===CSV:{name}===")
    writer = csv.writer(sys.stdout)
    writer.writerow(headers)
    writer.writerows(rows)


def end() -> None:
    print("===END===")


def log(*args: object) -> None:
    print(*args, file=sys.stderr)
