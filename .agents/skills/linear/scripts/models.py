"""Pydantic models and metrics for Linear analysis."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from pydantic import AliasPath, BaseModel, BeforeValidator, Field


def _parse_datetime(value: Any) -> datetime | None:
    """Validator for datetime fields from GraphQL (ISO8601 strings or already parsed)."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)
        except ValueError:
            try:
                return datetime.strptime(value[:10], "%Y-%m-%d").replace(tzinfo=UTC)
            except ValueError:
                return None
    return None


DateTime = Annotated[datetime | None, BeforeValidator(_parse_datetime)]


class State(BaseModel):
    name: str = ""
    type: str = ""


class Assignee(BaseModel):
    name: str = ""


class Label(BaseModel):
    name: str


class TeamRef(BaseModel):
    key: str


class ProjectRef(BaseModel):
    id: str | None = None
    name: str
    state: str = ""
    startDate: DateTime = None
    targetDate: DateTime = None


class ProjectMilestoneRef(BaseModel):
    name: str
    targetDate: DateTime = None


class CycleRef(BaseModel):
    name: str | None = None
    number: int = 0
    startsAt: DateTime = None
    endsAt: DateTime = None


class Parent(BaseModel):
    identifier: str


class Issue(BaseModel):
    id: str | None = None
    identifier: str
    title: str = ""
    url: str = ""
    createdAt: DateTime
    startedAt: DateTime = None
    completedAt: DateTime = None
    canceledAt: DateTime = None
    dueDate: DateTime = None
    estimate: int | None = None
    priority: int = 0
    state: State = Field(default_factory=State)
    assignee: Assignee | None = None
    labels: list[Label] = Field(default_factory=list, validation_alias=AliasPath("labels", "nodes"))
    project: ProjectRef | None = None
    projectMilestone: ProjectMilestoneRef | None = None
    cycle: CycleRef | None = None
    parent: Parent | None = None
    slaBreachesAt: DateTime = None
    slaStartedAt: DateTime = None

    @property
    def assignee_name(self) -> str:
        return self.assignee.name if self.assignee else "Unassigned"

    @property
    def state_type(self) -> str:
        return self.state.type

    @property
    def label_names(self) -> frozenset[str]:
        return frozenset(lbl.name for lbl in self.labels)

    @property
    def work_type(self) -> str:
        names = self.label_names
        if "Bug" in names:
            return "Bug"
        if "Feature" in names:
            return "Feature"
        if "Improvement" in names:
            return "Improvement"
        return "Other"

    @property
    def lead_time_days(self) -> float | None:
        if self.createdAt and self.completedAt:
            return (self.completedAt - self.createdAt).total_seconds() / 86400
        return None

    @property
    def cycle_time_days(self) -> float | None:
        if self.startedAt and self.completedAt:
            return (self.completedAt - self.startedAt).total_seconds() / 86400
        return None

    @property
    def queue_time_days(self) -> float | None:
        if self.createdAt and self.startedAt:
            return (self.startedAt - self.createdAt).total_seconds() / 86400
        return None

    @property
    def response_seconds(self) -> float | None:
        if self.createdAt and self.startedAt:
            return (self.startedAt - self.createdAt).total_seconds()
        return None

    @property
    def wip_age_days(self) -> float | None:
        if self.is_wip and self.startedAt:
            return (datetime.now(UTC) - self.startedAt).total_seconds() / 86400
        return None

    @property
    def is_completed(self) -> bool:
        return self.state_type == "completed"

    @property
    def is_canceled(self) -> bool:
        return self.state_type == "canceled"

    @property
    def is_wip(self) -> bool:
        return self.state_type == "started"

    @property
    def is_high_priority(self) -> bool:
        return self.priority in [1, 2]

    @property
    def is_sla_breached(self) -> bool:
        deadline = self.slaBreachesAt
        if not deadline:
            return False
        if self.is_completed and self.completedAt:
            return self.completedAt > deadline
        if self.is_canceled:
            return False
        return datetime.now(UTC) > deadline

    @property
    def is_sla_at_risk(self) -> bool:
        deadline = self.slaBreachesAt
        if not deadline:
            return False
        if self.is_completed or self.is_canceled:
            return False
        now = datetime.now(UTC)
        return now < deadline <= now + timedelta(hours=24)

    @property
    def milestone_name(self) -> str | None:
        return self.projectMilestone.name if self.projectMilestone else None

    @property
    def cycle_number(self) -> int | None:
        return self.cycle.number if self.cycle else None


class ProjectMilestone(BaseModel):
    name: str
    description: str | None = None
    targetDate: DateTime = None
    sortOrder: float = 0


class ProjectUpdate(BaseModel):
    body: str = ""
    health: str = ""
    createdAt: DateTime = None
    user: Assignee | None = None


class Project(BaseModel):
    id: str | None = None
    name: str
    progress: float = 0
    state: str = ""
    startDate: DateTime = None
    targetDate: DateTime = None
    completedAt: DateTime = None
    lead: Assignee | None = None
    teams: list[TeamRef] = Field(default_factory=list, validation_alias=AliasPath("teams", "nodes"))
    description: str = ""
    content: str | None = None
    health: str | None = None
    healthUpdatedAt: DateTime = None
    milestones: list[ProjectMilestone] = Field(
        default_factory=list, validation_alias=AliasPath("projectMilestones", "nodes")
    )
    updates: list[ProjectUpdate] = Field(default_factory=list, validation_alias=AliasPath("projectUpdates", "nodes"))

    @property
    def latest_update(self) -> ProjectUpdate | None:
        return self.updates[0] if self.updates else None

    def has_team(self, team_key: str) -> bool:
        return any(t.key == team_key for t in self.teams)


def get_iso_week(date: datetime | None) -> str | None:
    if date:
        return f"{date.isocalendar()[0]}-W{date.isocalendar()[1]:02d}"
    return None


def percentile(data: list[float | int], p: float) -> float:
    if not data:
        return 0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * p / 100
    floor_idx = int(k)
    ceil_idx = min(floor_idx + 1, len(sorted_data) - 1)
    if floor_idx == ceil_idx:
        return sorted_data[floor_idx]
    return sorted_data[floor_idx] + (sorted_data[ceil_idx] - sorted_data[floor_idx]) * (k - floor_idx)


def get_default_since_date(days: int = 90) -> str:
    return (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%d")


def cycle_sort_key(n: int | None) -> tuple[int, int]:
    return (1 if n is None else 0, -(n or 0))


PRIORITY_MAP = {0: "None", 1: "Urgent", 2: "High", 3: "Normal", 4: "Low"}
PRIORITY_ICONS = {0: "P0", 1: "P1", 2: "P2", 3: "P3", 4: "P4"}
