#!/usr/bin/env -S mise x -E local -- uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = ["pydantic>=2.10", "httpx>=0.28"]
# ///
"""Team overview: state/priority/label/project distribution."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime

from models import PRIORITY_MAP, cycle_sort_key, get_default_since_date
from selection import issues_created_since, projects_for_team
from tool_io import emit_csv, emit_meta, emit_prompt, end, log
from tool_prompts import build_prompt


def analyze_team(team_key: str, since_date: str | None = None, *, debug: bool = False) -> None:
    since = since_date or get_default_since_date()
    log(f"Fetching issues for {team_key} since {since}...")
    issues = issues_created_since(team_key, since, debug=debug)
    projects = projects_for_team(team_key, debug=debug)
    now = datetime.now(UTC)

    total_issues = len(issues)
    total_projects = len(projects)
    sub_issues = sum(1 for i in issues if i.parent)
    no_project = sum(1 for i in issues if not i.project)
    no_estimate = sum(1 for i in issues if i.estimate is None)
    with_sla = [i for i in issues if i.slaBreachesAt]
    breached = sum(1 for i in with_sla if i.is_sla_breached)
    pending = sum(1 for i in with_sla if i.is_sla_at_risk)

    emit_meta(
        {
            "tool": "overview",
            "team": team_key,
            "since": since,
            "generated_at": now.isoformat(),
            "selection": "createdAt>=since",
            "total_issues": total_issues,
            "total_projects": total_projects,
        }
    )

    # State distribution
    state_counts = Counter(i.state_type for i in issues)
    state_rows = [
        [state, count, f"{count / total_issues * 100:.1f}%" if total_issues else "0%"]
        for state, count in state_counts.most_common()
    ]

    # Priority distribution
    priority_counts = Counter(i.priority for i in issues)
    priority_rows = []
    for pri in [1, 2, 3, 4, 0]:
        if pri in priority_counts:
            pct = priority_counts[pri] / total_issues * 100 if total_issues else 0
            priority_rows.append([PRIORITY_MAP[pri], priority_counts[pri], f"{pct:.1f}%"])

    # Label distribution
    all_labels = [lbl for i in issues for lbl in i.label_names]
    label_rows = [[label, count] for label, count in Counter(all_labels).most_common(10)]

    # Project distribution
    project_counts = Counter(i.project.name if i.project else None for i in issues)
    project_rows = [["(No project)", project_counts.get(None, 0)]]
    project_rows.extend(
        [
            [proj, count]
            for proj, count in sorted(((k, v) for k, v in project_counts.items() if k), key=lambda x: -x[1])[:10]
        ]
    )

    # Estimate distribution
    estimate_rows = [
        ["(No estimate)", no_estimate, f"{no_estimate / total_issues * 100:.1f}%" if total_issues else "0%"]
    ]
    estimate_counts = Counter(i.estimate for i in issues if i.estimate is not None)
    for est, count in sorted(estimate_counts.items()):
        estimate_rows.append([f"{est} points", count, ""])

    # Cycle distribution
    cycle_counts = Counter(i.cycle_number for i in issues)
    cycle_rows = [
        [f"Cycle {num}" if num is not None else "(No cycle)", count]
        for num, count in sorted(cycle_counts.items(), key=lambda x: cycle_sort_key(x[0]))[:10]
    ]

    # Milestone distribution
    milestone_counts = Counter(i.milestone_name or "(No milestone)" for i in issues)
    milestone_rows = [[ms, count] for ms, count in milestone_counts.most_common(10)]

    # SLA status
    sla_rows = [
        ["With SLA", len(with_sla)],
        ["Breached", breached],
        ["At risk", pending],
    ]

    top_state = state_rows[0][0] if state_rows else "N/A"
    top_state_pct = state_rows[0][2] if state_rows else "N/A"
    top_label = label_rows[0][0] if label_rows else "N/A"
    top_label_count = label_rows[0][1] if label_rows else 0
    no_project_pct = f"{no_project / total_issues * 100:.1f}%" if total_issues else "0%"
    no_estimate_pct = f"{no_estimate / total_issues * 100:.1f}%" if total_issues else "0%"

    prompt = build_prompt(
        findings=[
            f"State Distribution (State, Count, Pct): top state is {top_state} at {top_state_pct}.",
            f"Label Distribution (Label, Count): top label is {top_label} with Count={top_label_count}.",
            f"Project Distribution (Project, Count): (No project) Count={project_counts.get(None, 0)} ({no_project_pct}).",
            f"Estimate Distribution (Estimate, Count, Pct): (No estimate) Count={no_estimate} ({no_estimate_pct}).",
            f"SLA Status (Metric, Count): Breached={breached}, At risk={pending} (With SLA={len(with_sla)}).",
        ],
        recommendations=[
            f"Keep (No estimate) in Estimate Distribution below 20% (current Pct={no_estimate_pct}).",
            f"Reduce (No project) in Project Distribution below 20% (current Pct={no_project_pct}).",
            f"Drive SLA Status to Breached=0 and At risk=0; current Breached={breached}, At risk={pending}.",
        ],
        next_checks=[
            "Run wip.py to review WIP Aging and identify stalled items.",
            "Run sla.py to deep-dive Lead Time by Priority and SLA hit rates.",
            "Run flow.py to confirm Queue vs Execution bottlenecks.",
        ],
    )

    emit_prompt(prompt)
    emit_csv("state_distribution", ["State", "Count", "Pct"], state_rows)
    emit_csv("priority_distribution", ["Priority", "Count", "Pct"], priority_rows)
    emit_csv("label_distribution", ["Label", "Count"], label_rows)
    emit_csv("project_distribution", ["Project", "Count"], project_rows)
    emit_csv("estimate_distribution", ["Estimate", "Count", "Pct"], estimate_rows)
    emit_csv("cycle_distribution", ["Cycle", "Count"], cycle_rows)
    emit_csv("milestone_distribution", ["Milestone", "Count"], milestone_rows)
    emit_csv("sla_status", ["Metric", "Count"], sla_rows)
    emit_csv("summary", ["Metric", "Value"], [["Sub-issues", sub_issues]])
    end()


if __name__ == "__main__":
    from cli import parse_team_args  # type: ignore[attr-defined]

    args = parse_team_args("Team overview analysis")
    analyze_team(args.team_key, args.since, debug=args.debug)
