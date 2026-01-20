---
name: linear
description: 'Query and manage Linear issues. Triggers: linear issue, team metrics, WIP.'
metadata:
  version: '1'
---

# Using Linear

Complete Linear workflow: daily issue management via CLI + deep team efficiency analysis.

## Prerequisites

```bash
linear --version    # Check CLI installed
linear auth whoami  # Check authenticated
```

If not installed: <https://github.com/schpet/linear-cli>

## ⚠️ Critical Data Caveats

Before running any analysis, understand these key constraints:

### 1. Selection Semantics (Cohort vs Window vs Snapshot)

Scripts now use explicit selection functions. Always read the `@selection` meta line:

- **createdAt >= since**: cohort view (process hygiene, structure)
- **completedAt >= since**: completion window (throughput/lead time)
- **snapshot**: current state (WIP, open SLA risk)

Do not compare metrics across different selections.

### 2. Time Precision

Scripts now use **float days** (e.g., `2.5d`) instead of integer days. This fixes:

- SLA calculations (previously `23h` was counted as `0d`)
- Queue/Cycle time analysis

### 3. startedAt Automation

Many teams auto-set `startedAt` on creation. Check the automation detection output:

- If **>50% issues have startedAt within 1 minute** → Cycle Time data is unreliable
- Lead Time (created→completed) remains valid

## Quick Start (Runbook)

```bash
# List teams
linear team list

# Team overview (last 90 days)
scripts/overview.py <TEAM_KEY>

# Compare teams (--since is optional)
scripts/compare.py AI INF --since 2025-10-01

# Deep dives (--since is optional, defaults to 90 days ago)
scripts/projects.py <TEAM_KEY> --since <YYYY-MM-DD>
scripts/workload.py <TEAM_KEY> --since <YYYY-MM-DD>
scripts/wip.py <TEAM_KEY> --since <YYYY-MM-DD>
scripts/sla.py <TEAM_KEY> --since <YYYY-MM-DD>
scripts/flow.py <TEAM_KEY> --since <YYYY-MM-DD>
scripts/forecast.py <TEAM_KEY> --since <YYYY-MM-DD>

# Targeted issue list
scripts/hunt.py <TEAM_KEY> --filter stale_wip --limit 50
```

## Tool Output Contract (stdout/stderr)

All tools must emit **only** the structured contract to stdout:

```text
@key: value
===PROMPT===
...
===CSV:<name>===
col1,col2,...
...
===END===
```

- **stdout**: contract only (PROMPT + one or more CSV tables + END)
- **stderr**: logs, progress, debug output
- Validate locally: `mise exec -- uv run scripts/validate_output.py < output.txt`
- Use `-debug` to log query names, variables, and pagination to **stderr** only

## Part 1: Daily CLI Usage

### Available Commands

```bash
linear issue      # list, view, create, start, update, delete, comment
linear team       # list, members, create, autolinks
linear project    # list, view
linear config     # Configure CLI for current repo
linear auth       # token, whoami
linear schema     # Print GraphQL schema
```

### Discovering Options

```bash
linear --help
linear issue --help
linear issue list --help
```

### Common Issue Operations

```bash
# View issue details
linear issue view <issue-id>

# Add comment (note: requires `add` subcommand)
linear issue comment add <issue-id> --body "Comment content"

# Update issue state
linear issue update <issue-id> --state "Canceled"   # Cancel
linear issue update <issue-id> --state "Done"       # Complete
linear issue update <issue-id> --state "Duplicate"  # Mark as duplicate
linear issue update <issue-id> --state "In Progress"

# Update other fields
linear issue update <issue-id> --assignee self
linear issue update <issue-id> --priority 1
linear issue update <issue-id> --label "Bug"

# List available workflow states for a team
curl -s -X POST https://api.linear.app/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: $(linear auth token)" \
  -d '{"query": "{ workflowStates(filter: {team: {key: {eq: \"TEAM_KEY\"}}}) { nodes { name type } } }"}' \
  | jq '.data.workflowStates.nodes'
```

## Part 2: GraphQL API (Escape Hatch)

### ⛔ MANDATORY: Pagination is Required

**NEVER** use `first: 250` or any large number without pagination. This will truncate data silently.

**Always** implement pagination with `hasNextPage` and `endCursor`:

```graphql
{
  issues(filter: {...}, first: 100) {
    nodes { ... }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
```

**Recommended**: Use Python selection helpers instead of raw GraphQL:

```python
from selection import issues_created_since
issues = issues_created_since("AI", "2025-10-01")
```

### Schema Discovery

```bash
# Write schema to tempfile
linear schema -o "${TMPDIR:-/tmp}/linear-schema.graphql"

# Search schema
rg -A30 "^type Issue " "${TMPDIR:-/tmp}/linear-schema.graphql"
rg -A50 "^input IssueFilter" "${TMPDIR:-/tmp}/linear-schema.graphql"
```

### Direct API Call (Long-tail Queries)

For ad-hoc queries not covered by scripts, use curl directly.

**Base pattern:**

```bash
curl -s -X POST https://api.linear.app/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: $(linear auth token)" \
  -d '{"query": "YOUR_QUERY_HERE"}' | jq .
```

**Handling timestamps with milliseconds (jq fix):**

Linear timestamps may include milliseconds (e.g., `2026-01-08T08:53:59.922Z`):

```bash
curl -s -X POST https://api.linear.app/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: $(linear auth token)" \
  -d '{"query": "{ issues(filter: {team: {key: {eq: \"AI\"}}}, first: 10) { nodes { identifier createdAt completedAt } } }"}' \
  | jq '.data.issues.nodes[] | {
      id: .identifier,
      created: (.createdAt | sub("\\.[0-9]+Z$"; "Z") | fromdateiso8601),
      completed: (.completedAt // null | if . then sub("\\.[0-9]+Z$"; "Z") | fromdateiso8601 else null end)
    }'
```

### Common Long-tail Query Templates

**Count issues by state type:**

```bash
curl -s -X POST https://api.linear.app/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: $(linear auth token)" \
  -d '{"query": "{ issues(filter: {team: {key: {eq: \"AI\"}}, createdAt: {gte: \"2025-10-01\"}}, first: 100) { nodes { state { type } } } }"}' \
  | jq '[.data.issues.nodes[].state.type] | group_by(.) | map({type: .[0], count: length})'
```

**Find issues with specific label:**

```bash
curl -s -X POST https://api.linear.app/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: $(linear auth token)" \
  -d '{"query": "{ issues(filter: {team: {key: {eq: \"AI\"}}, labels: {name: {eq: \"Bug\"}}}, first: 50) { nodes { identifier title state { name } } } }"}' \
  | jq '.data.issues.nodes[] | "\(.identifier): \(.title) [\(.state.name)]"'
```

**Get issue history (audit trail):**

```bash
curl -s -X POST https://api.linear.app/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: $(linear auth token)" \
  -d '{"query": "{ issue(id: \"ISSUE_UUID\") { history(first: 20) { nodes { createdAt fromState { name } toState { name } } } } }"}' \
  | jq '.data.issue.history.nodes'
```

**List cycle contents:**

```bash
curl -s -X POST https://api.linear.app/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: $(linear auth token)" \
  -d '{"query": "{ cycles(filter: {team: {key: {eq: \"AI\"}}, isActive: {eq: true}}, first: 1) { nodes { name issues { nodes { identifier title state { name } } } } } }"}' \
  | jq '.data.cycles.nodes[0]'
```

**Check recent comments on an issue:**

```bash
curl -s -X POST https://api.linear.app/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: $(linear auth token)" \
  -d '{"query": "{ issue(id: \"ISSUE_UUID\") { comments(first: 10) { nodes { body createdAt user { name } } } } }"}' \
  | jq '.data.issue.comments.nodes'
```

## Part 3: Team Efficiency Analysis

Efficiency is NOT "doing things fast" — it's **predictably delivering value**.

### Core Metrics

| Metric | Formula | Healthy Range |
| -------- | --------- | --------------- |
| **Throughput** | Completed issues per week | Stable or growing |
| **Lead Time** | `completedAt - createdAt` | Depends on work type |
| **Cycle Time** | `completedAt - startedAt` | < Lead Time |
| **Queue Time** | `startedAt - createdAt` | < 50% of Lead Time |
| **WIP** | Started but not completed | 2-3 per person |
| **SLA Hit Rate** | % completed within target | > 80% for P1/P2 |

### Analysis Scripts

All scripts use [uv inline script metadata](https://docs.astral.sh/uv/guides/scripts/#declaring-script-dependencies) with Pydantic models. Run directly:

```bash
scripts/<script>.py <TEAM_KEY> [--since YYYY-MM-DD] [--debug]
```

| Script | Purpose |
| -------- | --------- |
| `overview.py` | Team stats: state/priority/label/project distribution |
| `sla.py` | SLA analysis, response time by priority, automation detection |
| `flow.py` | Lead Time decomposition: Queue vs Execution |
| `wip.py` | WIP trends, Little's Law, aging analysis |
| `projects.py` | Project health, scope creep, delivery risk |
| `workload.py` | Person load, SLA by person, bottleneck detection |
| `compare.py` | Cross-team comparison |
| `forecast.py` | Monte Carlo delivery forecast, project risk assessment |
| `hunt.py` | Targeted issue list by named filter |

### Quick Examples

```bash
# Team overview (defaults to 90 days)
scripts/overview.py AI

# Team overview with custom date range
scripts/overview.py AI --since 2025-10-01

# Compare two teams
scripts/compare.py AI INF --since 2025-10-01

# Targeted issues
scripts/hunt.py AI --filter stale_wip --limit 50
```

## Key Concepts

### Lead Time Decomposition

```text
Lead Time = Queue Time + Execution Time
     (C→C)      (C→S)         (S→C)
```

- If **Queue > 50%** → Control WIP, improve prioritization
- If **Execution > 50%** → Break down tasks, reduce blockers

### Little's Law

```text
WIP = Throughput × Lead Time
```

Track weekly:

- WIP count (started but not completed)
- Throughput (completed per week)
- Estimated Lead Time = WIP / Throughput × 7

### Pseudo-Cycle Analysis

If team doesn't use Linear Cycles, use natural weeks:

- Arrival per week
- Completion per week
- Net change = arrival - completion - canceled

⚠️ If arrival > throughput consistently, backlog grows forever.

## Common Pitfalls

### 1. startedAt Automation

Many teams auto-set `startedAt` on creation, making Cycle Time meaningless.

**Detection**: If >50% issues have startedAt within 1 minute of createdAt → data unreliable.

### 2. Comparing Raw Counts

❌ "Team A completed 100 issues, Team B completed 50"

✅ Compare same work types (Bug/Feature) at same priority and estimate.

### 3. dueDate as SLA

❌ "Team A has 6% on-time, Team B has 98%"

✅ Check dueDate usage rate first — if one team rarely uses it, not comparable.

### 4. Ignoring Work Type Mix

❌ Comparing lead times without segmenting

✅ Always segment by Bug/Feature/Improvement before comparing.

---

## Adding a New Tool

Use this lightweight template to keep output contract and selection semantics consistent:

```python
from tool_io import emit_meta, emit_prompt, emit_csv, end, log
from tool_prompts import build_prompt
from selection import issues_created_since

def collect_data(team_key: str, since: str, *, debug: bool = False):
    log("Fetching data...")
    issues = issues_created_since(team_key, since, debug=debug)
    return issues

def build_tables(issues):
    # Compute rows for CSV tables here.
    return {"table_name": (headers, rows)}

def emit(team_key: str, since: str, tables: dict):
    emit_meta({"tool": "new_tool", "team": team_key, "since": since, "selection": "createdAt>=since"})
    emit_prompt(build_prompt(findings=[...], recommendations=[...], next_checks=[...]))
    for name, (headers, rows) in tables.items():
        emit_csv(name, headers, rows)
    end()
```

Notes:

- stdout: contract only (PROMPT + CSV + END)
- stderr: logs and debug (use `-debug`)
- selection must be explicit in `@selection`

## Adding a New Filter

1. Add a `FilterSpec` entry in `filters.py`
2. Choose the correct data source (wip snapshot, open SLA, completed window)
3. Keep predicate small and explicit
4. Run `hunt.py` with `--filter <name>` and validate stdout

Example:

```python
FILTERS["stale_wip"] = FilterSpec(
    name="stale_wip",
    description="WIP items with age > 14 days.",
    source=_source_wip,
    predicate=lambda i: bool(i.wip_age_days and i.wip_age_days > 14),
    default_limit=50,
)
```

## GraphQL Query Examples

### Issues with Full Details

```graphql
{
  issues(filter: {
    team: { key: { eq: "AI" } },
    createdAt: { gte: "2025-10-01" }
  }, first: 100) {
    nodes {
      identifier title createdAt startedAt completedAt
      estimate priority
      state { name type }
      assignee { name }
      labels { nodes { name } }
      project { name state targetDate }
      parent { identifier }
    }
    pageInfo { hasNextPage endCursor }
  }
}
```

### Projects for Team

```graphql
{
  projects(first: 100) {
    nodes {
      name progress state startDate targetDate
      lead { name }
      teams { nodes { key } }
    }
  }
}
```
