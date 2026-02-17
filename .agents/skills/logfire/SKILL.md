---
name: logfire
description: 'Query, debug, and visualize Logfire traces. Triggers: logfire, trace debug, dashboard.'
metadata:
  version: '3'
---

# Logfire Skill

This skill provides two ways to interact with Logfire:

1. **CLI** (`uvx logfire`) — Generate debugging prompts, manage projects/tokens
2. **MCP Tools** — Query traces and metrics directly from the agent

## CLI Reference

All commands use `uvx logfire <command>`. Global options: `--region {us,eu}`, `--base-url <url>`.

### Authentication & Info

```bash
uvx logfire auth                    # Login (stores credentials locally)
uvx logfire whoami                  # Show current project URL
uvx logfire info                    # Show logfire/python/otel versions
uvx logfire clean [--logs]          # Remove local data/logs
```

### Project Management

```bash
uvx logfire projects list                              # List accessible projects
uvx logfire projects use <name> [--org <org>]          # Switch active project
uvx logfire projects new <name> [--org <org>]          # Create new project
uvx logfire read-tokens --project jihuanshe/jp create  # Create read token for MCP
```

### Generate Debugging Prompt

```bash
uvx logfire prompt --project jihuanshe/<region> "fix-span-issue:<trace-id>"
```

- `<region>`: `cn`, `jp`, or `us`
- `<trace-id>`: 32-char hex trace ID from Logfire UI
- Add `--codex` (Cursor), `--claude`, or `--opencode` to also configure MCP for that editor

### Run with Instrumentation

```bash
uvx logfire run script.py                     # Run with auto-instrumentation
uvx logfire run -m module.name                # Run module
uvx logfire run --exclude httpx script.py     # Exclude specific package
uvx logfire inspect [--ignore <pkg>]          # Show recommended instrumentation packages
```

## MCP Tools

### `mcp__logfire__arbitrary_query`

Run SQL queries on Logfire data. Parameters:

- `query`: SQL string (DataFusion dialect, similar to Postgres)
- `age`: Minutes to look back (max 43200 = 30d)

Example queries:

```sql
-- Top exceptions by type
SELECT exception_type, COUNT(*) as count
FROM records WHERE is_exception = true
GROUP BY exception_type ORDER BY count DESC LIMIT 10

-- Exceptions by service
SELECT service_name, COUNT(*) as count
FROM records WHERE is_exception = true
GROUP BY service_name ORDER BY count DESC

-- Top API routes by request count
SELECT attributes->>'http.route' as route, COUNT(*) as count
FROM records WHERE http_method IS NOT NULL
GROUP BY route ORDER BY count DESC LIMIT 10

-- Trace spans for a specific trace_id
SELECT span_name, message, duration, start_timestamp
FROM records WHERE trace_id = '<trace-id>'
ORDER BY start_timestamp

-- Metrics overview
SELECT metric_name, COUNT(*) as samples
FROM metrics GROUP BY metric_name ORDER BY samples DESC LIMIT 10
```

### `mcp__logfire__find_exceptions_in_file`

Find recent exceptions in a specific file. Returns up to 10 exceptions with full stacktraces.

- `filepath`: Path to the file (e.g., `packages/deck/src/deck/infra/adapters/llm_adapter.py`)
- `age`: Minutes to look back

### `mcp__logfire__logfire_link`

Generate a Logfire UI link for a trace ID. Returns a clickable URL like:
`https://logfire-us.pydantic.dev/jihuanshe/jp?q=trace_id%3D'<trace-id>'`

### `mcp__logfire__schema_reference`

Get the full database schema. Key tables:

**`records`** — Spans and logs

- `trace_id`, `span_id`, `parent_span_id` — Trace correlation
- `span_name`, `message` — What happened
- `start_timestamp`, `end_timestamp`, `duration` — Timing
- `is_exception`, `exception_type`, `exception_message`, `exception_stacktrace` — Errors
- `service_name`, `deployment_environment` — Context
- `http_method`, `http_route`, `http_response_status_code` — HTTP info
- `attributes` — JSON (use `->>'key'` to extract)

**`metrics`** — Counters, gauges, histograms

- `metric_name`, `scalar_value` — For counters/gauges
- `histogram_count`, `histogram_sum`, `histogram_min`, `histogram_max` — For histograms
- `recorded_timestamp` — Time (use this for time_bucket)

## Query Tips

1. Filter by environment: Add `deployment_environment = 'prod'` for production analysis
2. Use DISTINCT: Use `COUNT(DISTINCT trace_id)` to avoid counting retries
3. Exception vs business error: `exception_type` is for Python exceptions; business errors are in `attributes`
4. Time range: Use minutes for age filter (e.g., `720` = 12h, `10080` = 7d)

## Query Validation Checklist

When writing metrics or notification queries, always validate before delivering. Follow these steps:

### 1. Understand the metric type first

```sql
SELECT metric_name, metric_description, is_monotonic, aggregation_temporality,
       MIN(scalar_value), MAX(scalar_value), COUNT(*) AS data_points
FROM metrics WHERE metric_name = '<name>' AND deployment_environment = 'prod'
GROUP BY metric_name, metric_description, is_monotonic, aggregation_temporality
```

- `is_monotonic=true` + `aggregation_temporality=cumulative` → **cumulative counter**. `scalar_value` is the running total since process start, NOT the count in the query window. Never use `COUNT(*)` on data points — that counts how many times the metric was reported, not the metric value.
- `is_monotonic=false` → **gauge**. `scalar_value` is the current value at each point in time.

### 2. Check for multiple instances

```sql
SELECT otel_resource_attributes->>'host.name' AS pod, COUNT(*), MIN(scalar_value), MAX(scalar_value)
FROM metrics WHERE metric_name = '<name>' AND deployment_environment = 'prod'
GROUP BY pod
```

Multiple pods each maintain their own cumulative counter. A naive `MAX(scalar_value) - MIN(scalar_value)` across all data will compute the **cross-instance difference** (e.g., Pod A at 17, Pod B at 9 → result 8), not the actual increase. Always GROUP BY instance first.

### 3. Correct pattern for cumulative counters

```sql
-- Per-instance increase, then sum across instances
SELECT metric_description, SUM(increase) AS new_count
FROM (
  SELECT metric_description,
         otel_resource_attributes->>'host.name' AS pod,
         MAX(scalar_value) - MIN(scalar_value) AS increase
  FROM metrics
  WHERE metric_name = '<name>' AND deployment_environment = 'prod'
  GROUP BY metric_description, pod
) per_pod
GROUP BY metric_description
```

### 4. Watch out for counter resets

If a pod restarts mid-window, its counter resets to 0. `MAX - MIN` will undercount. For critical alerts, consider checking if `MIN` appeared after `MAX` in the time series, which indicates a reset.

## Creating Logfire Dashboards

Generates valid Logfire dashboard JSON for import into the Logfire UI.

### Dashboard JSON Structure

```json
{
  "kind": "Dashboard",
  "metadata": {
    "name": "<DashboardName>",
    "createdAt": "<ISO8601>",
    "updatedAt": "<ISO8601>",
    "version": 0,
    "project": "<project-slug>"
  },
  "spec": {
    "display": {
      "name": "<Display Name>",
      "description": null
    },
    "panels": { ... },
    "layouts": [ ... ],
    "variables": [],
    "duration": "1h",
    "refreshInterval": "0s",
    "datasources": {}
  }
}
```

### Panel Types

#### Time Series Chart

```json
{
  "PanelKey": {
    "kind": "Panel",
    "spec": {
      "display": { "name": "Panel Title" },
      "plugin": {
        "kind": "TimeSeriesChart",
        "spec": {
          "legend": { "position": "bottom" },
          "visual": { "connectNulls": true }
        }
      },
      "queries": [{
        "kind": "TimeSeriesQuery",
        "spec": {
          "plugin": {
            "kind": "LogfireTimeSeriesQuery",
            "spec": {
              "query": "SELECT time_bucket($resolution, recorded_timestamp) AS x, ... FROM metrics GROUP BY x ORDER BY x",
              "metrics": ["metric1", "metric2"],
              "groupBy": "dimension_column"  // optional
            }
          }
        }
      }]
    }
  }
}
```

#### Values (Stats)

```json
{
  "PanelKey": {
    "kind": "Panel",
    "spec": {
      "display": { "name": "Panel Title" },
      "plugin": { "kind": "Values", "spec": {} },
      "queries": [{
        "kind": "NonTimeSeriesQuery",
        "spec": {
          "plugin": {
            "kind": "LogfireNonTimeSeriesQuery",
            "spec": { "query": "SELECT ... FROM metrics" }
          }
        }
      }]
    }
  }
}
```

#### Bar Chart

```json
{
  "PanelKey": {
    "kind": "Panel",
    "spec": {
      "display": { "name": "Panel Title" },
      "plugin": {
        "kind": "BarChart",
        "spec": {
          "calculation": "last",
          "format": { "unit": "decimal", "shortValues": true },
          "sort": "desc",
          "mode": "value",
          "showValues": true
        }
      },
      "queries": [{
        "kind": "NonTimeSeriesQuery",
        "spec": {
          "plugin": {
            "kind": "LogfireNonTimeSeriesQuery",
            "spec": { "query": "SELECT category, value FROM ..." }
          }
        }
      }]
    }
  }
}
```

#### Table

```json
{
  "PanelKey": {
    "kind": "Panel",
    "spec": {
      "display": { "name": "Panel Title" },
      "plugin": { "kind": "Table", "spec": {} },
      "queries": [{
        "kind": "NonTimeSeriesQuery",
        "spec": {
          "plugin": {
            "kind": "LogfireNonTimeSeriesQuery",
            "spec": { "query": "SELECT ... FROM ..." }
          }
        }
      }]
    }
  }
}
```

#### Pie Chart

```json
{
  "plugin": { "kind": "PieChart", "spec": {} }
}
```

#### Gauge Chart

```json
{
  "PanelKey": {
    "kind": "Panel",
    "spec": {
      "display": { "name": "Panel Title" },
      "plugin": {
        "kind": "GaugeChart",
        "spec": {
          "calculation": "last",
          "format": { "unit": "percent" },
          "thresholds": {
            "steps": [
              { "value": 0, "color": "green" },
              { "value": 50, "color": "yellow" },
              { "value": 80, "color": "red" }
            ]
          },
          "max": 100
        }
      },
      "queries": [{
        "kind": "NonTimeSeriesQuery",
        "spec": {
          "plugin": {
            "kind": "LogfireNonTimeSeriesQuery",
            "spec": { "query": "SELECT value FROM ..." }
          }
        }
      }]
    }
  }
}
```

### Layout Configuration

Panels are arranged in a 24-column grid:

```json
{
  "layouts": [{
    "kind": "Grid",
    "spec": {
      "display": {
        "title": "Group Title",
        "collapse": { "open": true }
      },
      "items": [
        { "x": 0, "y": 0, "width": 12, "height": 6, "content": { "$ref": "#/spec/panels/PanelKey" } },
        { "x": 12, "y": 0, "width": 12, "height": 6, "content": { "$ref": "#/spec/panels/AnotherPanel" } }
      ]
    }
  }]
}
```

- width: 1-24 (full width = 24, half = 12)
- height: typically 6 for standard panels
- x, y: grid position (x: 0-23, y: row * 6)

### Query Guidelines

#### Time Series Queries

- Must include `time_bucket($resolution, recorded_timestamp) AS x`
- Use `recorded_timestamp` for metrics table
- Use `start_timestamp` for records table
- GROUP BY x, ORDER BY x

#### Metrics Table Columns

- `metric_name`, `scalar_value` - for counters/gauges
- `histogram_count`, `histogram_sum`, `histogram_min`, `histogram_max` - for histograms
- `attributes` - JSON attributes (use `->>'key'` to extract)

#### Special Variable

- `$resolution` - auto-adjusts based on dashboard time range

### Panel Key Naming

- Use PascalCase without spaces: `MessagesOverTime`, `QueueLength`
- Avoid special characters in keys (use `SuccessErrorRate` not `Success/ErrorRate`)

### Workflow

1. Define panels in `spec.panels` with unique keys
2. Create grid layout in `spec.layouts[0].spec.items`
3. Reference panels using `{ "$ref": "#/spec/panels/PanelKey" }`
4. Set `duration` (e.g., "1h", "24h", "7d")
5. Save as `.json` and import via Logfire UI → Dashboards → + Dashboard → Custom → Import JSON
