---
name: spider2-debug
description: 'Debug Spider2 crawl failures and data quality. Triggers: crawl error, empty fields, data issue.'
metadata:
  version: '1'
---

# Debugging Spider2

## 🚀 快速排查流程（先做这些再深入）

### Step 1: 确定问题类型

| 问题描述 | 快速命令 | 判断依据 |
| :--------- | :--------- | :--------- |
| 增量数据字段为空 | `duckdb -csv -c "SELECT ... empty_title"` | empty_title > 0 = 后台维护 |
| 任务失败 | `pueue log <ID> \| tail -50` | 看 ERROR 和统计 |
| 数据量异常 | `duckdb -csv -c "SELECT crawler, COUNT(*)"` | 对比昨日 |

### Step 2: 增量数据质量检查（最常用）

```bash
# 一键检查最新增量批次的数据质量
duckdb -csv -c "
SELECT
  regexp_extract(product_url, 'dorasuta\.jp/([^/]+)/', 1) as game,
  COUNT(*) as total,
  SUM(CASE WHEN product_title = '' OR product_title IS NULL THEN 1 ELSE 0 END) as empty_title,
  SUM(CASE WHEN product_condition_list IS NULL OR len(product_condition_list) = 0 THEN 1 ELSE 0 END) as empty_condition
FROM 'dump_parquet/increment/$(ls -t dump_parquet/increment | head -1)/**/*.parquet'
GROUP BY 1
ORDER BY empty_title DESC
"
```

**解读**：

- `empty_title = total` → 该类目后台维护，整个类目失败
- `empty_title` 占比小 → 部分商品下架
- `empty_condition > 0` 但 `empty_title = 0` → 检查解析逻辑

### Step 3: 快速定位日志

```bash
# 找到某批次的 pueue 任务 ID
rg -l "<task_id_pattern>" ~/.local/share/pueue/task_logs/ | head -5

# 检查警告数（空字段的快速指标）
rg -c "没有获取到" ~/.local/share/pueue/task_logs/<ID>.log
```

**警告数判断**：

- 警告数 ≈ scraped × 2 → 全部失败（后台维护）
- 警告数 << scraped → 大部分成功
- 警告数 = 0 → 全部成功

## ⚠️ 常见弯路（不要这样做）

| ❌ 弯路 | ✅ 正确做法 | 原因 |
| :-------- | :----------- | :----- |
| 用 polars/pandas 写复杂 Python 分析 | 用 duckdb 一行 SQL | duckdb 直接读 parquet，更快更简洁 |
| 用 `os.environ['MONGODB_URI']` 连 MongoDB | 直接分析 `dump_parquet/` | parquet 已是导出数据，无需连接数据库 |
| 看到空字段就怀疑解析逻辑 | 先检查 `empty_title` 是否也为空 | title 也空 = 整个解析失败 = 后台维护 |
| 用 httpx/curl 测试页面 | 用 `scrapy fetch` | TLS 指纹不同，curl 会被 Cloudflare 拦截 |
| 逐条分析空字段 | 先看日志警告数 | 警告数 ≈ scraped × 2 = 后台维护 |

## ⚠️ 关键背景知识

### 代理配置来源

**运行时配置看 `apps/cron/spider2/crawl_all/main.sh`，不是爬虫代码。**

```bash
# 查看实际运行配置
rg "<spider_name>" apps/cron/spider2/crawl_all/main.sh

# 有 -s JHS_PROXY=cloudbypass → 使用 HTTP 代理
# 无 JHS_PROXY → 直连（如 dorasuta）
```

### 代理策略速查

| 网站 | 代理策略 | 备注 |
| ------ | ---------- | ------ |
| **dorasuta** | 直连（无代理） | IP 白名单，龙星已开放 |
| cardrush | HTTP 代理 | JHS_PROXY=cloudbypass |
| hareruya2 | HTTP 代理 | JHS_PROXY=cloudbypass |
| hareruyamtg | HTTP 代理 | JHS_PROXY=cloudbypass |
| mercari | HTTP 代理 | JHS_PROXY=cloudbypass |
| yuyu-tei | HTTP 代理 | JHS_PROXY=cloudbypass |

### 两种代理模式（不要混淆）

| 模式 | 触发方式 | 环境变量 | 工作原理 |
| ------ | ---------- | ---------- | ---------- |
| **HTTP 代理** | `-s JHS_PROXY=cloudbypass` | `PROXY_CLOUDBYPASS_SERVER/USERNAME/PASSWORD` | 请求通过 HTTP 代理服务器 |
| **API 代理** | `CloudBypassRequest(cloudbypass_enabled=True)` | `PROXY_CLOUDBYPASS_APIKEY/LONG` | 请求发送到 api.cloudbypass.com |

**dorasuta 特殊情况**：代码中有 `CloudBypassRequest`，但 `cloudbypass_enabled=False`（默认），实际不走 API，直连目标网站。

### 测试工具选择

**必须用 `scrapy fetch`，不能用 httpx/curl/requests。**

Cloudflare 根据 TLS fingerprint 区分客户端。scrapy 和 httpx 的指纹不同：

- scrapy fetch → 通过（匹配爬虫环境）
- httpx/curl → 403 "Just a moment..."（被拦截）

```bash
# 正确
cd apps/spider2
timeout 30 mise exec --env local -- uv run scrapy fetch "<URL>" -s LOG_LEVEL=ERROR 2>/dev/null > /tmp/page.html

# 错误（会误判为 Cloudflare 封禁）
curl "https://dorasuta.jp/..."
python -c "import httpx; print(httpx.get('https://dorasuta.jp/...').status_code)"
```

### URL 来源

**从爬虫代码提取，不要猜测。**

```bash
# 找 URL 定义
rg "base_url|start_urls" apps/spider2/src/spider2/spiders/<site>/
rg "def gen_request" apps/spider2/src/spider2/spiders/<site>/

# 常见错误
# ❌ hareruya.com → ✅ hareruya2.com
# ❌ 随意构造参数 → ✅ 从 gen_request 提取完整参数
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

提取 spider 名称（jq 表达式）：

```bash
.original_command | capture("crawl (?<s>[^ ]+)").s
```

按日期汇总：

```bash
pueue status --json | jq '
  [.tasks | to_entries[]
   | select(.value.path | contains("spider2"))
   | select(.value.created_at > "'$(date +%Y-%m-%d)'")
  ] | group_by(.value.created_at | split("T")[0])
    | map({date: .[0].value.created_at | split("T")[0], total: length,
           success: [.[] | select(.value.status.Done.result == "Success")] | length})'
```

## Parquet Schema

```sql
SELECT site, crawler, task_id, COUNT(*)
FROM 'dump_parquet/all/YYMMDD/**/*.parquet'
GROUP BY 1,2,3
```

按 crawler 对比两天数据：

```bash
TODAY=$(date +%y%m%d)
YESTERDAY=$(date -d "yesterday" +%y%m%d 2>/dev/null || date -v-1d +%y%m%d)
duckdb -csv -c "
WITH t AS (SELECT crawler, COUNT(*) as cnt FROM 'dump_parquet/all/${TODAY}/**/*.parquet' GROUP BY 1),
     y AS (SELECT crawler, COUNT(*) as cnt FROM 'dump_parquet/all/${YESTERDAY}/**/*.parquet' GROUP BY 1)
SELECT COALESCE(t.crawler, y.crawler) as crawler,
       COALESCE(y.cnt,0) as yesterday, COALESCE(t.cnt,0) as today,
       COALESCE(t.cnt,0) - COALESCE(y.cnt,0) as diff
FROM t FULL OUTER JOIN y ON t.crawler = y.crawler
WHERE ABS(diff) > 100 ORDER BY diff
"
```

## Data Structure

```text
dump_parquet/
├── all/YYMMDD/                      # 全量爬虫 (UTC 00:00)
└── increment/YYMMDD_HHMMSS/         # 增量爬虫 (UTC 03:00-23:00)

dump_ndjson/
└── increment/YYMMDD_HHMMSS/         # 增量原始数据

~/.local/share/pueue/task_logs/      # Pueue 任务日志 (<ID>.log)
```

## Log Patterns

日志位置：`~/.local/share/pueue/task_logs/<ID>.log`

关键 rg patterns：

```bash
# 爬取统计（在日志末尾，任务快速失败时可能无输出）
rg -oP "'item_scraped_count': \K\d+"
rg -oP "'spider_exceptions/count': \K\d+"

# 代理配置确认
rg "ProxyMiddleware initialized with JHS_PROXY"
# JHS_PROXY: None → 直连
# JHS_PROXY: cloudbypass → HTTP 代理

# 错误类型
rg "ERROR"
rg "ValueError: Cannot use xpath"      # 代理返回 JSON 而非 HTML
rg "Failed to get page_max_value"      # 首页解析失败
```

## Common Issues

| 症状 | 原因 | 修复 |
| ------ | ------ | ------ |
| 无 `item_scraped_count` + 任务 <10s 结束 | 首页解析失败，无分页生成 | 检查日志 ERROR，确认网站可访问性 |
| `item_scraped_count: 0` + `Failed to get page_max_value` + HTTP 200 | **网站后台问题**（page_max 为空） | 联系网站方确认商品数据库状态 |
| `item_scraped_count: 0` + `Failed to get page_max_value` + HTTP 403 | Cloudflare 封禁 | 添加 `-s JHS_PROXY=cloudbypass`（仅限非 dorasuta） |
| `ValueError: Cannot use xpath on Selector of type 'json'` | 代理返回 403 JSON | 代理问题或需要增加容错 |
| `response_status_count/403` 很高 | 被目标网站限流 | 降低 `CONCURRENT_REQUESTS` |
| 单个 spider 数据为 0，其他正常 | 该类目页面结构变化或后台无数据 | 用 scrapy fetch 对比页面结构 |
| hareruya2 返回 "商品が見つかりませんでした" | 该类目无在库商品（filter.v.availability=1） | 正常现象，无需处理 |

## Page Structure Analysis

当怀疑是**页面结构变化**或**网站后台问题**时，用 scrapy fetch 保存页面进行分析：

```bash
cd /root/python-spider2/apps/spider2

# 保存页面内容（比 scrapy shell 更可靠，不会卡住）
timeout 30 mise exec --env local -- uv run scrapy fetch "<URL>" -s LOG_LEVEL=ERROR 2>/dev/null > /tmp/page.html

# 检查关键元素
rg -oP '<input[^>]*id="page_max"[^>]*>' /tmp/page.html   # 分页数
rg -c 'class="element"' /tmp/page.html                    # 商品数量（dorasuta）
rg -c 'id="product-grid"' /tmp/page.html                  # 商品容器（hareruya2）
```

### 对比正常页面和异常页面

```bash
# 保存两个页面（同一网站不同类目）
timeout 30 mise exec --env local -- uv run scrapy fetch "https://dorasuta.jp/pokemon-card/product-list?cocd=1" -s LOG_LEVEL=ERROR 2>/dev/null > /tmp/pokemon.html
timeout 30 mise exec --env local -- uv run scrapy fetch "https://dorasuta.jp/mtg/product-list?cocd=1" -s LOG_LEVEL=ERROR 2>/dev/null > /tmp/mtg.html

# 对比关键元素
echo "Pokemon page_max:"; rg -oP 'id="page_max"[^>]*value="\K[^"]*' /tmp/pokemon.html || echo "(empty)"
echo "MTG page_max:"; rg -oP 'id="page_max"[^>]*value="\K[^"]*' /tmp/mtg.html
echo "Pokemon elements:"; rg -c 'class="element"' /tmp/pokemon.html
echo "MTG elements:"; rg -c 'class="element"' /tmp/mtg.html
```

**解读**：如果 MTG 正常（page_max=6266）而 Pokemon 为空，说明是 Pokemon 类目后台问题，不是爬虫问题。

## Debug Workflow

1. **确认问题范围**：检查今日相关任务的 item_scraped_count
2. **查看日志**：找 ERROR 或异常统计（注意：快速失败的任务无统计输出）
3. **确认代理配置**：

   ```bash
   rg "ProxyMiddleware initialized" ~/.local/share/pueue/task_logs/<ID>.log
   ```

4. **区分问题类型**：
   - HTTP 403 + "Just a moment..." → Cloudflare 封禁
   - HTTP 200 + page_max 为空 → 网站后台问题
   - HTTP 200 + xpath 匹配失败 → 页面结构变化
   - "商品が見つかりませんでした" → 该类目无在库商品（正常）
5. **对比分析**：用 scrapy fetch 保存页面，对比正常/异常页面
6. **历史趋势**：检查问题开始时间，判断是突发还是渐进

## 常见误判及避免方法

| 误判 | 实际情况 | 如何避免 |
| ------ | ---------- | ---------- |
| "dorasuta 需要加 cloudbypass 代理" | dorasuta 是 IP 白名单，直连即可 | 检查 apps/cron/spider2/crawl_all/main.sh |
| "CloudBypass 余额不足导致失败" | dorasuta 不走 CloudBypass API | 确认代理模式 |
| "网站无法访问（curl 403）" | curl/httpx 被 Cloudflare 拦截 | 用 scrapy fetch 测试 |
| "hareruya.com 超时" | 实际 URL 是 hareruya2.com | 从爬虫代码提取 URL |
| "代理配置错误" | HTTP 代理和 API 代理混淆 | 区分 JHS_PROXY 和 CloudBypassRequest |

## 环境变量参考

### HTTP 代理模式（JHS_PROXY=cloudbypass）

```bash
PROXY_CLOUDBYPASS_SERVER    # 代理服务器地址
PROXY_CLOUDBYPASS_USERNAME  # 代理用户名
PROXY_CLOUDBYPASS_PASSWORD  # 代理密码
```

### API 代理模式（CloudBypassRequest）

```bash
PROXY_CLOUDBYPASS_APIKEY    # API Key
PROXY_CLOUDBYPASS_LONG      # 代理池列表（| 分隔）
```

**注意**：dorasuta 代码虽有 CloudBypassRequest，但默认 `cloudbypass_enabled=False`，不使用 API 模式。

## Historical Trend Analysis

检查问题开始时间，定位是渐进性还是突发性：

```bash
# 查看某个 spider 最近 10 次的 item_scraped_count 趋势
for id in $(pueue status --json | jq -r '.tasks | to_entries[] | select(.value.original_command | contains("dorasuta_pokemon")) | select(.value.original_command | contains("product_detail") | not) | .key' | tail -10); do
  created=$(pueue status --json | jq -r ".tasks[\"$id\"].created_at" | cut -d'T' -f1)
  cnt=$(rg -oP "'item_scraped_count': \K\d+" ~/.local/share/pueue/task_logs/${id}.log 2>/dev/null | tail -1)
  echo "$created (task $id): ${cnt:-0} items"
done | sort
```

批量检查最近日志的 exceptions：

```bash
for id in $(ls -t ~/.local/share/pueue/task_logs/*.log 2>/dev/null | head -20 | xargs -I {} basename {} .log); do
  exc=$(rg -oP "'spider_exceptions/count': \K\d+" ~/.local/share/pueue/task_logs/${id}.log 2>/dev/null | tail -1)
  [ -n "$exc" ] && [ "$exc" -gt 0 ] && echo "$id: $exc exceptions"
done
```

## Quick Checks

```bash
# Cron 配置
crontab -l | rg spider2

# 今日任务概览
pueue status --json | jq '[.tasks | to_entries[] | select(.value.created_at > "'$(date +%Y-%m-%d)'") | select(.value.path | contains("spider2"))] | length'

# 检查特定 spider 的任务
pueue status --json | jq '.tasks | to_entries[] | select(.value.original_command | contains("dorasuta_pokemon"))'

# 今日所有 dorasuta 任务的 item_scraped_count
for id in $(pueue status --json | jq -r '.tasks | to_entries[] | select(.value.created_at > "'$(date +%Y-%m-%d)'") | select(.value.original_command | contains("dorasuta")) | .key'); do
  spider=$(pueue status --json | jq -r ".tasks[\"$id\"].original_command" | rg -oP 'crawl \K[^ ]+')
  cnt=$(rg -oP "'item_scraped_count': \K\d+" ~/.local/share/pueue/task_logs/${id}.log 2>/dev/null | tail -1)
  echo "$spider: ${cnt:-0}"
done
```

## 增量爬虫调试

增量爬虫（`dorasuta_product_detail`）按 URL 爬取详情页，与全量列表爬虫不同。

### 增量数据路径

```text
data/product_urls/increment/YYMMDD_HHMMSS/
├── summary.json                           # 各类目 URL 数量
├── dorasuta_pokemon_urls.txt              # Pokemon URL 列表
├── dorasuta_pokemon_urls_split/           # 分片目录
│   ├── part_0.txt
│   ├── part_1.txt
│   └── ...
└── dorasuta_yugioh_urls.txt               # YuGiOh URL 列表
```

### 检查增量爬取结果

```bash
# 查看某时段某类目的爬取结果
for id in $(rg -l "pokemon_260115_060001" ~/.local/share/pueue/task_logs/ 2>/dev/null | xargs -I{} basename {} .log); do
  cnt=$(rg -oP "'item_scraped_count': \K\d+" ~/.local/share/pueue/task_logs/${id}.log | tail -1)
  warn=$(rg -c "没有获取到" ~/.local/share/pueue/task_logs/${id}.log)
  echo "Task $id: scraped=${cnt:-0}, warnings=$warn"
done
```

### 判断增量失败类型

**警告数 vs 抓取数关系**：

| 警告数 | 含义 | 原因 |
| :------- | :----- | :----- |
| `warnings ≈ scraped × 2` | 全部失败 | 每条商品 2 个警告（条件列表 + 系列列表） |
| `warnings << scraped × 2` | 大部分成功 | 少量商品下架或数据异常 |
| `warnings = 0` | 全部成功 | 正常 |

### 增量 Parquet 按类目统计

```sql
-- 检查哪些类目有空标题（失败标志）
SELECT
  CASE
    WHEN product_url LIKE '%pokemon%' THEN 'pokemon'
    WHEN product_url LIKE '%yugioh%' THEN 'yugioh'
    WHEN product_url LIKE '%mtg%' THEN 'mtg'
    ELSE 'other'
  END as game,
  COUNT(*) as total,
  SUM(CASE WHEN product_title = '' OR product_title IS NULL THEN 1 ELSE 0 END) as empty_title
FROM 'dump_parquet/increment/260115_*/**/*.parquet'
GROUP BY 1
ORDER BY empty_title DESC
```

**解读**：`empty_title = total` 表示该类目全部失败（后台维护）；`empty_title` 占比小表示部分商品下架。

### condition_list 字段排查

当发现 `condition_list` 为空时，按以下顺序排查：

```bash
# 1. 先检查 title 是否也为空（快速判断后台维护）
duckdb -csv -c "
SELECT
  regexp_extract(product_url, 'dorasuta\.jp/([^/]+)/', 1) as game,
  SUM(CASE WHEN len(product_condition_list) = 0 THEN 1 ELSE 0 END) as empty_condition,
  SUM(CASE WHEN product_title = '' THEN 1 ELSE 0 END) as empty_title
FROM 'dump_parquet/increment/<RUN_ID>/**/*.parquet'
GROUP BY 1 HAVING empty_condition > 0
"
```

| empty_condition | empty_title | 结论 |
| :---------------- | :------------ | :----- |
| N | N | 后台维护，无需修复 |
| N | 0 | **解析逻辑问题**，需检查 xpath |
| 少量 | 0 | 部分商品无库存（在庫なし），正常 |

```bash
# 2. 如果 empty_title = 0，检查 condition 值分布
duckdb -csv -c "
SELECT unnest(product_condition_list).condition as cond, COUNT(*)
FROM 'dump_parquet/increment/<RUN_ID>/**/*.parquet'
GROUP BY 1 ORDER BY 2 DESC
"
# 正常值: 状態A, 状態B, 状態C, 状態A特価, 状態B特価, 状態C特価
```

## 后台维护 vs 商品下架

龙星后台会轮换维护不同类目，导致不同时段不同类目可能失败。

### 两种场景区分

| 场景 | 影响范围 | 列表页 | 详情页 | 日志特征 |
| :----- | :--------- | :------- | :------- | :--------- |
| **后台维护** | 整个类目 100% | `page_max` 为空 | 无 `frame product` | 全量：`Failed to get page_max_value` 增量：每条都有 2 个警告 |
| **商品下架** | 单个商品 | 正常 | 无 `frame product` | 仅个别商品有警告 |

### 后台维护验证

```bash
# 对比同一网站不同类目的 page_max
cd apps/spider2
for game in pokemon-card mtg yugioh-jp weissschwarz; do
  cnt=$(timeout 20 mise exec --env local -- uv run scrapy fetch "https://dorasuta.jp/${game}/product-list?cocd=1" -s LOG_LEVEL=ERROR 2>/dev/null | rg -oP 'id="page_max"[^>]*value="\K[^"]*')
  echo "$game: ${cnt:-(empty)}"
done
```

**解读**：如果部分类目正常、部分为空 → 龙星后台轮换维护

### 商品下架验证

```bash
# 检查详情页是否有 frame product
cd apps/spider2
mise exec --env local -- uv run scrapy fetch "https://dorasuta.jp/pokemon-card/product?pid=654882" -s LOG_LEVEL=ERROR 2>/dev/null > /tmp/detail.html

# frame product 存在 = 正常商品
rg -c 'class="frame product"' /tmp/detail.html  # 0=下架, 1=正常

# 页面行数对比（下架约1200行，正常约3500行）
wc -l /tmp/detail.html
```

### 定位恢复时间点

全量失败时，检查增量从哪个时段开始恢复：

```bash
for run in 030001 033001 040001 043001 050001 053001; do
  logs=$(rg -l "pokemon_260115_${run}" ~/.local/share/pueue/task_logs/ 2>/dev/null)
  [ -z "$logs" ] && continue
  warn=0; scraped=0
  for f in $logs; do
    w=$(rg -c "没有获取到" $f 2>/dev/null)
    c=$(rg -oP "'item_scraped_count': \K\d+" $f | tail -1)
    warn=$((warn + w))
    scraped=$((scraped + ${c:-0}))
  done
  # 警告数远小于 scraped 说明已恢复
  if [ $warn -lt $scraped ]; then
    echo "恢复时间点: 260115_${run} (scraped=$scraped, warnings=$warn)"
    break
  else
    echo "260115_${run}: 仍失败 (scraped=$scraped, warnings=$warn)"
  fi
done
```
