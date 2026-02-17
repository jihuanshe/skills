from __future__ import annotations

from collections.abc import Callable
from typing import Any

from linear_client import run_query
from models import Issue, Project
from tool_io import log


def _paginate(
    query: str,
    variables: dict[str, Any],
    extract_connection: Callable[[dict], dict],
    *,
    query_name: str,
    debug: bool = False,
) -> list[dict]:
    all_nodes: list[dict] = []
    has_next = True
    cursor = None
    page = 0
    while has_next:
        vars_with_cursor = {**variables, "after": cursor}
        data = run_query(query, variables=vars_with_cursor, query_name=query_name, debug=debug)
        connection = extract_connection(data.get("data", {}))
        nodes = connection.get("nodes", [])
        all_nodes.extend(nodes)
        page_info = connection.get("pageInfo", {})
        has_next = page_info.get("hasNextPage", False)
        cursor = page_info.get("endCursor")
        page += 1
        if debug:
            log(f"[selection] {query_name} page={page} nodes={len(nodes)}")
    return all_nodes


def _query_issues(
    query: str,
    variables: dict[str, Any],
    *,
    query_name: str,
    debug: bool = False,
) -> list[Issue]:
    nodes = _paginate(query, variables, lambda d: d.get("issues", {}), query_name=query_name, debug=debug)
    return [Issue.model_validate(n) for n in nodes]


CREATED_QUERY = """
query IssuesCreated($teamKey: String!, $since: DateTimeOrDuration!, $after: String) {
    issues(
        filter: {
            team: { key: { eq: $teamKey } }
            createdAt: { gte: $since }
        }
        first: 100
        after: $after
    ) {
        nodes {
            id identifier title url createdAt startedAt completedAt canceledAt
            dueDate estimate priority slaBreachesAt slaStartedAt
            state { name type }
            assignee { name }
            labels { nodes { name } }
            project { id name state startDate targetDate }
            projectMilestone { name targetDate }
            cycle { name number startsAt endsAt }
            parent { identifier }
        }
        pageInfo { hasNextPage endCursor }
    }
}
"""


def issues_created_since(team_key: str, since: str, *, debug: bool = False) -> list[Issue]:
    return _query_issues(
        CREATED_QUERY,
        {"teamKey": team_key, "since": since},
        query_name="issues_created_since",
        debug=debug,
    )


COMPLETED_QUERY = """
query IssuesCompleted($teamKey: String!, $since: DateTimeOrDuration!, $after: String) {
    issues(
        filter: {
            team: { key: { eq: $teamKey } }
            completedAt: { gte: $since }
            state: { type: { eq: "completed" } }
        }
        first: 100
        after: $after
    ) {
        nodes {
            id identifier title url createdAt startedAt completedAt canceledAt
            dueDate estimate priority slaBreachesAt slaStartedAt
            state { name type }
            assignee { name }
            labels { nodes { name } }
            project { id name state startDate targetDate }
            projectMilestone { name targetDate }
            cycle { name number startsAt endsAt }
            parent { identifier }
        }
        pageInfo { hasNextPage endCursor }
    }
}
"""


def issues_completed_since(team_key: str, since: str, *, debug: bool = False) -> list[Issue]:
    return _query_issues(
        COMPLETED_QUERY,
        {"teamKey": team_key, "since": since},
        query_name="issues_completed_since",
        debug=debug,
    )


CANCELED_QUERY = """
query IssuesCanceled($teamKey: String!, $since: DateTimeOrDuration!, $after: String) {
    issues(
        filter: {
            team: { key: { eq: $teamKey } }
            canceledAt: { gte: $since }
            state: { type: { eq: "canceled" } }
        }
        first: 100
        after: $after
    ) {
        nodes {
            id identifier title url createdAt startedAt completedAt canceledAt
            dueDate estimate priority slaBreachesAt slaStartedAt
            state { name type }
            assignee { name }
            labels { nodes { name } }
            project { id name state startDate targetDate }
            projectMilestone { name targetDate }
            cycle { name number startsAt endsAt }
            parent { identifier }
        }
        pageInfo { hasNextPage endCursor }
    }
}
"""


def issues_canceled_since(team_key: str, since: str, *, debug: bool = False) -> list[Issue]:
    return _query_issues(
        CANCELED_QUERY,
        {"teamKey": team_key, "since": since},
        query_name="issues_canceled_since",
        debug=debug,
    )


WIP_QUERY = """
query IssuesWIP($teamKey: String!, $after: String) {
    issues(
        filter: {
            team: { key: { eq: $teamKey } }
            state: { type: { eq: "started" } }
        }
        first: 100
        after: $after
    ) {
        nodes {
            id identifier title url createdAt startedAt completedAt canceledAt
            dueDate estimate priority slaBreachesAt slaStartedAt
            state { name type }
            assignee { name }
            labels { nodes { name } }
            project { id name state startDate targetDate }
            projectMilestone { name targetDate }
            cycle { name number startsAt endsAt }
            parent { identifier }
        }
        pageInfo { hasNextPage endCursor }
    }
}
"""


def wip_started_snapshot(team_key: str, *, debug: bool = False) -> list[Issue]:
    return _query_issues(WIP_QUERY, {"teamKey": team_key}, query_name="wip_started_snapshot", debug=debug)


OPEN_QUERY = """
query IssuesOpen($teamKey: String!, $after: String) {
    issues(
        filter: {
            team: { key: { eq: $teamKey } }
            state: { type: { nin: ["completed", "canceled"] } }
        }
        first: 100
        after: $after
    ) {
        nodes {
            id identifier title url createdAt startedAt completedAt canceledAt
            dueDate estimate priority slaBreachesAt slaStartedAt
            state { name type }
            assignee { name }
            labels { nodes { name } }
            project { id name state startDate targetDate }
            projectMilestone { name targetDate }
            cycle { name number startsAt endsAt }
            parent { identifier }
        }
        pageInfo { hasNextPage endCursor }
    }
}
"""


def _open_issues_snapshot(team_key: str, *, debug: bool = False) -> list[Issue]:
    return _query_issues(OPEN_QUERY, {"teamKey": team_key}, query_name="open_issues_snapshot", debug=debug)


PROJECTS_QUERY = """
query ProjectsForTeam($teamKey: String!, $after: String) {
    projects(
        first: 50
        after: $after
        filter: {
            state: { nin: ["canceled"] }
            accessibleTeams: { some: { key: { eq: $teamKey } } }
        }
    ) {
        nodes {
            id name progress state startDate targetDate completedAt
            description health
            lead { name }
            teams { nodes { key } }
            projectMilestones { nodes { name description targetDate sortOrder } }
            projectUpdates(first: 1) { nodes { body health createdAt user { name } } }
        }
        pageInfo { hasNextPage endCursor }
    }
}
"""


def projects_for_team(team_key: str, *, debug: bool = False) -> list[Project]:
    nodes = _paginate(
        PROJECTS_QUERY,
        {"teamKey": team_key},
        lambda d: d.get("projects", {}),
        query_name="projects_for_team",
        debug=debug,
    )
    return [Project.model_validate(p) for p in nodes]


PROJECT_ISSUES_QUERY = """
query ProjectIssues($projectId: String!, $after: String) {
    project(id: $projectId) {
        issues(first: 100, after: $after) {
            nodes {
                id identifier title url createdAt startedAt completedAt canceledAt
                dueDate estimate priority slaBreachesAt slaStartedAt
                state { name type }
                assignee { name }
                labels { nodes { name } }
                project { id name state startDate targetDate }
                projectMilestone { name targetDate }
                cycle { name number startsAt endsAt }
                parent { identifier }
            }
            pageInfo { hasNextPage endCursor }
        }
    }
}
"""


def issues_for_project(project_id: str, *, debug: bool = False) -> list[Issue]:
    all_issues: list[Issue] = []
    has_next = True
    cursor = None
    page = 0

    while has_next:
        data = run_query(
            PROJECT_ISSUES_QUERY,
            variables={"projectId": project_id, "after": cursor},
            query_name="issues_for_project",
            debug=debug,
        )
        project_data = data.get("data", {}).get("project")
        if project_data is None:
            if debug:
                log(f"[selection] issues_for_project project_id={project_id} not found")
            break
        issues_data = project_data.get("issues", {})
        nodes = issues_data.get("nodes", [])
        all_issues.extend(Issue.model_validate(n) for n in nodes)
        page_info = issues_data.get("pageInfo", {})
        has_next = page_info.get("hasNextPage", False)
        cursor = page_info.get("endCursor")
        page += 1
        if debug:
            log(f"[selection] issues_for_project page={page} nodes={len(nodes)}")

    return all_issues


def open_issues_with_sla(team_key: str, *, debug: bool = False) -> list[Issue]:
    return [i for i in _open_issues_snapshot(team_key, debug=debug) if i.slaBreachesAt]
