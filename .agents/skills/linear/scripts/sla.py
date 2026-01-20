#!/usr/bin/env -S mise x -E local -- uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = ["pydantic>=2.10", "httpx>=0.28"]
# ///
"""SLA and response time analysis."""

from __future__ import annotations

from datetime import UTC, datetime

from models import PRIORITY_ICONS, PRIORITY_MAP, get_default_since_date, percentile
from selection import issues_completed_since, issues_created_since, open_issues_with_sla
from tool_io import RowValue, emit_csv, emit_meta, emit_prompt, end, log
from tool_prompts import build_prompt


def analyze_sla(team_key: str, since_date: str | None = None, *, debug: bool = False) -> None:
    since = since_date or get_default_since_date()
    now = datetime.now(UTC)

    log(f"Fetching created cohort for {team_key} since {since}...")
    created = issues_created_since(team_key, since, debug=debug)
    log(f"Fetching completed window for {team_key} since {since}...")
    completed = issues_completed_since(team_key, since, debug=debug)
    log(f"Fetching open SLA snapshot for {team_key}...")
    open_with_sla = open_issues_with_sla(team_key, debug=debug)

    emit_meta(
        {
            "tool": "sla",
            "team": team_key,
            "since": since,
            "generated_at": now.isoformat(),
            "selection": "dueDate/response=createdAt>=since; leadtime=completedAt>=since; sla=open snapshot with slaBreachesAt",
            "created_count": len(created),
            "completed_count": len(completed),
            "open_sla_count": len(open_with_sla),
        }
    )

    # Due date usage (created cohort)
    with_due = [i for i in created if i.dueDate]
    without_due = [i for i in created if not i.dueDate]
    due_rows: list[list[RowValue]] = [
        [
            "With dueDate",
            len(with_due),
            f"{len(with_due) / len(created) * 100:.1f}%" if created else "0%",
        ],
        [
            "Without dueDate",
            len(without_due),
            f"{len(without_due) / len(created) * 100:.1f}%" if created else "0%",
        ],
    ]

    with_estimates = [est for i in with_due if (est := i.estimate) is not None]
    without_estimates = [est for i in without_due if (est := i.estimate) is not None]
    avg_with = sum(with_estimates) / (len(with_estimates) or 1)
    avg_without = sum(without_estimates) / (len(without_estimates) or 1)
    bias_rows: list[list[RowValue]] = [
        ["With dueDate", f"{avg_with:.2f}"],
        ["Without dueDate", f"{avg_without:.2f}"],
    ]

    # Response time (created cohort)
    started = [i for i in created if i.startedAt]
    instant = sum(1 for i in started if (rs := i.response_seconds) is not None and rs < 60)
    automation_pct = instant / len(started) * 100 if started else 0

    response_rows: list[list[RowValue]] = []
    for pri in [1, 2, 3, 4, 0]:
        pri_issues = [i for i in started if i.priority == pri]
        times = [i.queue_time_days for i in pri_issues if i.queue_time_days is not None]
        if times:
            mean = sum(times) / len(times)
            response_rows.append(
                [
                    f"{PRIORITY_ICONS[pri]} {PRIORITY_MAP[pri]}",
                    f"{mean:.1f}d",
                    f"{percentile(times, 50):.0f}d",
                    f"{percentile(times, 90):.0f}d",
                    f"{percentile(times, 95):.0f}d",
                    len(times),
                ]
            )

    # Lead time by priority (completed window)
    lead_rows: list[list[RowValue]] = []
    for pri in [1, 2, 3, 4, 0]:
        pri_issues = [i for i in completed if i.priority == pri]
        times = [i.lead_time_days for i in pri_issues if i.lead_time_days is not None]
        if times:
            mean = sum(times) / len(times)
            lead_rows.append(
                [
                    f"{PRIORITY_ICONS[pri]} {PRIORITY_MAP[pri]}",
                    f"{mean:.1f}d",
                    f"{percentile(times, 50):.0f}d",
                    f"{percentile(times, 90):.0f}d",
                    f"{percentile(times, 95):.0f}d",
                    len(times),
                ]
            )

    # SLA target check (completed window)
    sla_targets = {1: 3, 2: 7}
    target_rows: list[list[RowValue]] = []
    for pri, target in sla_targets.items():
        pri_completed = [i for i in completed if i.priority == pri]
        times = [i.lead_time_days for i in pri_completed if i.lead_time_days is not None]
        if times:
            hit = sum(1 for t in times if t <= target)
            hit_rate = hit / len(times) * 100
            target_rows.append(
                [f"P{pri} ({PRIORITY_MAP[pri]})", f"{hit}/{len(times)}", f"{hit_rate:.1f}%", f"{target}d"]
            )

    # Open SLA risk (snapshot)
    breached = [i for i in open_with_sla if i.is_sla_breached]
    at_risk = [i for i in open_with_sla if i.is_sla_at_risk]

    breached_rows: list[list[RowValue]] = []
    for i in sorted(breached, key=lambda x: x.slaBreachesAt or x.createdAt or now)[:10]:
        breach_dt = i.slaBreachesAt
        breach_str = breach_dt.strftime("%Y-%m-%d %H:%M") if breach_dt else "N/A"
        breached_rows.append(
            [
                i.identifier,
                f"{PRIORITY_ICONS[i.priority]} {PRIORITY_MAP[i.priority]}",
                i.state.name,
                breach_str,
                i.title[:60],
            ]
        )

    at_risk_rows: list[list[RowValue]] = []
    for i in sorted(at_risk, key=lambda x: x.slaBreachesAt or now)[:10]:
        breach_dt = i.slaBreachesAt
        if breach_dt:
            hours_left = (breach_dt - now).total_seconds() / 3600
            time_str = f"{hours_left:.1f}h" if hours_left < 24 else f"{hours_left / 24:.1f}d"
        else:
            time_str = "N/A"
        at_risk_rows.append(
            [
                i.identifier,
                f"{PRIORITY_ICONS[i.priority]} {PRIORITY_MAP[i.priority]}",
                i.state.name,
                time_str,
                i.title[:60],
            ]
        )

    prompt = build_prompt(
        findings=[
            f"Due Date Usage (Metric, Count, Pct): With dueDate={len(with_due)} ({due_rows[0][2]}), Without dueDate={len(without_due)}.",
            f"Response Time by Priority (Priority, Mean, P50, P90, P95, n): automation within 1 min is {automation_pct:.1f}% of started issues.",
            f"Lead Time by Priority (Priority, Mean, P50, P90, P95, n): completed window size is {len(completed)}.",
            "SLA Target Check (Priority, Hit, Rate, Target): P1/P2 hit rates are listed in SLA Target table.",
            f"Open SLA Risk (ID, Priority, State, Time): breached={len(breached)} and at_risk={len(at_risk)}.",
        ],
        recommendations=[
            "Increase Due Date usage if it is below 50% to improve SLA tracking consistency.",
            "Target P1<=3d and P2<=7d hit rates above 80%; use SLA Target table to pick gaps.",
            f"Clear open SLA breaches (count={len(breached)}) and reduce at-risk items (count={len(at_risk)}).",
        ],
        next_checks=[
            "Run flow.py to confirm queue vs execution contribution to lead time.",
            "Run wip.py to identify stale WIP that may drive SLA misses.",
            "List open SLA items in hunt.py with filter p1_breached or p2_breached.",
        ],
    )

    emit_prompt(prompt)
    emit_csv("due_date_usage", ["Metric", "Count", "Pct"], due_rows)
    emit_csv("due_date_estimate_bias", ["Group", "AvgEstimate"], bias_rows)
    emit_csv("response_time_by_priority", ["Priority", "Mean", "P50", "P90", "P95", "n"], response_rows)
    emit_csv("lead_time_by_priority", ["Priority", "Mean", "P50", "P90", "P95", "n"], lead_rows)
    emit_csv("sla_target_hit", ["Priority", "Hit", "Rate", "Target"], target_rows)
    emit_csv("sla_open_breached", ["ID", "Priority", "State", "BreachedAt", "Title"], breached_rows)
    emit_csv("sla_open_at_risk", ["ID", "Priority", "State", "TimeLeft", "Title"], at_risk_rows)
    emit_csv(
        "automation_check",
        ["Metric", "Value"],
        [["Started within 1 min", f"{automation_pct:.1f}%"]],
    )
    end()


if __name__ == "__main__":
    from cli import parse_team_args  # type: ignore[attr-defined]

    args = parse_team_args("Analyze SLA performance")
    analyze_sla(args.team_key, args.since, debug=args.debug)
