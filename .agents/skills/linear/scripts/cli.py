"""Unified CLI argument parsing for Linear tools."""

from __future__ import annotations

import argparse
from dataclasses import dataclass


@dataclass
class TeamArgs:
    team_key: str
    since: str | None
    debug: bool


@dataclass
class CompareArgs:
    team_keys: list[str]
    since: str | None
    debug: bool


def parse_team_args(description: str) -> TeamArgs:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("team_key", help="Team key (e.g., ENG)")
    parser.add_argument("--since", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--debug", "-d", action="store_true", help="Enable debug output")
    args = parser.parse_args()
    return TeamArgs(team_key=args.team_key, since=args.since, debug=args.debug)


def parse_compare_args(description: str) -> CompareArgs:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("team_keys", nargs="+", help="Team keys to compare (at least 2)")
    parser.add_argument("--since", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--debug", "-d", action="store_true", help="Enable debug output")
    args = parser.parse_args()
    if len(args.team_keys) < 2:
        parser.error("At least 2 team keys required for comparison")
    return CompareArgs(team_keys=args.team_keys, since=args.since, debug=args.debug)
