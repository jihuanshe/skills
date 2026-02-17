from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from models import Issue, get_default_since_date
from selection import issues_completed_since, open_issues_with_sla, wip_started_snapshot

SourceFn = Callable[[str, str | None, bool], list[Issue]]
Predicate = Callable[[Issue], bool]


@dataclass(frozen=True)
class FilterSpec:
    name: str
    description: str
    source: SourceFn
    predicate: Predicate
    default_limit: int = 50

    def apply(self, team_key: str, since: str | None, *, debug: bool = False) -> list[Issue]:
        issues = self.source(team_key, since, debug)
        return [i for i in issues if self.predicate(i)]


def _source_wip(team_key: str, since: str | None, debug: bool) -> list[Issue]:
    return wip_started_snapshot(team_key, debug=debug)


def _source_open_sla(team_key: str, since: str | None, debug: bool) -> list[Issue]:
    return open_issues_with_sla(team_key, debug=debug)


def _source_completed(team_key: str, since: str | None, debug: bool) -> list[Issue]:
    effective_since = since or get_default_since_date()
    return issues_completed_since(team_key, effective_since, debug=debug)


FILTERS: dict[str, FilterSpec] = {
    "stale_wip": FilterSpec(
        name="stale_wip",
        description="WIP items with age > 14 days.",
        source=_source_wip,
        predicate=lambda i: bool(i.wip_age_days and i.wip_age_days > 14),
        default_limit=50,
    ),
    "p1_breached": FilterSpec(
        name="p1_breached",
        description="Open SLA items with priority P1 that are already breached.",
        source=_source_open_sla,
        predicate=lambda i: i.priority == 1 and i.is_sla_breached,
        default_limit=50,
    ),
    "p2_breached": FilterSpec(
        name="p2_breached",
        description="Open SLA items with priority P2 that are already breached.",
        source=_source_open_sla,
        predicate=lambda i: i.priority == 2 and i.is_sla_breached,
        default_limit=50,
    ),
    "p1_at_risk": FilterSpec(
        name="p1_at_risk",
        description="Open SLA items with priority P1 that are at risk.",
        source=_source_open_sla,
        predicate=lambda i: i.priority == 1 and i.is_sla_at_risk,
        default_limit=50,
    ),
    "recently_completed_bugs": FilterSpec(
        name="recently_completed_bugs",
        description="Completed bugs since the given date.",
        source=_source_completed,
        predicate=lambda i: i.work_type == "Bug",
        default_limit=100,
    ),
}
