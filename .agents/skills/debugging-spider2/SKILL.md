---
name: debugging-spider2
description: 'Debug Spider2 data issues on remote servers. Triggers: spider2 data missing, parquet row count mismatch, crawl failures, pueue task issues.'
---

# Debugging Spider2

## Data Structure

```text
dump_parquet/
├── all/YYMMDD/                      # 全量爬虫 (UTC 00:00)
└── increment/YYMMDD_HHMMSS/         # 增量爬虫 (UTC 03:00-23:00)

dump_ndjson/
└── increment/YYMMDD_HHMMSS/         # 增量原始数据

~/.local/share/pueue/task_logs/      # Pueue 任务日志 (<ID>.log)
```

## Pueue JSON Schema

```bash
pueue status --json | jq '.tasks["<ID>"]'
```

关键字段：

- `.original_command` → 包含 `crawl <spider_name> -a task_id=<task_id>`
- `.status.Done.result` → `"Success"` 或 `{"Failed": <code>}`
- `.created_at` / `.status.Done.start` / `.status.Done.end` → 时间戳
- `.path` → 包含 `spider2` 可用于过滤

提取 spider 名称：

```bash
.original_command | capture("crawl (?<s>[^ ]+)").s
```

按日期汇总：

```bash
pueue status --json | jq '
  [.tasks | to_entries[]
   | select(.value.path | contains("spider2"))
   | select(.value.created_at > "YYYY-MM-DD")
  ] | group_by(.value.created_at | split("T")[0])
    | map({date: .[0].value.created_at | split("T")[0], total: length,
           success: [.[] | select(.value.status.Done.result == "Success")] | length})'
```

## Parquet Schema

```sql
-- 关键字段
SELECT site, crawler, task_id, COUNT(*)
FROM 'dump_parquet/all/YYMMDD/**/*.parquet'
GROUP BY 1,2,3
```

按 crawler 对比两天数据：

```sql
WITH t AS (SELECT crawler, COUNT(*) as cnt FROM 'dump_parquet/all/260113/**/*.parquet' GROUP BY 1),
     y AS (SELECT crawler, COUNT(*) as cnt FROM 'dump_parquet/all/260112/**/*.parquet' GROUP BY 1)
SELECT COALESCE(t.crawler, y.crawler) as crawler,
       COALESCE(y.cnt,0) as yesterday, COALESCE(t.cnt,0) as today,
       COALESCE(t.cnt,0) - COALESCE(y.cnt,0) as diff
FROM t FULL OUTER JOIN y ON t.crawler = y.crawler
WHERE ABS(diff) > 100 ORDER BY diff
```

## Log Patterns

日志位置：`~/.local/share/pueue/task_logs/<ID>.log`

关键 grep patterns：

```bash
# 爬取统计 (在日志末尾)
grep -oP "'item_scraped_count': \K\d+"
grep -oP "'spider_exceptions/count': \K\d+"

# 错误类型
grep "ERROR"
grep "ValueError: Cannot use xpath"      # 代理返回 JSON 而非 HTML
grep "Failed to get page_max_value"      # 首页解析失败，通常是 403
```

批量检查最近日志的 exceptions：

```bash
for id in $(ls -t ~/.local/share/pueue/task_logs/*.log | head -20 | xargs -I {} basename {} .log); do
  exc=$(grep -oP "'spider_exceptions/count': \K\d+" ~/.local/share/pueue/task_logs/${id}.log 2>/dev/null | tail -1)
  [ -n "$exc" ] && [ "$exc" -gt 0 ] && echo "$id: $exc exceptions"
done
```

## Common Issues

| 症状 | 原因 | 修复 |
|------|------|------|
| `item_scraped_count: 0` + `Failed to get page_max_value` | 网站 403 封禁直连 IP | 添加 `-s JHS_PROXY=cloudbypass` |
| `ValueError: Cannot use xpath on Selector of type 'json'` | 代理返回 403 JSON | 代理问题或需要增加容错 |
| 任务 3 秒结束 | 首页解析失败，无分页 | 检查网站是否可访问 |
| `response_status_count/403` 很高 | 被目标网站限流 | 降低 `CONCURRENT_REQUESTS` |

## Quick Checks

```bash
# Cron 配置
crontab -l | grep spider2

# 今日任务概览
pueue status --json | jq '[.tasks | to_entries[] | select(.value.created_at > "'$(date +%Y-%m-%d)'") | select(.value.path | contains("spider2"))] | length'

# 检查特定 spider 的任务
pueue status --json | jq '.tasks | to_entries[] | select(.value.original_command | contains("dorasuta_pokemon"))'

# 快速验证网站可访问性
curl -s -o /dev/null -w "%{http_code}" "https://dorasuta.jp/pokemon-card/product-list?cocd=1"
```
