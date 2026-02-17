---
name: signoz-dashboard
description: "Generates SigNoz dashboard JSON files for metrics visualization. Use when asked to create SigNoz dashboards, monitoring panels, or export metrics to SigNoz."
---

# SigNoz Dashboard Generator

Generates ready-to-import SigNoz dashboard JSON files based on OpenTelemetry metrics.

## Capabilities

- Create complete dashboard JSON for SigNoz import
- Support all panel types: Value, Timeseries, Bar, Pie, Table, Histogram
- Configure metrics queries using Query Builder format
- Set up dashboard variables for filtering
- Organize panels with row separators

## Workflow

1. **Gather Requirements**
   - Ask for metric names and their types (Counter, Gauge, Histogram)
   - Ask for desired panel layout and grouping
   - Ask for labels/attributes to filter or group by

2. **Generate Dashboard JSON**
   - Use the template structure from `reference/template.json`
   - Follow naming convention: `{service}-dashboard-otlp-v1.json`

3. **Output Location**
   - Save to `docs/signoz-dashboards/` directory

## Panel Types

| Type | Use Case | Key Config |
|------|----------|------------|
| `value` | Single metric display | `reduceTo`: latest/sum/avg |
| `graph` | Time series trends | `timeAggregation`: rate/increase/avg |
| `bar` | Categorical comparison | `groupBy` required |
| `pie` | Proportional data | `groupBy` required |
| `table` | Detailed breakdowns | Multiple `groupBy` |
| `histogram` | Distribution analysis | For Histogram metrics |

## Query Builder Structure

```json
{
  "aggregateAttribute": {
    "dataType": "float64",
    "key": "metric_name",
    "type": "Sum|Gauge|Histogram"
  },
  "aggregateOperator": "sum|avg|rate|p50|p90|p99|increase",
  "dataSource": "metrics",
  "filters": {
    "items": [
      {"key": {"key": "label_name", "type": "tag"}, "op": "=", "value": "value"}
    ],
    "op": "AND"
  },
  "groupBy": [
    {"key": "label_name", "type": "tag", "dataType": "string"}
  ],
  "legend": "{{label_name}}",
  "timeAggregation": "rate|increase|avg|latest"
}
```

## Common Metric Type Mappings

| OTel Type | SigNoz Type | Typical Aggregation |
|-----------|-------------|---------------------|
| Counter | Sum | rate, increase |
| Gauge | Gauge | avg, latest |
| Histogram | Histogram | p50, p90, p99 |

## Y-Axis Units

Common units: `none`, `s`, `ms`, `percent`, `bytes`, `reqps`, `ops`

## Example: Counter Rate Panel

```json
{
  "id": "request-rate",
  "panelTypes": "graph",
  "title": "Request Rate",
  "query": {
    "builder": {
      "queryData": [{
        "aggregateAttribute": {
          "dataType": "float64",
          "key": "http_requests_total",
          "type": "Sum"
        },
        "aggregateOperator": "rate",
        "dataSource": "metrics",
        "filters": {"items": [], "op": "AND"},
        "groupBy": [{"key": "status", "type": "tag", "dataType": "string"}],
        "legend": "{{status}}",
        "queryName": "A",
        "timeAggregation": "rate"
      }],
      "queryFormulas": []
    },
    "queryType": "builder"
  },
  "yAxisUnit": "reqps"
}
```

## Example: Histogram Percentiles Panel

```json
{
  "id": "latency-percentiles",
  "panelTypes": "graph",
  "title": "Latency P50/P90/P99",
  "query": {
    "builder": {
      "queryData": [
        {
          "aggregateAttribute": {"key": "request_duration_seconds", "type": "Histogram"},
          "aggregateOperator": "p50",
          "legend": "P50",
          "queryName": "A"
        },
        {
          "aggregateAttribute": {"key": "request_duration_seconds", "type": "Histogram"},
          "aggregateOperator": "p90",
          "legend": "P90",
          "queryName": "B"
        },
        {
          "aggregateAttribute": {"key": "request_duration_seconds", "type": "Histogram"},
          "aggregateOperator": "p99",
          "legend": "P99",
          "queryName": "C"
        }
      ]
    }
  },
  "yAxisUnit": "s"
}
```

## Example: Value Panel with Formula

```json
{
  "id": "success-rate",
  "panelTypes": "value",
  "title": "Success Rate",
  "query": {
    "builder": {
      "queryData": [
        {
          "aggregateAttribute": {"key": "requests_total", "type": "Sum"},
          "filters": {"items": [{"key": {"key": "status"}, "op": "=", "value": "success"}]},
          "queryName": "A"
        },
        {
          "aggregateAttribute": {"key": "requests_total", "type": "Sum"},
          "queryName": "B"
        }
      ],
      "queryFormulas": [{"expression": "A / B * 100", "queryName": "F1"}]
    }
  },
  "yAxisUnit": "percent"
}
```

## Layout Configuration

Panel positions use grid coordinates:

- `w`: width (1-12, full width = 12)
- `h`: height (rows, typical = 3-6)
- `x`: horizontal position (0-11)
- `y`: vertical position (row number)

Row separators: `"panelTypes": "row"` with `h: 1`, `w: 12`

## Import Instructions

1. SigNoz UI → Dashboards → + New Dashboard
2. Click "Import JSON"
3. Paste or upload the generated JSON file
