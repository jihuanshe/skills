#!/usr/bin/env -S mise x -E local -- uv run --script
# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = ["pydantic>=2.10", "httpx>=0.28"]
# ///

from __future__ import annotations

import sys
from datetime import UTC, datetime

from filters import FILTERS, FilterSpec
from models import PRIORITY_ICONS, PRIORITY_MAP, Issue, get_default_since_date
from tool_io import RowValue, emit_csv, emit_meta, emit_prompt, end, log
from tool_prompts import build_prompt


def _selection_label(spec: FilterSpec, since: str | None) -> str:
    if spec.name == "stale_wip":
        return "wip=state.started snapshot"
    if spec.name in {"p1_breached", "p2_breached", "p1_at_risk"}:
        return "sla=open snapshot with slaBreachesAt"
    if spec.name == "recently_completed_bugs":
        return f"completedAt>={since}"
    return "custom"


def _sort_key(name: str):
    if name == "stale_wip":
        return lambda i: -(i.wip_age_days or 0)
    if name in {"p1_breached", "p2_breached", "p1_at_risk"}:
        return lambda i: i.slaBreachesAt or datetime.now(UTC)
    if name == "recently_completed_bugs":
        return lambda i: i.completedAt or datetime.min.replace(tzinfo=UTC)
    return lambda i: i.createdAt or datetime.min.replace(tzinfo=UTC)


def _issue_row(issue: Issue) -> list[RowValue]:
    age = f"{issue.wip_age_days:.1f}" if issue.wip_age_days is not None else ""
    lead = f"{issue.lead_time_days:.1f}" if issue.lead_time_days is not None else ""
    sla_status = "breached" if issue.is_sla_breached else "at_risk" if issue.is_sla_at_risk else ""
    return [
        issue.identifier,
        f"{PRIORITY_ICONS[issue.priority]} {PRIORITY_MAP[issue.priority]}",
        issue.state.name,
        issue.assignee_name,
        age,
        lead,
        sla_status,
        issue.createdAt.isoformat() if issue.createdAt else "",
        issue.startedAt.isoformat() if issue.startedAt else "",
        issue.completedAt.isoformat() if issue.completedAt else "",
        issue.title[:80],
        issue.url,
    ]


def main(team_key: str, filter_name: str, since: str | None, limit: int | None, *, debug: bool) -> None:
    if filter_name not in FILTERS:
        log(f"Unknown filter: {filter_name}")
        log(f"Available filters: {', '.join(sorted(FILTERS.keys()))}")
        sys.exit(1)

    spec = FILTERS[filter_name]
    effective_since = since or (get_default_since_date() if spec.name == "recently_completed_bugs" else None)
    log(f"Running filter {spec.name} for team {team_key}...")
    issues = spec.apply(team_key, effective_since, debug=debug)
    issues.sort(key=_sort_key(spec.name))
    limited = issues[: (limit or spec.default_limit)]

    emit_meta(
        {
            "tool": "hunt",
            "team": team_key,
            "filter": spec.name,
            "since": effective_since or "",
            "generated_at": datetime.now(UTC).isoformat(),
            "selection": _selection_label(spec, effective_since),
            "matched": len(issues),
            "emitted": len(limited),
        }
    )

    prompt = build_prompt(
        findings=[
            f"Issue List (ID, Priority, State, Assignee, AgeDays, LeadTimeDays): matched={len(issues)}.",
            f"Filter description: {spec.description}",
            "Review oldest/highest-risk items at the top of the Issue List.",
        ],
        recommendations=[
            "Assign owners and next actions for the top 5 items in Issue List.",
            "Resolve breached or at-risk SLA items within the target window.",
            "Reduce stale WIP to zero by closing or splitting blocked work.",
        ],
        next_checks=[
            "Run sla.py to review SLA hit rates by priority.",
            "Run wip.py to inspect WIP aging and throughput balance.",
            "Use compare.py to benchmark the same filter across teams.",
        ],
    )

    emit_prompt(prompt)
    emit_csv(
        "issues",
        [
            "ID",
            "Priority",
            "State",
            "Assignee",
            "AgeDays",
            "LeadTimeDays",
            "SLAStatus",
            "CreatedAt",
            "StartedAt",
            "CompletedAt",
            "Title",
            "URL",
        ],
        [_issue_row(i) for i in limited],
    )
    end()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Hunt for issues matching a filter")
    parser.add_argument("team_key", help="Team key (e.g., ENG)")
    parser.add_argument(
        "--filter", required=True, dest="filter_name", help=f"Filter name: {', '.join(sorted(FILTERS.keys()))}"
    )
    parser.add_argument("--since", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--limit", type=int, help="Maximum issues to return")
    parser.add_argument("--debug", "-d", action="store_true", help="Enable debug output")
    args = parser.parse_args()
    main(args.team_key, args.filter_name, args.since, args.limit, debug=args.debug)
