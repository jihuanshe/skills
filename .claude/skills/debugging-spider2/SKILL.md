---
name: debugging-spider2
description: 'Debug Spider2 data issues on remote servers. Triggers: spider2 data missing, parquet row count mismatch, crawl failures, pueue task issues.'
---

# Debugging Spider2 Data Issues

Guide for investigating Spider2 crawler data problems on production servers.

## Prerequisites

- SSH access to the spider2 server
- `pueue`, `jq`, `duckdb` available on the server
- Spider2 project at `/root/python-spider2`

## Date Variables

Many commands use date placeholders. Set them first:

```bash
# For Linux
TODAY=$(date +%Y%m%d)
YESTERDAY=$(date -d 'yesterday' +%Y%m%d)

# For macOS
TODAY=$(date +%Y%m%d)
YESTERDAY=$(date -v-1d +%Y%m%d)
```

Then use them in commands:

```bash
ls -la dump_parquet/task_${TODAY}/ dump_parquet/task_${YESTERDAY}/ 2>/dev/null
```

## Investigation Workflow

### 1. Check Task Status (Pueue)

List recent spider2 tasks:

```bash
pueue status --json 2>/dev/null | jq '[.tasks | to_entries[] | select(.value.path | contains("spider2")) | {id: .key, status: .value.status, command: .value.original_command, created: .value.created_at}] | sort_by(.id | tonumber) | reverse | .[0:20]'
```

Check largest log files:

```bash
ls -lt ~/.local/share/pueue/task_logs/ | head -30
```

### 2. Check Cron Configuration

```bash
crontab -l 2>/dev/null
```

### 3. Compare Data Across Days

Check parquet directories:

```bash
ls -la dump_parquet/task_${TODAY}/ dump_parquet/task_${YESTERDAY}/ 2>/dev/null
```

Count rows with DuckDB:

```bash
mise exec -- uv run duckdb -c "SELECT COUNT(*) as today FROM 'dump_parquet/task_${TODAY}/**/*.parquet'"
mise exec -- uv run duckdb -c "SELECT COUNT(*) as yesterday FROM 'dump_parquet/task_${YESTERDAY}/**/*.parquet'"
```

### 4. Find Problem Source by Site

Compare row counts per site:

```bash
mise exec -- uv run duckdb -c "
WITH today AS (
    SELECT site, COUNT(*) as cnt FROM 'dump_parquet/task_${TODAY}/**/*.parquet' GROUP BY site
),
yesterday AS (
    SELECT site, COUNT(*) as cnt FROM 'dump_parquet/task_${YESTERDAY}/**/*.parquet' GROUP BY site
)
SELECT
    COALESCE(t.site, y.site) as site,
    COALESCE(y.cnt, 0) as yesterday,
    COALESCE(t.cnt, 0) as today,
    COALESCE(t.cnt, 0) - COALESCE(y.cnt, 0) as diff
FROM today t
FULL OUTER JOIN yesterday y ON t.site = y.site
ORDER BY diff ASC
LIMIT 30;
"
```

### 5. Check Specific Crawler Logs

View log for a specific task:

```bash
tail -100 ~/.local/share/pueue/task_logs/<TASK_ID>.log
```

Common issues to look for:

- SSL certificate warnings
- Connection timeouts
- Rate limiting (429 errors)
- Parse errors

### 6. Verify SSL Certificates

Check if target site certificate is valid:

```bash
echo | openssl s_client -connect <HOSTNAME>:443 -servername <HOSTNAME> 2>/dev/null | openssl x509 -noout -text 2>/dev/null | grep -E "Subject:|DNS:|Not Before|Not After|subjectAltName"
```

### 7. Check Retry Configuration

Scrapy default retry exceptions:

```bash
mise exec -- uv run python -c "from scrapy.settings.default_settings import RETRY_EXCEPTIONS; print(RETRY_EXCEPTIONS)"
```

Check spider-specific retry settings:

```bash
grep -E "RETRY|retry" /root/python-spider2/apps/spider2/src/spider2/spiders/<SPIDER_PATH>.py
```

## Common Issues & Fixes

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| SSL cert warning in logs | Proxy returning wrong cert | Add SSL error to `RETRY_EXCEPTIONS` |
| 429 errors | Rate limiting | Reduce `CONCURRENT_REQUESTS` |
| Connection timeout | Network/proxy issues | Check proxy health |
| Early exit, no errors | Missing pagination | Check next page selector |

## Key Files

- Crawler code: `/root/python-spider2/apps/spider2/src/spider2/spiders/`
- Proxy middleware: `middlewares/proxy.py`
- Task runner: `.mise/tasks/spider2/run-crawl-all.sh`
- Pueue logs: `~/.local/share/pueue/task_logs/`
