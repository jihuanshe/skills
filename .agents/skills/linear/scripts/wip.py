#!/usr/bin/env -S mise x -E local -- uv run --script
# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = ["pydantic>=2.10", "httpx>=0.28"]
# ///

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import TypedDict

from models import get_default_since_date, get_iso_week
from selection import (
    issues_canceled_since,
    issues_completed_since,
    issues_created_since,
    wip_started_snapshot,
)
from tool_io import emit_csv, emit_meta, emit_prompt, end, log
from tool_prompts import build_prompt


class PersonWip(TypedDict):
    count: int
    max_age: float
    issues: list[str]


def _new_person_wip() -> PersonWip:
    return {"count": 0, "max_age": 0.0, "issues": list[str]()}


def analyze_wip(team_key: str, since_date: str | None = None, *, debug: bool = False) -> None:
    since = since_date or get_default_since_date()
    now = datetime.now(UTC)

    log(f"Fetching arrivals for {team_key} since {since}...")
    arrivals = issues_created_since(team_key, since, debug=debug)
    log(f"Fetching completions for {team_key} since {since}...")
    done = issues_completed_since(team_key, since, debug=debug)
    log(f"Fetching cancellations for {team_key} since {since}...")
    canceled = issues_canceled_since(team_key, since, debug=debug)
    log(f"Fetching WIP snapshot for {team_key}...")
    wip = wip_started_snapshot(team_key, debug=debug)

    emit_meta(
        {
            "tool": "wip",
            "team": team_key,
            "since": since,
            "generated_at": now.isoformat(),
            "selection": "arrive=createdAt>=since; done=completedAt>=since; cancel=canceledAt>=since; wip=state.started snapshot",
            "arrival_count": len(arrivals),
            "done_count": len(done),
            "cancel_count": len(canceled),
            "wip_count": len(wip),
        }
    )

    # Weekly flow (last 13 weeks)
    weeks: list[str] = []
    weekly: dict[str, dict[str, int]] = {}
    for i in range(12, -1, -1):
        week_key = get_iso_week(now - timedelta(weeks=i))
        if week_key:
            weeks.append(week_key)
            weekly[week_key] = {"arrive": 0, "done": 0, "cancel": 0}

    for i in arrivals:
        if (w := get_iso_week(i.createdAt)) and w in weekly:
            weekly[w]["arrive"] += 1
    for i in done:
        if i.completedAt and (w := get_iso_week(i.completedAt)) and w in weekly:
            weekly[w]["done"] += 1
    for i in canceled:
        if i.canceledAt and (w := get_iso_week(i.canceledAt)) and w in weekly:
            weekly[w]["cancel"] += 1

    weekly_rows = []
    for w in weeks:
        d = weekly[w]
        net = d["arrive"] - d["done"] - d["cancel"]
        rate = d["done"] / d["arrive"] * 100 if d["arrive"] > 0 else 0
        weekly_rows.append([w, d["arrive"], d["done"], d["cancel"], f"{net:+d}", f"{rate:.0f}%"])

    display_done = sum(weekly[w]["done"] for w in weeks)
    display_arrive = sum(weekly[w]["arrive"] for w in weeks)
    avg_throughput = display_done / len(weeks) if weeks else 0
    avg_arrival = display_arrive / len(weeks) if weeks else 0

    # WIP aging
    wip_ages: list[tuple[str, float, str, str]] = []
    for i in wip:
        if i.startedAt:
            age = (now - i.startedAt).total_seconds() / 86400
            wip_ages.append((i.identifier, age, i.assignee_name, i.title[:35]))
    wip_ages.sort(key=lambda x: -x[1])
    wip_aging_rows = []
    for ident, age, assignee, title in wip_ages[:15]:
        status = "stale" if age > 14 else "aging" if age > 7 else "fresh"
        wip_aging_rows.append([status, ident, f"{age:.1f}d", assignee, title])

    over_14d = sum(1 for _, age, _, _ in wip_ages if age > 14)
    over_7d = sum(1 for _, age, _, _ in wip_ages if age > 7)

    # WIP by person
    person_wip: defaultdict[str, PersonWip] = defaultdict(_new_person_wip)
    for i in wip:
        if i.startedAt:
            age = (now - i.startedAt).total_seconds() / 86400
            record = person_wip[i.assignee_name]
            record["count"] += 1
            record["max_age"] = max(record["max_age"], age)
            record["issues"] = record["issues"] + [i.identifier]

    person_rows = []
    for name in sorted(person_wip.keys(), key=lambda x: -person_wip[x]["count"]):
        if name == "Unassigned":
            continue
        pw = person_wip[name]
        issues_list = " ".join(pw["issues"][:5])
        if len(pw["issues"]) > 5:
            issues_list += f" (+{len(pw['issues']) - 5})"
        person_rows.append([name, pw["count"], f"{pw['max_age']:.1f}d", issues_list])

    top_person = person_rows[0][0] if person_rows else "N/A"
    top_person_wip = person_rows[0][1] if person_rows else 0

    prompt = build_prompt(
        findings=[
            f"Weekly Flow (Week, Arrive, Done, Cancel, Net, Rate): avg Arrive={avg_arrival:.1f}/week, avg Done={avg_throughput:.1f}/week.",
            f"WIP Aging (Status, ID, Age, Assignee, Title): {over_14d} items >14d and {over_7d} items >7d.",
            f"WIP by Person (Name, WIP, MaxAge, Issues): highest WIP is {top_person} with WIP={top_person_wip}.",
        ],
        recommendations=[
            f"Keep Arrival close to Throughput; target avg Done >= avg Arrive (currently {avg_throughput:.1f} vs {avg_arrival:.1f}).",
            f"Reduce stale WIP >14d to 0; current count={over_14d}.",
            "Limit individual WIP to 3-5 items; rebalance from high-WIP owners.",
        ],
        next_checks=[
            "Run workload.py to see SLA and WIP load per person.",
            "Run flow.py to validate queue vs execution bottlenecks.",
            "Run sla.py to check response-time automation impact.",
        ],
    )

    emit_prompt(prompt)
    emit_csv("weekly_flow", ["Week", "Arrive", "Done", "Cancel", "Net", "Rate"], weekly_rows)
    emit_csv("wip_aging", ["Status", "ID", "Age", "Assignee", "Title"], wip_aging_rows)
    emit_csv("wip_by_person", ["Name", "WIP", "MaxAge", "Issues"], person_rows)
    end()


if __name__ == "__main__":
    from cli import parse_team_args  # type: ignore[attr-defined]

    args = parse_team_args("Analyze WIP aging and throughput")
    analyze_wip(args.team_key, args.since, debug=args.debug)
