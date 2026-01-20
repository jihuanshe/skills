---
name: creating-logfire-dashboards
description: Generates Logfire dashboard JSON files for importing into Pydantic Logfire. Use when asked to create dashboards, visualize metrics, or build monitoring panels.
---

# Creating Logfire Dashboards

Generates valid Logfire dashboard JSON for import into the Logfire UI.

## Dashboard JSON Structure

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

## Panel Types

### Time Series Chart
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

### Values (Stats)
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

### Bar Chart
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

### Table
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

### Pie Chart
```json
{
  "plugin": { "kind": "PieChart", "spec": {} }
}
```

### Gauge Chart
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

## Layout Configuration

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

- **width**: 1-24 (full width = 24, half = 12)
- **height**: typically 6 for standard panels
- **x, y**: grid position (x: 0-23, y: row * 6)

## Query Guidelines

### Time Series Queries
- Must include `time_bucket($resolution, recorded_timestamp) AS x`
- Use `recorded_timestamp` for metrics table
- Use `start_timestamp` for records table
- GROUP BY x, ORDER BY x

### Metrics Table Columns
- `metric_name`, `scalar_value` - for counters/gauges
- `histogram_count`, `histogram_sum`, `histogram_min`, `histogram_max` - for histograms
- `attributes` - JSON attributes (use `->>'key'` to extract)

### Special Variable
- `$resolution` - auto-adjusts based on dashboard time range

## Panel Key Naming

- Use PascalCase without spaces: `MessagesOverTime`, `QueueLength`
- Avoid special characters in keys (use `SuccessErrorRate` not `Success/ErrorRate`)

## Workflow

1. Define panels in `spec.panels` with unique keys
2. Create grid layout in `spec.layouts[0].spec.items`
3. Reference panels using `{ "$ref": "#/spec/panels/PanelKey" }`
4. Set `duration` (e.g., "1h", "24h", "7d")
5. Save as `.json` and import via Logfire UI → Dashboards → + Dashboard → Custom → Import JSON
