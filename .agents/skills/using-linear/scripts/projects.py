#!/usr/bin/env -S mise x -E local -- uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = ["pydantic>=2.10", "httpx>=0.28"]
# ///
"""Project health and scope creep analysis."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime

from models import Project, get_default_since_date
from selection import issues_for_project, projects_for_team
from tool_io import emit_csv, emit_meta, emit_prompt, end, log
from tool_prompts import build_prompt


def _risk_label(project: Project, days_left: int | None, not_done_pct: float, not_done: int) -> str:
    if project.state == "completed":
        return "DONE"
    if project.state == "canceled":
        return "CANCELED"
    if days_left is None:
        return "NO_TARGET"
    if days_left < 0:
        return f"LATE {abs(days_left)}d"
    if days_left <= 3 and not_done_pct > 0.30:
        return f"CRITICAL {not_done} left"
    if days_left <= 7 and not_done_pct > 0.50:
        return f"HIGH {not_done} left"
    if days_left <= 14:
        return f"TIGHT {days_left}d_left"
    return f"ON_TRACK {days_left}d_left"


def analyze_projects(team_key: str, since_date: str | None = None, *, debug: bool = False) -> None:
    since = since_date or get_default_since_date()
    now = datetime.now(UTC)

    log(f"Fetching projects for {team_key}...")
    projects = projects_for_team(team_key, debug=debug)

    overview_rows = []
    active_rows = []
    risk_rows = []
    milestone_rows = []
    contributor_rows = []

    for project in projects:
        if not project.id:
            continue
        log(f"Fetching issues for project {project.name} ({project.id})...")
        issues = issues_for_project(project.id, debug=debug)
        if not issues:
            continue

        total = len(issues)
        done = sum(1 for i in issues if i.is_completed)
        canceled = sum(1 for i in issues if i.is_canceled)
        started = sum(1 for i in issues if i.is_wip)
        backlog = sum(1 for i in issues if i.state_type in ("backlog", "unstarted", "triage"))
        not_done = total - done - canceled
        not_done_pct = not_done / total if total else 0
        created_since = sum(1 for i in issues if i.createdAt and i.createdAt.strftime("%Y-%m-%d") >= since)

        days_left = (project.targetDate - now).days if project.targetDate else None
        risk = _risk_label(project, days_left, not_done_pct, not_done)

        scope_creep = 0.0
        if project.startDate:
            created_after = sum(1 for i in issues if i.createdAt and i.createdAt > project.startDate)
            scope_creep = created_after / total * 100 if total else 0

        health = project.health or "unknown"
        target = project.targetDate.strftime("%Y-%m-%d") if project.targetDate else "N/A"
        progress = project.progress * 100

        overview_rows.append(
            [
                project.name[:30],
                project.state,
                f"{progress:.0f}%",
                health,
                target,
                risk,
                f"{scope_creep:.0f}%",
                total,
                not_done,
                created_since,
            ]
        )

        # Active project details
        if project.state in ("started", "planned"):
            pts_total = sum(i.estimate or 0 for i in issues)
            pts_done = sum(i.estimate or 0 for i in issues if i.is_completed)
            remaining = total - done - canceled
            req_velocity = ""
            if days_left and days_left > 0 and remaining > 0:
                req_velocity = f"{remaining / (days_left / 7):.1f}"

            unestimated = sum(1 for i in issues if i.estimate is None and i.state_type not in ("completed", "canceled"))
            high_pri_not_started = sum(
                1 for i in issues if i.is_high_priority and i.state_type in ("backlog", "unstarted", "triage")
            )
            unassigned = sum(
                1 for i in issues if i.assignee_name == "Unassigned" and i.state_type not in ("completed", "canceled")
            )
            stale_wip = sum(1 for i in issues if i.wip_age_days and i.wip_age_days > 14)

            active_rows.append(
                [
                    project.name[:30],
                    health,
                    project.state,
                    done,
                    started,
                    backlog,
                    total,
                    f"{pts_done}/{pts_total}",
                    days_left if days_left is not None else "N/A",
                    remaining,
                    req_velocity or "N/A",
                    unestimated,
                    high_pri_not_started,
                    unassigned,
                    stale_wip,
                ]
            )

            risk_rows.append(
                [
                    project.name[:30],
                    risk,
                    unestimated,
                    high_pri_not_started,
                    unassigned,
                    stale_wip,
                ]
            )

            assignees = Counter(i.assignee_name for i in issues if i.assignee_name != "Unassigned")
            for name, count in assignees.most_common(5):
                contributor_rows.append([project.name[:30], name, count])

        # Milestones
        if project.milestones:
            for m in sorted(project.milestones, key=lambda x: x.sortOrder):
                target_dt = m.targetDate.strftime("%Y-%m-%d") if m.targetDate else "N/A"
                status = "OVERDUE" if m.targetDate and m.targetDate < now else "UPCOMING"
                milestone_rows.append([project.name[:30], m.name, target_dt, status])

    high_risk = sum(1 for row in overview_rows if row[5].startswith(("LATE", "CRITICAL", "HIGH")))
    scope_creep_high = sum(1 for row in overview_rows if float(row[6].rstrip("%")) > 50)

    emit_meta(
        {
            "tool": "projects",
            "team": team_key,
            "since": since,
            "generated_at": now.isoformat(),
            "selection": "projects=team snapshot; project_issues=project snapshot; activity=createdAt>=since",
            "projects_count": len(overview_rows),
            "high_risk_projects": high_risk,
        }
    )

    prompt = build_prompt(
        findings=[
            "Project Overview (Project, State, Progress, Health, Target, Risk, ScopeCreepPct): review Risk and ScopeCreepPct columns.",
            f"Active Projects (Project, Done, WIP, Backlog, DaysLeft, ReqVelocity): high risk count={high_risk}.",
            f"Scope creep >50% appears in {scope_creep_high} projects.",
        ],
        recommendations=[
            "Reduce scope creep for projects above 50% by re-baselining or splitting scope.",
            "For HIGH/CRITICAL/LATE projects, cut backlog or extend targets to match velocity.",
            "Address unestimated, unassigned, and stale WIP items in Active Projects.",
        ],
        next_checks=[
            "Run forecast.py to validate delivery risk against team velocity.",
            "Run wip.py to see stale WIP contributing to project delays.",
            "Use hunt.py with filter stale_wip to list blockers.",
        ],
    )

    emit_prompt(prompt)
    emit_csv(
        "project_overview",
        ["Project", "State", "Progress", "Health", "Target", "Risk", "ScopeCreepPct", "Total", "Open", "CreatedSince"],
        overview_rows,
    )
    emit_csv(
        "active_projects",
        [
            "Project",
            "Health",
            "State",
            "Done",
            "WIP",
            "Backlog",
            "Total",
            "PointsDone/Total",
            "DaysLeft",
            "Remaining",
            "ReqVelocity",
            "UnestimatedOpen",
            "HighPriNotStarted",
            "UnassignedOpen",
            "StaleWIP",
        ],
        active_rows,
    )
    emit_csv(
        "project_risks",
        ["Project", "Risk", "UnestimatedOpen", "HighPriNotStarted", "UnassignedOpen", "StaleWIP"],
        risk_rows,
    )
    emit_csv("project_milestones", ["Project", "Milestone", "TargetDate", "Status"], milestone_rows)
    emit_csv("project_contributors", ["Project", "Assignee", "IssueCount"], contributor_rows)
    end()


if __name__ == "__main__":
    from cli import parse_team_args  # type: ignore[attr-defined]

    args = parse_team_args("Analyze team projects")
    analyze_projects(args.team_key, args.since, debug=args.debug)
