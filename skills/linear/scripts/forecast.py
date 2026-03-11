#!/usr/bin/env -S mise x -E local -- uv run --script
# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = ["pydantic>=2.10", "httpx>=0.28"]
# ///

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from random import choices
from statistics import mean, stdev
from typing import TypedDict

from models import Issue, Project, get_default_since_date, get_iso_week, percentile
from selection import issues_completed_since, issues_for_project, projects_for_team
from tool_io import emit_csv, emit_meta, emit_prompt, end, log
from tool_prompts import build_prompt


class ProjectAnalysis(TypedDict):
    project: Project
    done: int
    wip: int
    backlog: int
    remaining: int
    done_points: float
    remaining_points: float
    total_points: float
    days_left: int | None
    weeks_left: float
    avg_velocity_issues: float
    avg_velocity_points: float
    required_velocity: float
    velocity_ratio: float
    risk_level: str
    mc_p50: float
    mc_p75: float
    mc_p90: float
    mc_not_finished_pct: float
    stale_wip: list[Issue]
    unassigned: list[Issue]
    unestimated: list[Issue]
    high_priority_not_started: list[Issue]
    scope_creep: float


def get_weekly_velocity(issues: list[Issue], weeks: int = 8) -> dict[str, dict[str, float]]:
    """Calculate weekly velocity (issues and points completed) for last N weeks."""
    now = datetime.now(UTC)
    cutoff = now - timedelta(weeks=weeks)
    completed = [i for i in issues if i.is_completed and i.completedAt and i.completedAt > cutoff]

    weekly: dict[str, dict[str, float]] = {}
    for i in range(weeks):
        week_dt = now - timedelta(weeks=i)
        week_key = get_iso_week(week_dt)
        if week_key:
            weekly[week_key] = {"issues": 0.0, "points": 0.0}

    for issue in completed:
        week = get_iso_week(issue.completedAt)
        if week and week in weekly:
            weekly[week]["issues"] += 1
            weekly[week]["points"] += issue.estimate or 0

    return weekly


def monte_carlo_forecast(
    remaining_issues: int,
    weekly_velocities: list[dict[str, float]],
    simulations: int = 1000,
) -> dict[str, float]:
    """Run Monte Carlo simulation to forecast completion time."""
    if not weekly_velocities or remaining_issues == 0:
        return {"p50": 0, "p75": 0, "p90": 0, "p95": 0, "not_finished_pct": 0}

    issue_velocities = [w["issues"] for w in weekly_velocities]
    if all(v == 0 for v in issue_velocities):
        return {
            "p50": float("inf"),
            "p75": float("inf"),
            "p90": float("inf"),
            "p95": float("inf"),
            "not_finished_pct": 100,
        }

    completion_weeks: list[float] = []
    not_finished = 0
    max_weeks = 52

    for _ in range(simulations):
        remaining = remaining_issues
        weeks = 0
        while remaining > 0 and weeks < max_weeks:
            velocity = choices(issue_velocities)[0]
            remaining -= velocity
            weeks += 1

        if remaining > 0:
            completion_weeks.append(float("inf"))
            not_finished += 1
        else:
            completion_weeks.append(weeks)

    return {
        "p50": percentile(completion_weeks, 50),
        "p75": percentile(completion_weeks, 75),
        "p90": percentile(completion_weeks, 90),
        "p95": percentile(completion_weeks, 95),
        "not_finished_pct": not_finished / simulations * 100,
    }


def analyze_project_risk(
    project: Project,
    project_issues: list[Issue],
    team_weekly_velocity: dict[str, dict[str, float]],
) -> ProjectAnalysis:
    now = datetime.now(UTC)

    done = [i for i in project_issues if i.is_completed]
    wip = [i for i in project_issues if i.is_wip]
    backlog = [i for i in project_issues if i.state_type in ("backlog", "unstarted", "triage")]
    canceled = [i for i in project_issues if i.is_canceled]

    remaining = wip + backlog
    remaining_count = len(remaining)
    remaining_points = sum(i.estimate or 0 for i in remaining)
    done_points = sum(i.estimate or 0 for i in done)
    total_points = done_points + remaining_points + sum(i.estimate or 0 for i in canceled)

    days_left = (project.targetDate - now).days if project.targetDate else None
    weekly_data = list(team_weekly_velocity.values())
    avg_velocity_issues = mean([w["issues"] for w in weekly_data]) if weekly_data else 0
    avg_velocity_points = mean([w["points"] for w in weekly_data]) if weekly_data else 0

    mc_forecast = monte_carlo_forecast(remaining_count, weekly_data)

    if days_left is not None and days_left > 0:
        weeks_left = days_left / 7
        required_velocity = remaining_count / weeks_left if weeks_left > 0 else float("inf")
        velocity_ratio = required_velocity / avg_velocity_issues if avg_velocity_issues > 0 else float("inf")
    else:
        weeks_left = 0
        required_velocity = float("inf")
        velocity_ratio = float("inf")

    if project.state == "completed":
        risk_level = "DONE"
    elif days_left is None:
        risk_level = "NO_TARGET"
    elif days_left < 0:
        risk_level = "LATE"
    elif velocity_ratio > 2:
        risk_level = "CRITICAL"
    elif velocity_ratio > 1.5:
        risk_level = "HIGH"
    elif velocity_ratio > 1:
        risk_level = "MEDIUM"
    else:
        risk_level = "ON_TRACK"

    stale_wip = [i for i in wip if i.wip_age_days and i.wip_age_days > 14]
    unassigned = [i for i in remaining if i.assignee_name == "Unassigned"]
    unestimated = [i for i in remaining if i.estimate is None]
    high_priority_not_started = [i for i in backlog if i.is_high_priority]

    scope_creep = 0.0
    if project.startDate:
        added_after_start = [i for i in project_issues if i.createdAt and i.createdAt > project.startDate]
        original = len(project_issues) - len(added_after_start)
        if original > 0:
            scope_creep = len(added_after_start) / original * 100

    return {
        "project": project,
        "done": len(done),
        "wip": len(wip),
        "backlog": len(backlog),
        "remaining": remaining_count,
        "done_points": done_points,
        "remaining_points": remaining_points,
        "total_points": total_points,
        "days_left": days_left,
        "weeks_left": weeks_left,
        "avg_velocity_issues": avg_velocity_issues,
        "avg_velocity_points": avg_velocity_points,
        "required_velocity": required_velocity,
        "velocity_ratio": velocity_ratio,
        "risk_level": risk_level,
        "mc_p50": mc_forecast["p50"],
        "mc_p75": mc_forecast["p75"],
        "mc_p90": mc_forecast["p90"],
        "mc_not_finished_pct": mc_forecast["not_finished_pct"],
        "stale_wip": stale_wip,
        "unassigned": unassigned,
        "unestimated": unestimated,
        "high_priority_not_started": high_priority_not_started,
        "scope_creep": scope_creep,
    }


def main(team_key: str, since_date: str | None, *, debug: bool = False) -> None:
    since_date = since_date or get_default_since_date(120)

    now = datetime.now(UTC)
    velocity_since = (now - timedelta(weeks=8)).strftime("%Y-%m-%d")

    log(f"Fetching completed window for velocity since {velocity_since}...")
    velocity_issues = issues_completed_since(team_key, velocity_since, debug=debug)
    log(f"Fetching projects for {team_key}...")
    projects = projects_for_team(team_key, debug=debug)

    weekly_velocity = get_weekly_velocity(velocity_issues, weeks=8)
    sorted_weeks = sorted(weekly_velocity.keys())

    if weekly_velocity:
        all_issues_vel = [weekly_velocity[w]["issues"] for w in sorted_weeks]
        all_points_vel = [weekly_velocity[w]["points"] for w in sorted_weeks]
        avg_issues = mean(all_issues_vel)
        avg_points = mean(all_points_vel)
        std_issues = stdev(all_issues_vel) if len(all_issues_vel) > 1 else 0
        std_points = stdev(all_points_vel) if len(all_points_vel) > 1 else 0
    else:
        avg_issues = avg_points = std_issues = std_points = 0

    active_projects = [p for p in projects if p.state in ("started", "planned")]
    project_analyses: list[ProjectAnalysis] = []

    for proj in active_projects:
        if not proj.id:
            continue
        log(f"Fetching issues for project {proj.name} ({proj.id})...")
        proj_issues = issues_for_project(proj.id, debug=debug)
        if not proj_issues:
            continue
        analysis = analyze_project_risk(proj, proj_issues, weekly_velocity)
        project_analyses.append(analysis)

    risk_order = {
        "CRITICAL": 0,
        "LATE": 0,
        "HIGH": 1,
        "MEDIUM": 2,
        "ON_TRACK": 3,
        "NO_TARGET": 4,
        "DONE": 5,
    }
    project_analyses.sort(key=lambda x: risk_order.get(x["risk_level"], 9))

    emit_meta(
        {
            "tool": "forecast",
            "team": team_key,
            "since": since_date,
            "generated_at": now.isoformat(),
            "selection": "velocity=completedAt>=last8w; project_issues=project snapshot",
            "velocity_since": velocity_since,
            "active_projects": len(active_projects),
        }
    )

    velocity_rows = [
        [w, f"{weekly_velocity[w]['issues']:.0f}", f"{weekly_velocity[w]['points']:.0f}"] for w in sorted_weeks
    ]

    risk_rows = [
        [
            a["project"].name[:30],
            a["risk_level"],
            a["done"],
            a["wip"],
            a["remaining"],
            a["remaining_points"],
            a["days_left"] if a["days_left"] is not None else "N/A",
            f"{a['required_velocity']:.1f}" if a["required_velocity"] != float("inf") else "inf",
            f"{a['avg_velocity_issues']:.1f}",
            f"{a['velocity_ratio']:.1f}x" if a["velocity_ratio"] != float("inf") else "inf",
        ]
        for a in project_analyses
    ]

    def format_mc_weeks(val: float) -> str:
        return "inf" if val == float("inf") else f"{val:.1f}w"

    def format_forecast_status(a: ProjectAnalysis) -> str:
        if a["mc_not_finished_pct"] > 10.0:
            return f"NOT_FINISHED {a['mc_not_finished_pct']:.0f}%"
        weeks_left = a["weeks_left"]
        if not weeks_left:
            return "NO_TARGET"
        if a["mc_p75"] <= weeks_left:
            return "OK"
        if a["mc_p90"] <= weeks_left:
            return "TIGHT"
        return "AT_RISK"

    forecast_rows = [
        [
            a["project"].name[:30],
            format_mc_weeks(a["mc_p50"]),
            format_mc_weeks(a["mc_p75"]),
            format_mc_weeks(a["mc_p90"]),
            f"{a['weeks_left']:.1f}w" if a["weeks_left"] else "N/A",
            format_forecast_status(a),
        ]
        for a in project_analyses
    ]

    critical = [a for a in project_analyses if str(a["risk_level"]) in {"CRITICAL", "HIGH", "LATE"}]
    critical_rows = [
        [
            a["project"].name[:30],
            a["risk_level"],
            a["remaining"],
            a["days_left"] if a["days_left"] is not None else "N/A",
            f"{a['velocity_ratio']:.1f}x" if a["velocity_ratio"] != float("inf") else "inf",
            len(a["stale_wip"]),
            len(a["unassigned"]),
            len(a["unestimated"]),
            f"{a['scope_creep']:.0f}%",
        ]
        for a in critical[:10]
    ]

    top_risk = critical[0]["project"].name if critical else "N/A"

    prompt = build_prompt(
        findings=[
            f"Team Velocity (Week, Issues, Points): avg {avg_issues:.1f} issues/week +/-{std_issues:.1f}.",
            f"Project Risk (Project, Risk, Done, WIP, Left, Days, ReqVel, AvgVel, Ratio): highest risk is {top_risk}.",
            "Monte Carlo (Project, P50, P75, P90, Target, Status): review projects marked At Risk or Tight.",
        ],
        recommendations=[
            "For Critical/High projects, reduce scope or extend target dates to bring Ratio <= 1.0x.",
            "Reduce stale WIP (>14d) and unassigned items in Critical Details table.",
            "Stabilize velocity by smoothing intake; keep weekly Issues within +/-1 std dev.",
        ],
        next_checks=[
            "Run projects.py to inspect scope creep and milestone risks in detail.",
            "Run wip.py to identify WIP aging that threatens delivery.",
            "Use hunt.py with filter stale_wip to list blockers for critical projects.",
        ],
    )

    emit_prompt(prompt)
    emit_csv("team_velocity_8w", ["Week", "Issues", "Points"], velocity_rows)
    emit_csv(
        "project_risk",
        ["Project", "Risk", "Done", "WIP", "Left", "PtsLeft", "DaysLeft", "ReqVel", "AvgVel", "Ratio"],
        risk_rows,
    )
    emit_csv("monte_carlo", ["Project", "P50", "P75", "P90", "Target", "Status"], forecast_rows)
    emit_csv(
        "critical_details",
        [
            "Project",
            "Risk",
            "Remaining",
            "DaysLeft",
            "VelocityRatio",
            "StaleWIP",
            "Unassigned",
            "Unestimated",
            "ScopeCreep",
        ],
        critical_rows,
    )
    emit_csv(
        "velocity_summary",
        ["Metric", "Value"],
        [
            ["Avg issues/week", f"{avg_issues:.1f}"],
            ["Avg points/week", f"{avg_points:.1f}"],
            ["Std issues/week", f"{std_issues:.1f}"],
            ["Std points/week", f"{std_points:.1f}"],
        ],
    )
    end()


if __name__ == "__main__":
    from cli import parse_team_args  # type: ignore[attr-defined]

    args = parse_team_args("Project forecast and risk analysis")
    main(args.team_key, args.since, debug=args.debug)
