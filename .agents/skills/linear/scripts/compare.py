#!/usr/bin/env -S mise x -E local -- uv run --script
# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = ["pydantic>=2.10", "httpx>=0.28"]
# ///

from __future__ import annotations

from datetime import UTC, datetime

from models import PRIORITY_MAP, get_default_since_date, percentile
from selection import issues_completed_since, issues_created_since
from tool_io import emit_csv, emit_meta, emit_prompt, end, log
from tool_prompts import build_prompt


def compare_teams(team_keys: list[str], since_date: str | None = None, *, debug: bool = False) -> None:
    since = since_date or get_default_since_date()
    now = datetime.now(UTC)

    created_by_team: dict[str, list] = {}
    completed_by_team: dict[str, list] = {}

    for tk in team_keys:
        log(f"Fetching created cohort for {tk} since {since}...")
        created_by_team[tk] = issues_created_since(tk, since, debug=debug)
        log(f"Fetching completed window for {tk} since {since}...")
        completed_by_team[tk] = issues_completed_since(tk, since, debug=debug)

    emit_meta(
        {
            "tool": "compare",
            "teams": ",".join(team_keys),
            "since": since,
            "generated_at": now.isoformat(),
            "selection": "cohort=createdAt>=since; completed=completedAt>=since",
        }
    )

    # Cohort basic metrics
    cohort_basic_rows = []
    for tk in team_keys:
        issues = created_by_team[tk]
        total = len(issues)
        done = sum(1 for i in issues if i.is_completed)
        cancel = sum(1 for i in issues if i.is_canceled)
        wip = sum(1 for i in issues if i.is_wip)
        rate = done / total * 100 if total > 0 else 0
        cohort_basic_rows.append([tk, total, done, f"{rate:.1f}%", cancel, wip])

    # Cohort structure metrics
    cohort_structure_rows = []
    for tk in team_keys:
        issues = created_by_team[tk]
        if issues:
            n = len(issues)
            sub = sum(1 for i in issues if i.parent)
            no_est = sum(1 for i in issues if i.estimate is None)
            no_proj = sum(1 for i in issues if not i.project)
            cohort_structure_rows.append(
                [
                    tk,
                    f"{sub / n * 100:.1f}%",
                    f"{no_est / n * 100:.1f}%",
                    f"{no_proj / n * 100:.1f}%",
                ]
            )

    # Completed lead time
    completed_lead_rows = []
    for tk in team_keys:
        completed = completed_by_team[tk]
        lts = [i.lead_time_days for i in completed if i.lead_time_days is not None]
        if lts:
            mean = sum(lts) / len(lts)
            completed_lead_rows.append(
                [
                    tk,
                    f"{mean:.1f}d",
                    f"{percentile(lts, 50):.0f}d",
                    f"{percentile(lts, 75):.0f}d",
                    f"{percentile(lts, 90):.0f}d",
                    f"{percentile(lts, 95):.0f}d",
                ]
            )
        else:
            completed_lead_rows.append([tk, "N/A", "N/A", "N/A", "N/A", "N/A"])

    # Completed SLA (P1/P2 target check)
    completed_sla_rows = []
    sla_targets = {1: 3, 2: 7}
    for tk in team_keys:
        completed = completed_by_team[tk]
        for pri, target in sla_targets.items():
            pri_completed = [i for i in completed if i.priority == pri]
            times = [i.lead_time_days for i in pri_completed if i.lead_time_days is not None]
            if times:
                hit = sum(1 for t in times if t <= target)
                hit_rate = hit / len(times) * 100
                completed_sla_rows.append(
                    [
                        tk,
                        f"P{pri} {PRIORITY_MAP[pri]}",
                        f"{hit}/{len(times)}",
                        f"{hit_rate:.1f}%",
                        f"{target}d",
                    ]
                )
            else:
                completed_sla_rows.append([tk, f"P{pri} {PRIORITY_MAP[pri]}", "N/A", "N/A", f"{target}d"])

    prompt = build_prompt(
        findings=[
            "Cohort Basic (Team, Total, Done, Rate, Cancel, WIP): compare counts only within created cohort.",
            "Cohort Structure (Team, Sub-issue%, No-estimate%, No-project%): use for process hygiene comparisons.",
            "Completed Lead Time (Team, Mean, P50, P75, P90, P95): windowed by completedAt>=since.",
            "Completed SLA (Team, Priority, Hit, Rate, Target): P1/P2 hit rates by team.",
        ],
        recommendations=[
            "Use Cohort Structure to drive estimation/project hygiene; target No-estimate% < 20% and No-project% < 20%.",
            "Compare lead-time percentiles only across the Completed Lead Time table to avoid cohort bias.",
            "Use Completed SLA to align on shared P1/P2 targets and improvement goals.",
        ],
        next_checks=[
            "Run flow.py for each team to see Queue% vs Exec% differences.",
            "Run wip.py for each team to compare WIP aging and throughput balance.",
            "Use hunt.py filters to list breached or stale items for targeted follow-up.",
        ],
    )

    emit_prompt(prompt)
    emit_csv("cohort_basic", ["Team", "Total", "Done", "Rate", "Cancel", "WIP"], cohort_basic_rows)
    emit_csv("cohort_structure", ["Team", "Sub-issue%", "No-estimate%", "No-project%"], cohort_structure_rows)
    emit_csv("completed_lead_time", ["Team", "Mean", "P50", "P75", "P90", "P95"], completed_lead_rows)
    emit_csv("completed_sla", ["Team", "Priority", "Hit", "Rate", "Target"], completed_sla_rows)
    end()


if __name__ == "__main__":
    from cli import parse_compare_args  # type: ignore[attr-defined]

    args = parse_compare_args("Compare efficiency metrics between teams")
    compare_teams(args.team_keys, args.since, debug=args.debug)
