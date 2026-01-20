#!/usr/bin/env -S mise x -E local -- uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = ["pydantic>=2.10", "httpx>=0.28"]
# ///
"""Person load analysis and bottleneck detection."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import TypedDict

from models import get_default_since_date
from selection import issues_completed_since, issues_created_since, open_issues_with_sla, wip_started_snapshot
from tool_io import emit_csv, emit_meta, emit_prompt, end, log
from tool_prompts import build_prompt


class CreatedStats(TypedDict):
    total: int
    completed: int
    canceled: int
    points: int
    points_done: int
    projects: set[str]


class CompletedStats(TypedDict):
    p1_lt: list[float]
    p2_lt: list[float]
    count: int


class WipStats(TypedDict):
    count: int
    max_age: float
    issues: list[str]


def analyze_person_load(team_key: str, since_date: str | None = None, *, debug: bool = False) -> None:
    since = since_date or get_default_since_date()
    now = datetime.now(UTC)

    log(f"Fetching created cohort for {team_key} since {since}...")
    created = issues_created_since(team_key, since, debug=debug)
    log(f"Fetching completed window for {team_key} since {since}...")
    completed = issues_completed_since(team_key, since, debug=debug)
    log(f"Fetching WIP snapshot for {team_key}...")
    wip = wip_started_snapshot(team_key, debug=debug)
    log(f"Fetching open SLA snapshot for {team_key}...")
    open_sla = open_issues_with_sla(team_key, debug=debug)

    emit_meta(
        {
            "tool": "workload",
            "team": team_key,
            "since": since,
            "generated_at": now.isoformat(),
            "selection": "created=createdAt>=since; completed=completedAt>=since; wip=state.started snapshot; sla=open snapshot with slaBreachesAt",
        }
    )

    # Created cohort stats
    created_stats: defaultdict[str, CreatedStats] = defaultdict(
        lambda: {
            "total": 0,
            "completed": 0,
            "canceled": 0,
            "points": 0,
            "points_done": 0,
            "projects": set[str](),
        }
    )
    for i in created:
        p = created_stats[i.assignee_name]
        p["total"] += 1
        p["points"] += i.estimate or 0
        if i.project:
            p["projects"].add(i.project.name)
        if i.is_completed:
            p["completed"] += 1
            p["points_done"] += i.estimate or 0
        elif i.is_canceled:
            p["canceled"] += 1

    # Completed window stats for SLA hit rates
    completed_stats: defaultdict[str, CompletedStats] = defaultdict(
        lambda: {"p1_lt": list[float](), "p2_lt": list[float](), "count": 0}
    )
    for i in completed:
        p = completed_stats[i.assignee_name]
        p["count"] += 1
        if (lt := i.lead_time_days) is not None:
            if i.priority == 1:
                p["p1_lt"].append(lt)
            elif i.priority == 2:
                p["p2_lt"].append(lt)

    # WIP snapshot stats
    wip_stats: defaultdict[str, WipStats] = defaultdict(lambda: {"count": 0, "max_age": 0.0, "issues": list[str]()})
    for i in wip:
        if i.startedAt:
            age = (now - i.startedAt).total_seconds() / 86400
            record = wip_stats[i.assignee_name]
            record["count"] += 1
            record["max_age"] = max(record["max_age"], age)
            record["issues"] = record["issues"] + [i.identifier]

    # Open SLA risk stats
    sla_stats: dict[str, dict[str, int]] = defaultdict(lambda: {"breached": 0, "at_risk": 0})
    for i in open_sla:
        if i.assignee_name == "Unassigned":
            continue
        if i.is_sla_breached:
            sla_stats[i.assignee_name]["breached"] += 1
        elif i.is_sla_at_risk:
            sla_stats[i.assignee_name]["at_risk"] += 1

    # Person overview table
    overview_rows = []
    for name in sorted(created_stats.keys(), key=lambda x: -created_stats[x]["total"]):
        if name == "Unassigned":
            continue
        c = created_stats[name]
        w = wip_stats[name]
        overview_rows.append(
            [
                name,
                c["total"],
                c["completed"],
                c["canceled"],
                w["count"],
                f"{w['max_age']:.1f}",
                c["points"],
                c["points_done"],
                len(c["projects"]),
            ]
        )

    # SLA hit rates table (completed window)
    sla_rows = []
    sla_p1, sla_p2 = 3, 7
    for name in sorted(completed_stats.keys(), key=lambda x: -completed_stats[x]["count"]):
        if name == "Unassigned":
            continue
        p = completed_stats[name]
        p1_times = p["p1_lt"]
        p2_times = p["p2_lt"]
        p1_hit = sum(1 for lt in p1_times if lt <= sla_p1)
        p2_hit = sum(1 for lt in p2_times if lt <= sla_p2)
        p1_rate = p1_hit / len(p1_times) * 100 if p1_times else 0
        p2_rate = p2_hit / len(p2_times) * 100 if p2_times else 0
        sla_rows.append(
            [
                name,
                f"{p1_hit}/{len(p1_times)}",
                f"{p1_rate:.0f}%",
                f"{p2_hit}/{len(p2_times)}",
                f"{p2_rate:.0f}%",
                p["count"],
            ]
        )

    # WIP details table
    wip_rows = []
    for name in sorted(wip_stats.keys(), key=lambda x: -wip_stats[x]["count"]):
        if name == "Unassigned":
            continue
        w = wip_stats[name]
        issues_str = " ".join(w["issues"][:5])
        if len(w["issues"]) > 5:
            issues_str += f" (+{len(w['issues']) - 5})"
        wip_rows.append([name, w["count"], f"{w['max_age']:.1f}", issues_str])

    # SLA open risk table
    sla_open_rows = []
    for name in sorted(sla_stats.keys(), key=lambda x: -(sla_stats[x]["breached"] + sla_stats[x]["at_risk"])):
        s = sla_stats[name]
        sla_open_rows.append([name, s["breached"], s["at_risk"]])

    # Long lead time table
    long_lead = []
    for i in completed:
        if (lt := i.lead_time_days) is not None and lt > 14:
            long_lead.append((i.identifier, lt, i.assignee_name, i.title[:60]))
    long_lead.sort(key=lambda x: -x[1])
    long_lead_rows = [[ident, f"{lt:.1f}", name, title] for ident, lt, name, title in long_lead[:10]]

    high_wip = sum(1 for _, _, _, _, wip_count, *_ in overview_rows if wip_count >= 5)
    breached_total = sum(r[1] for r in sla_open_rows) if sla_open_rows else 0

    prompt = build_prompt(
        findings=[
            "Person Overview (Name, Created, Completed, Canceled, WIP, MaxAgeDays, Points, PointsDone, Projects): check high WIP and MaxAgeDays.",
            "SLA Hit Rates (Name, P1Hit, P1Rate, P2Hit, P2Rate, Completed): review low hit rates.",
            f"SLA Open Risk (Name, Breached, AtRisk): total breached={breached_total}.",
            "Long Lead Time (ID, LeadTimeDays, Assignee, Title): review top 10 slowest completions.",
        ],
        recommendations=[
            f"Reduce WIP owners with WIP>=5 (current count={high_wip}).",
            "Raise P1/P2 hit rates toward 80% by reducing queue time or splitting work.",
            "Clear SLA breaches first; then focus on at-risk items.",
        ],
        next_checks=[
            "Run wip.py to see team-level WIP aging and throughput balance.",
            "Run flow.py to understand queue vs execution contributors.",
            "Use hunt.py with p1_breached or stale_wip to target fixes.",
        ],
    )

    emit_prompt(prompt)
    emit_csv(
        "person_overview",
        ["Name", "Created", "Completed", "Canceled", "WIP", "MaxAgeDays", "Points", "PointsDone", "Projects"],
        overview_rows,
    )
    emit_csv("sla_hit_rates", ["Name", "P1Hit", "P1Rate", "P2Hit", "P2Rate", "Completed"], sla_rows)
    emit_csv("wip_by_person", ["Name", "WIP", "MaxAgeDays", "Issues"], wip_rows)
    emit_csv("sla_open_risk", ["Name", "Breached", "AtRisk"], sla_open_rows)
    emit_csv("long_lead_time", ["ID", "LeadTimeDays", "Assignee", "Title"], long_lead_rows)
    end()


if __name__ == "__main__":
    from cli import parse_team_args  # type: ignore[attr-defined]

    args = parse_team_args("Analyze team workload")
    analyze_person_load(args.team_key, args.since, debug=args.debug)
