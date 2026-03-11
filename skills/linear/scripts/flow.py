#!/usr/bin/env -S mise x -E local -- uv run --script
# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = ["pydantic>=2.10", "httpx>=0.28"]
# ///

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime

from models import PRIORITY_ICONS, PRIORITY_MAP, cycle_sort_key, get_default_since_date, percentile
from selection import issues_completed_since
from tool_io import emit_csv, emit_meta, emit_prompt, end, log
from tool_prompts import build_prompt


def analyze_lead_time(team_key: str, since_date: str | None = None, *, debug: bool = False) -> None:
    since = since_date or get_default_since_date()
    now = datetime.now(UTC)

    log(f"Fetching completed issues for {team_key} since {since}...")
    completed_all = issues_completed_since(team_key, since, debug=debug)
    completed = [i for i in completed_all if i.startedAt]

    queue_times = [i.queue_time_days for i in completed if i.queue_time_days is not None]
    exec_times = [i.cycle_time_days for i in completed if i.cycle_time_days is not None]
    lead_times = [i.lead_time_days for i in completed if i.lead_time_days is not None]

    # Automation detection (started within 1 minute)
    started = [i for i in completed_all if i.startedAt]
    instant = sum(1 for i in started if (rs := i.response_seconds) is not None and rs < 60)
    automation_pct = instant / len(started) * 100 if started else 0
    cycle_unreliable = automation_pct > 50

    emit_meta(
        {
            "tool": "flow",
            "team": team_key,
            "since": since,
            "generated_at": now.isoformat(),
            "selection": "completedAt>=since with startedAt",
            "completed_total": len(completed_all),
            "completed_with_started": len(completed),
            "started_at_automation_pct": f"{automation_pct:.1f}",
            "cycle_time_unreliable": cycle_unreliable,
        }
    )

    overall_rows = []
    if queue_times:
        mean = sum(queue_times) / len(queue_times)
        overall_rows.append(
            [
                "Queue Time (C->S)",
                f"{mean:.1f}d",
                f"{percentile(queue_times, 50):.0f}d",
                f"{percentile(queue_times, 75):.0f}d",
                f"{percentile(queue_times, 90):.0f}d",
                f"{percentile(queue_times, 95):.0f}d",
            ]
        )
    if exec_times:
        mean = sum(exec_times) / len(exec_times)
        overall_rows.append(
            [
                "Execution Time (S->C)",
                f"{mean:.1f}d",
                f"{percentile(exec_times, 50):.0f}d",
                f"{percentile(exec_times, 75):.0f}d",
                f"{percentile(exec_times, 90):.0f}d",
                f"{percentile(exec_times, 95):.0f}d",
            ]
        )
    if lead_times:
        mean = sum(lead_times) / len(lead_times)
        overall_rows.append(
            [
                "Lead Time (C->C)",
                f"{mean:.1f}d",
                f"{percentile(lead_times, 50):.0f}d",
                f"{percentile(lead_times, 75):.0f}d",
                f"{percentile(lead_times, 90):.0f}d",
                f"{percentile(lead_times, 95):.0f}d",
            ]
        )

    queue_pct = 0.0
    if queue_times and lead_times:
        avg_queue = sum(queue_times) / len(queue_times)
        avg_lead = sum(lead_times) / len(lead_times)
        queue_pct = avg_queue / avg_lead * 100 if avg_lead > 0 else 0

    priority_rows = []
    for pri in [1, 2, 3, 4]:
        pri_issues = [i for i in completed if i.priority == pri]
        if len(pri_issues) >= 3:
            qts = [i.queue_time_days for i in pri_issues if i.queue_time_days is not None]
            ets = [i.cycle_time_days for i in pri_issues if i.cycle_time_days is not None]
            if qts and ets:
                avg_q, avg_e = sum(qts) / len(qts), sum(ets) / len(ets)
                total = avg_q + avg_e
                q_pct = avg_q / total * 100 if total > 0 else 0
                priority_rows.append(
                    [
                        f"{PRIORITY_ICONS[pri]} {PRIORITY_MAP[pri]}",
                        f"{avg_q:.1f}d",
                        f"{avg_e:.1f}d",
                        f"{total:.1f}d",
                        f"{q_pct:.0f}%",
                        len(pri_issues),
                    ]
                )

    work_rows = []
    for wtype in ["Bug", "Feature", "Improvement", "Other"]:
        type_issues = [i for i in completed if i.work_type == wtype]
        if len(type_issues) >= 3:
            qts = [i.queue_time_days for i in type_issues if i.queue_time_days is not None]
            ets = [i.cycle_time_days for i in type_issues if i.cycle_time_days is not None]
            if qts and ets:
                avg_q, avg_e = sum(qts) / len(qts), sum(ets) / len(ets)
                total = avg_q + avg_e
                q_pct = avg_q / total * 100 if total > 0 else 0
                work_rows.append(
                    [wtype, f"{avg_q:.1f}d", f"{avg_e:.1f}d", f"{total:.1f}d", f"{q_pct:.0f}%", len(type_issues)]
                )

    cycle_issues: dict[int | None, list] = defaultdict(list)
    for i in completed:
        cycle_issues[i.cycle_number].append(i)

    cycle_rows = []
    for num in sorted(cycle_issues.keys(), key=cycle_sort_key):
        issues_in_cycle = cycle_issues[num]
        if len(issues_in_cycle) >= 3:
            qts = [i.queue_time_days for i in issues_in_cycle if i.queue_time_days is not None]
            ets = [i.cycle_time_days for i in issues_in_cycle if i.cycle_time_days is not None]
            if qts and ets:
                avg_q, avg_e = sum(qts) / len(qts), sum(ets) / len(ets)
                total = avg_q + avg_e
                q_pct = avg_q / total * 100 if total > 0 else 0
                cycle_name = f"Cycle {num}" if num is not None else "(No cycle)"
                cycle_rows.append(
                    [
                        cycle_name,
                        f"{avg_q:.1f}d",
                        f"{avg_e:.1f}d",
                        f"{total:.1f}d",
                        f"{q_pct:.0f}%",
                        len(issues_in_cycle),
                    ]
                )

    bottleneck = "QUEUE" if queue_pct > 50 else "EXECUTION"

    prompt = build_prompt(
        findings=[
            f"Overall Breakdown (Metric, Mean, P50, P75, P90, P95): queue share is {queue_pct:.1f}% (bottleneck={bottleneck}).",
            "Breakdown by Priority (Priority, Queue, Exec, Total, Queue%, n): review rows for high Queue%.",
            "Breakdown by Work Type (Type, Queue, Exec, Total, Queue%, n): compare Bug vs Feature mix.",
            "Breakdown by Cycle (Cycle, Queue, Exec, Total, Queue%, n): check cycles with high Queue%.",
            f"Automation check: started within 1 minute is {automation_pct:.1f}% (cycle_time_unreliable={cycle_unreliable}).",
        ],
        recommendations=[
            "If Queue% > 50%, tighten intake and limit WIP to reduce wait time.",
            "If Execution% dominates, split large work items and reduce blockers.",
            "If cycle time automation is high, rely on Lead Time over Cycle Time.",
        ],
        next_checks=[
            "Run wip.py to correlate Queue% with WIP load.",
            "Run sla.py to link queue delays to SLA misses.",
            "Run compare.py to benchmark priority lead times across teams.",
        ],
    )

    emit_prompt(prompt)
    emit_csv("overall_breakdown", ["Metric", "Mean", "P50", "P75", "P90", "P95"], overall_rows)
    emit_csv("by_priority", ["Priority", "Queue", "Exec", "Total", "Queue%", "n"], priority_rows)
    emit_csv("by_work_type", ["Type", "Queue", "Exec", "Total", "Queue%", "n"], work_rows)
    emit_csv("by_cycle", ["Cycle", "Queue", "Exec", "Total", "Queue%", "n"], cycle_rows)
    end()


if __name__ == "__main__":
    from cli import parse_team_args  # type: ignore[attr-defined]

    args = parse_team_args("Analyze lead time flow efficiency")
    analyze_lead_time(args.team_key, args.since, debug=args.debug)
