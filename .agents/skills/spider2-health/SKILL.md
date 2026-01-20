---
name: spider2-health
description: 'Check Spider2 data integrity. Triggers: health check, missing crawlers, row count.'
metadata:
  version: '1'
---

# Validating Spider2 Data

检测 Spider2 爬取数据异常，覆盖全链路：Pueue → Parquet → **实时网站状态**。

## ⚠️ 核心理解：库存同步的特殊性

龙星数据同时服务于**集换价**和**库存同步**：

- **价格爬虫**：数据滞后影响较小，等网站恢复即可
- **库存同步**：**数据滞后会导致用户下单失败**
  - 网站维护 → 我们的库存数据过时 → 用户看到"有货"但实际无法下单
  - 用户体验极差，必须**主动下架**

因此健康检查必须区分两种异常：

| 类型 | 含义 | 紧急程度 | 处理方式 |
| :----- | :----- | :--------: | :--------- |
| 🔴 爬虫失败 | 凌晨爬虫运行时网站就维护 | 中 | 等待恢复，增量可补救 |
| 🟠 **网站当前维护** | 凌晨抓到数据，但现在网站维护 | **高** | **立即手动下架** |

## Workflow

1. **运行验证脚本** → 输出异常信号到 stdout
2. **检查实时网站状态** → 区分"爬虫失败"和"网站当前维护"
3. **对需要下架的类目** → 立即通知运营手动下架
4. **对每个异常** → 加载 `spider2-troubleshoot` skill 调研根因
5. **汇总结果** → 加载 `sending-feishu-message` skill 发送有理有据的通知

## Quick Validation

运行健康检查命令，输出到临时文件以避免截断：

```bash
mise exec --env local -- uv run apps/spider2/tools/health_check.py 2>&1 | tee /tmp/health-check.log
mise exec --env local -- uv run apps/spider2/tools/health_check.py --date 260114 2>&1 | tee /tmp/health-check.log
mise exec --env local -- uv run apps/spider2/tools/health_check.py --baseline 260110 2>&1 | tee /tmp/health-check.log
mise exec --env local -- uv run apps/spider2/tools/health_check.py --history 30 2>&1 | tee /tmp/health-check.log  # 检查30天历史
```

如果输出被截断，用 `Read` 工具读取 `/tmp/health-check.log` 获取完整内容。

脚本会输出异常列表，作为后续根因分析的输入。

## 实时网站状态检查（关键！）

**健康检查脚本只检查"爬虫是否成功"，不检查"当前网站状态"。必须额外执行实时检查。**

### 龙星全类目实时状态检查

```bash
cd apps/spider2

# 龙星所有类目 URL 映射（从爬虫代码提取，不要猜测！）
declare -A URL_MAP=(
  ["pokemon"]="pokemon-card"
  ["yugioh"]="yugioh-jp"
  ["yugioh_rushduel"]="yugioh-rushduel"
  ["mtg"]="mtg"
  ["weissschwarz"]="weiss-schwarz"
  ["onepiece"]="onepiece-cardgame"
  ["duelmasters"]="duelmasters"
  ["vanguard"]="vanguard"
  ["battlespirits"]="battlespirits"
  ["digimon"]="digimon"
  ["unionarena"]="union-arena"
  ["shadowverse"]="shadowverse-evolve"
  ["dragonball"]="dbs-cardgame-fw"      # ⚠️ 不是 dragonball
  ["gundam"]="gundam-gcg"               # ⚠️ 不是 gundam
  ["lorcana"]="disneylorcana"           # ⚠️ 不是 lorcana
  ["ultraman"]="ultraman-cardgame"      # ⚠️ 不是 ultraman
  ["conan"]="conan-cardgame"            # ⚠️ 不是 conan
)

echo "类目,URL路径,当前状态"
for name in "${!URL_MAP[@]}"; do
  path="${URL_MAP[$name]}"
  val=$(timeout 20 mise exec --env local -- uv run scrapy fetch "https://dorasuta.jp/${path}/product-list?cocd=1" -s LOG_LEVEL=ERROR 2>/dev/null | rg -oP 'id="page_max"[^>]*value="\K[^"]*')
  [ -z "$val" ] && echo "${name},${path},🔴 维护中" || echo "${name},${path},🟢 正常(${val}页)"
done | sort
```

### 交叉对比：实时状态 vs 今日 Parquet

```bash
# 获取今日 parquet 数据
duckdb -csv -c "
SELECT
  REPLACE(crawler, 'dorasuta_', '') as name,
  COUNT(*) as today_count
FROM 'dump_parquet/all/$(date +%y%m%d)/**/*.parquet'
WHERE crawler LIKE 'dorasuta%'
GROUP BY 1
ORDER BY 1
"
```

**判断逻辑**：

| 当前网站 | 今日 Parquet | 状态 | 处理 |
| :--------- | :------------- | :----- | :----- |
| 🟢 正常 | > 0 | ✅ 健康 | 无需处理 |
| 🔴 维护 | = 0 | 🔴 爬虫失败 | 等待恢复 |
| 🔴 维护 | > 0 | 🟠 **需下架** | **立即通知运营** |

### 需要下架的类目（紧急！）

当检测到"网站当前维护但今日有数据"时，输出下架 URL 列表：

```bash
# 示例输出格式
echo "以下类目需要手动下架："
echo "| 类目 | URL |"
echo "|:-----|:----|"
echo "| dragonball | https://dorasuta.jp/dbs-cardgame-fw/product-list?cocd=1 |"
echo "| gundam | https://dorasuta.jp/gundam-gcg/product-list?cocd=1 |"
```

## Manual Checks

### 1. Pueue: Zero Items（最关键）

检测完成但无数据的爬虫：

```bash
for id in $(pueue status --json | jq -r '.tasks | to_entries[] | select(.value.created_at > "'$(date +%Y-%m-%d)'") | select(.value.path | contains("spider2")) | .key'); do
  spider=$(pueue status --json | jq -r ".tasks[\"$id\"].original_command" | rg -oP 'crawl \K[^ ]+' 2>/dev/null)
  [ -z "$spider" ] && continue
  cnt=$(rg -oP "'item_scraped_count': \K\d+" ~/.local/share/pueue/task_logs/${id}.log 2>/dev/null | tail -1)
  [ "${cnt:-0}" -eq 0 ] && echo "🔴 $spider (task $id): 0 items"
done
```

> **注意**：任务快速失败（<10 秒）时，Scrapy 不会输出 `item_scraped_count` 统计。此时需查看日志中的 ERROR 信息。

### 2. Parquet: Missing/Dropped Crawlers

与基准日期对比（选择已知正常的日期）：

```bash
duckdb -csv -c "
WITH baseline AS (
  SELECT DISTINCT crawler FROM 'dump_parquet/all/260110/**/*.parquet'
),
today AS (
  SELECT crawler, COUNT(*) as cnt FROM 'dump_parquet/all/$(date +%y%m%d)/**/*.parquet' GROUP BY 1
)
SELECT
  b.crawler,
  COALESCE(t.cnt, 0) as today_count,
  CASE WHEN t.cnt IS NULL OR t.cnt = 0 THEN '🔴 MISSING/ZERO' ELSE '🟢 OK' END as status
FROM baseline b
LEFT JOIN today t ON b.crawler = t.crawler
WHERE t.cnt IS NULL OR t.cnt = 0
ORDER BY b.crawler
"
```

### 3. Parquet: Significant Drops (>50%)

```bash
TODAY=$(date +%y%m%d)
YESTERDAY=$(date -d "yesterday" +%y%m%d 2>/dev/null || date -v-1d +%y%m%d)
duckdb -csv -c "
WITH t AS (SELECT crawler, COUNT(*) as cnt FROM 'dump_parquet/all/${TODAY}/**/*.parquet' GROUP BY 1),
     y AS (SELECT crawler, COUNT(*) as cnt FROM 'dump_parquet/all/${YESTERDAY}/**/*.parquet' GROUP BY 1)
SELECT
  COALESCE(t.crawler, y.crawler) as crawler,
  COALESCE(y.cnt, 0) as yesterday,
  COALESCE(t.cnt, 0) as today,
  ROUND((COALESCE(t.cnt, 0) - COALESCE(y.cnt, 0)) * 100.0 / NULLIF(y.cnt, 0), 1) as pct_change
FROM t FULL OUTER JOIN y ON t.crawler = y.crawler
WHERE COALESCE(t.cnt, 0) < COALESCE(y.cnt, 0) * 0.5
ORDER BY pct_change
"
```

### 4. Historical Trend

检查某爬虫是否连续多天失败：

```bash
CRAWLER="dorasuta_pokemon"
for i in $(seq 5 -1 0); do
  day=$(date -d "-${i} days" +%y%m%d 2>/dev/null || date -v-${i}d +%y%m%d)
  cnt=$(duckdb -noheader -c "SELECT COUNT(*) FROM 'dump_parquet/all/${day}/**/*.parquet' WHERE crawler = '${CRAWLER}'" 2>/dev/null | tr -d '[:space:]')
  echo "$day: ${cnt:-0}"
done
```

## Anomaly Types

| Status | Meaning | 紧急度 | Action |
| -------- | --------- | :------: | -------- |
| 🟠 **STALE** | 网站当前维护但今日有数据 | **高** | **立即通知运营下架** |
| 🔴 ZERO | item_scraped_count = 0 | 中 | 查看 Pueue 日志中的 ERROR |
| 🔴 MISSING | 基准有但今日无 | 中 | 检查 spider 是否运行、cron 配置 |
| 🔴 EMPTY | 增量 Parquet 为空 | 中 | 检查导出链路（见下方判别流程） |
| 🔴 PERSISTENT | 连续缺失 ≥5 天 | 中 | 持久性问题，需要修复 |
| 🟠 DROP >50% | 数据量显著下降 | 低 | 可能正常波动或部分失败 |
| 🟠 RECURRING | 连续缺失 2-4 天 | 低 | 可能是临时维护或间歇性问题 |
| 🟢 OK | 在正常范围内 | - | 无需处理 |

## Root Cause Decision Tree

### 全量爬虫 (🔴 ZERO / 🔴 MISSING)

```text
item_scraped_count = 0?
├── 日志有 ERROR + HTTP 403 → Cloudflare 封禁 → 添加 -s JHS_PROXY=cloudbypass
├── 日志有 ERROR + HTTP 200 + page_max 为空 → 网站后台问题 → 联系站方
├── 日志有 ERROR + HTTP 200 + page_max 正常 → XPath 变化 → 更新选择器
└── 日志无 item_scraped_count（任务 <10s 结束）→ 首页解析失败 → 检查网站可访问性
```

### 增量导出 (🔴 EMPTY)

```text
Parquet 为空？
├── 检查 Pueue spider2_incr 组任务状态
│   └── 任务成功 + item_scraped_count > 0 → 导出链路问题
│       ├── 日志有 "No collections matched filters" → --include regex 错误
│       └── 日志无报错但 Parquet 空 → --suffix 与 task_id 不匹配
└── 任务失败或 item_scraped_count = 0 → 爬虫问题（按全量流程排查）
```

**快速验证导出链路**：

```bash
# 检查 MongoDB 是否有数据
RUN_ID="260115_080001"
mise exec --env local -- python3 -c "
from pymongo import MongoClient; import os
client = MongoClient(os.getenv('MONGO_DB_HOST', 'mongodb://localhost:27017/') + 'market')
print(client['market']['dorasuta_product_detail'].count_documents({'task_id': {'\$regex': '${RUN_ID}\$'}}))
"
```

## Root Cause Analysis

对于验证脚本输出的每个异常，**必须**加载 `spider2-troubleshoot` skill 进行根因分析：

1. 查看 Pueue 日志中的 ERROR 信息
2. 判断失败原因（Cloudflare 封禁、XPath 变化、网站问题等）
3. 记录根因结论

## Notify Results to Feishu

根因分析完成后，**必须**加载 `sending-feishu-message` skill 发送汇总通知。

通知应包含：

- 异常列表（哪些爬虫失败）
- 根因分析结论（为什么失败）
- 建议的修复措施

示例格式：

```markdown
**异常汇总**

| Spider | 根因 | 建议 |
|:-------|:-----|:-----|
| dorasuta_pokemon | 网站后台问题（page_max 为空） | 联系龙星确认商品数据库状态 |
| hareruya2_pokemon_47 | 该类目无在库商品 | 正常现象，无需处理 |
```

需要环境变量 `FEISHU_WEBHOOK` 已配置。

## ⚠️ 关键背景知识（避免弯路）

### 1. 代理配置来源

**运行时配置看 `apps/cron/spider2/crawl_all/main.sh`，不是爬虫代码。**

爬虫代码中的 `DOWNLOADER_MIDDLEWARES` 只是声明支持代理，实际是否启用取决于命令行参数 `-s JHS_PROXY=cloudbypass`。

```bash
# 查看运行时配置
rg "dorasuta|hareruya|cardrush" apps/cron/spider2/crawl_all/main.sh
```

### 2. 代理策略分类

| 网站 | 代理策略 | 原因 |
| ------ | ---------- | ------ |
| dorasuta | **直连（无代理）** | IP 白名单，龙星已开放 |
| cardrush | HTTP 代理 | 需要绕过 Cloudflare |
| hareruya2 | HTTP 代理 | 需要绕过 Cloudflare |
| mercari | HTTP 代理 | 需要绕过 Cloudflare |
| yuyu-tei | HTTP 代理 | 需要绕过 Cloudflare |
| hareruyamtg | HTTP 代理 | 需要绕过 Cloudflare |

**判断方法**：检查 `apps/cron/spider2/crawl_all/main.sh` 中是否有 `-s JHS_PROXY=cloudbypass`

### 3. 两种代理模式（不要混淆）

| 模式 | 触发方式 | 工作原理 | 适用爬虫 |
| ------ | ---------- | ---------- | ---------- |
| HTTP 代理 | `-s JHS_PROXY=cloudbypass` | 通过 `PROXY_CLOUDBYPASS_SERVER` 作为 HTTP 代理 | cardrush, hareruya2, mercari, yuyu-tei |
| API 代理 | `CloudBypassRequest` 类 | 请求发送到 `api.cloudbypass.com`，需要 API Key | dorasuta（代码支持但默认禁用） |

**注意**：dorasuta 代码中虽有 `CloudBypassRequest`，但 `cloudbypass_enabled=False`，实际不走 API。

### 4. URL 来源

**必须使用下表的 URL 路径，不要猜测。**

龙星 URL 路径映射（爬虫名 → 实际路径）：

**⚠️ 路径必须从爬虫代码提取，不要猜测！**

| 爬虫名 | URL 路径 | 备注 |
| :------- | :--------- | :----- |
| dorasuta_pokemon | `pokemon-card` | |
| dorasuta_yugioh | `yugioh-jp` | |
| dorasuta_yugioh_rushduel | `yugioh-rushduel` | |
| dorasuta_mtg | `mtg` | |
| dorasuta_weissschwarz | `weiss-schwarz` | |
| dorasuta_onepiece | `onepiece-cardgame` | |
| dorasuta_duelmasters | `duelmasters` | |
| dorasuta_vanguard | `vanguard` | |
| dorasuta_battlespirits | `battlespirits` | |
| dorasuta_digimon | `digimon` | |
| dorasuta_unionarena | `union-arena` | |
| dorasuta_shadowverse | `shadowverse-evolve` | |
| dorasuta_dragonball | `dbs-cardgame-fw` | ⚠️ 不是 dragonball |
| dorasuta_gundam | `gundam-gcg` | ⚠️ 不是 gundam |
| dorasuta_lorcana | `disneylorcana` | ⚠️ 不是 lorcana |
| dorasuta_ultraman | `ultraman-cardgame` | ⚠️ 不是 ultraman |
| dorasuta_conan | `conan-cardgame` | ⚠️ 不是 conan |

**获取正确路径的命令**：

```bash
# 从爬虫代码提取 URL 路径
for file in apps/spider2/src/spider2/spiders/dorasuta/*.py; do
  name=$(basename "$file" .py)
  [[ "$name" == "__init__" || "$name" == *"_series"* || "$name" == "product_detail" ]] && continue
  url_path=$(rg -oP '/\K[a-z0-9-]+(?=/product-list)' "$file" | head -1)
  echo "dorasuta_${name}: ${url_path}"
done
```

验证龙星类目状态的正确命令：

```bash
# 使用上表的路径，不要猜测
cd apps/spider2
for path in pokemon-card yugioh-jp mtg weiss-schwarz onepiece-cardgame duelmasters; do
  val=$(mise exec --env local -- uv run scrapy fetch "https://dorasuta.jp/${path}/product-list?cocd=1" -s LOG_LEVEL=ERROR 2>/dev/null | rg -oP 'id="page_max"[^>]*value="\K[^"]*')
  [ -z "$val" ] && echo "🔴 $path: 维护中" || echo "🟢 $path: $val"
done
```

如需查找其他爬虫的 URL：

```bash
rg "product-list|collections" apps/spider2/src/spider2/spiders/<site>/
```

### 5. 测试工具选择

**必须用 `scrapy fetch`，不能用 httpx/curl/requests。**

原因：Cloudflare 根据 TLS fingerprint 区分客户端。scrapy 的指纹与 httpx 不同，直接用 httpx 测试会被拦截，误判为 Cloudflare 封禁。

```bash
# 正确：使用 scrapy fetch
cd apps/spider2
timeout 30 mise exec --env local -- uv run scrapy fetch "<URL>" -s LOG_LEVEL=ERROR 2>/dev/null > /tmp/page.html

# 错误：使用 httpx/curl（会被 Cloudflare 拦截）
# curl "https://dorasuta.jp/..."  ← 403 Just a moment...
```

### 6. 常见误判场景

| 误判 | 实际情况 | 如何避免 |
| ------ | ---------- | ---------- |
| "CloudBypass 余额不足" | dorasuta 不走 CloudBypass API | 检查 `apps/cron/spider2/crawl_all/main.sh` 确认代理配置 |
| "网站无法访问" | httpx 被 Cloudflare 拦截 | 用 scrapy fetch 测试 |
| "hareruya.com 超时" | 实际 URL 是 hareruya2.com | 从爬虫代码提取 URL |
| "代理返回 403" | HTTP 代理和 API 代理混淆 | 区分 JHS_PROXY 和 CloudBypassRequest |
| "weiss/onepiece 维护中" | URL 路径错误（weiss→weiss-schwarz） | 使用上方 URL 映射表 |

## URL 测试脚本

使用 scrapy fetch 测试 URL 可达性：

```bash
mise exec --env local -- uv run apps/spider2/tools/check_url.py
mise exec --env local -- uv run apps/spider2/tools/check_url.py --url "https://dorasuta.jp/pokemon-card/product-list?cocd=1"
mise exec --env local -- uv run apps/spider2/tools/check_url.py --url "https://www.hareruya2.com/collections/47" --proxy
```

## 增量爬虫检查

全量爬虫（UTC 00:00）可能因网站临时维护失败，但增量爬虫（UTC 03:00-23:00 每半小时）可以捕获恢复后的数据。

### 1. 检查增量 URL 发现情况

```bash
# 查看今日各时段的 URL 发现数量
for run in 030001 033001 040001 043001 050001 053001 060001; do
  summary="data/product_urls/increment/260115_${run}/summary.json"
  if [ -f "$summary" ]; then
    pokemon=$(jq -r '.pokemon // 0' $summary)
    yugioh=$(jq -r '.yugioh // 0' $summary)
    echo "260115_${run}: pokemon=$pokemon, yugioh=$yugioh"
  fi
done
```

### 2. 检查增量爬取结果（区分成功 vs 失败）

```bash
# 按时段检查 Pokemon 增量爬取
for run in 030001 033001 040001; do
  logs=$(rg -l "pokemon_260115_${run}" ~/.local/share/pueue/task_logs/ 2>/dev/null)
  if [ -n "$logs" ]; then
    total=0; warn=0
    for f in $logs; do
      cnt=$(rg -oP "'item_scraped_count': \K\d+" $f | tail -1)
      w=$(rg -c "没有获取到" $f 2>/dev/null)
      total=$((total + ${cnt:-0}))
      warn=$((warn + w))
    done
    echo "260115_${run}: scraped=$total, warnings=$warn"
  fi
done
```

**判断标准**：

- `warnings ≈ scraped × 2`→ 全部失败（每条 2 个警告：条件列表 + 系列列表）
- `warnings << scraped × 2` → 大部分成功

### 3. 增量 Parquet 按类目统计空标题

```sql
-- 检查增量数据中哪些类目失败
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

### 4. 定位恢复时间点

如果全量失败但增量部分成功，需定位具体恢复时间：

```bash
# 找出从哪个时段开始恢复
for run in 030001 033001 040001 043001 050001 053001; do
  logs=$(rg -l "pokemon_260115_${run}" ~/.local/share/pueue/task_logs/ 2>/dev/null)
  [ -z "$logs" ] && continue
  warn=$(for f in $logs; do rg -c "没有获取到" $f; done | paste -sd+ | bc)
  scraped=$(for f in $logs; do rg -oP "'item_scraped_count': \K\d+" $f | tail -1; done | paste -sd+ | bc)
  # 如果警告数远小于 scraped×2，说明已恢复
  [ $warn -lt $((scraped)) ] && echo "恢复时间点: 260115_${run}" && break
done
```

## 后台维护 vs 商品下架（两种场景区分）

| 场景 | 影响范围 | 列表页 | 详情页 | 日志特征 |
| :----- | :--------- | :------- | :------- | :--------- |
| **后台维护** | 整个类目 100% 失败 | `page_max` 为空 | N/A | `Failed to get page_max_value` |
| **商品下架** | 单个商品失败 | 正常 | 无 `frame product` | `没有获取到条件列表` + `没有获取到系列列表` |

### 后台维护场景验证

```bash
# 对比同一网站不同类目
cd apps/spider2
echo "Pokemon:"; mise exec --env local -- uv run scrapy fetch "https://dorasuta.jp/pokemon-card/product-list?cocd=1" -s LOG_LEVEL=ERROR 2>/dev/null | rg -oP 'id="page_max"[^>]*value="\K[^"]*' || echo "(empty)"
echo "MTG:"; mise exec --env local -- uv run scrapy fetch "https://dorasuta.jp/mtg/product-list?cocd=1" -s LOG_LEVEL=ERROR 2>/dev/null | rg -oP 'id="page_max"[^>]*value="\K[^"]*'
```

如果 MTG 正常而 Pokemon 为空 → 后台维护（轮换维护不同类目）

### 商品下架场景验证

```bash
# 检查详情页是否有 frame product
cd apps/spider2
mise exec --env local -- uv run scrapy fetch "https://dorasuta.jp/pokemon-card/product?pid=654882" -s LOG_LEVEL=ERROR 2>/dev/null > /tmp/detail.html
rg -c 'class="frame product"' /tmp/detail.html
# 0 = 下架，1 = 正常

# 对比页面行数（下架页面约 1200 行，正常约 3500 行）
wc -l /tmp/detail.html
```

## 增量导出链路检查（关键！）

**增量爬虫成功不代表数据可用，必须检查导出链路是否正常。**

### 检查增量 Parquet 是否为空

```bash
# 检查最近 10 个增量批次的 Parquet 文件数
for dir in $(fd -t d . dump_parquet/increment -d1 | sort -r | head -10); do
  run_id=$(basename $dir)
  count=$(fd -e parquet . "$dir" | wc -l)
  [ $count -eq 0 ] && echo "🔴 $run_id: 0 parquet files (导出失效!)" || echo "🟢 $run_id: $count parquet files"
done
```

### 检查 MongoDB 与 Parquet 一致性

```bash
# 检查 MongoDB 中有数据但 Parquet 为空的情况
RUN_ID="260115_080001"

# MongoDB 中的记录数
mongo_count=$(mise exec --env local -- python3 -c "
from pymongo import MongoClient
import os
uri = os.getenv('MONGO_DB_HOST', 'mongodb://localhost:27017/')
client = MongoClient(f'{uri}market?readPreference=secondaryPreferred')
count = client['market']['dorasuta_product_detail'].count_documents({'task_id': {'\$regex': '${RUN_ID}\$'}})
print(count)
")

# Parquet 中的记录数
pq_count=$(duckdb -noheader -c "SELECT COUNT(*) FROM 'dump_parquet/increment/${RUN_ID}/**/*.parquet'" 2>/dev/null | tr -d '[:space:]')

echo "MongoDB: $mongo_count, Parquet: ${pq_count:-0}"
[ "${pq_count:-0}" -eq 0 ] && [ "$mongo_count" -gt 0 ] && echo "🔴 导出链路断裂！"
```

### 导出失效的常见原因

| 症状 | 原因 | 修复 |
| :----- | :----- | :----- |
| "No collections matched filters" | `--include` regex 匹配 collection 名，但 collection 名固定 | 检查 `increment_dorasuta.py` 的 `--include` 参数 |
| MongoDB 有数据但 Parquet 空 | `--suffix` 参数与 `task_id` 不匹配 | 确认 task_id 格式与 suffix 一致 |
| 导出成功但 S3 同步失败 | rclone 配置问题 | 检查 `rclone lsd prod-tigris:prod-python/` |

### 紧急修复：手动重新导出

```bash
# 重新导出指定批次
mise exec --env local -- uv run apps/spider2/tools/increment_dorasuta.py export --run-id 260115_080001
```

## Notes

- **实时状态检查优先**：健康检查脚本只看爬虫结果，必须额外检查当前网站状态
- **库存同步场景特殊**：数据滞后 → 用户下单失败 → 体验极差，必须主动下架
- **Pueue 检查最快**：在源头捕获大部分问题
- **基准日期很重要**：选择所有爬虫正常运行的日期（如 260110）
- **连续失败**：若爬虫连续 2+ 天失败，通常是持久性问题
- **对比组验证**：测试同一网站的其他类目（如 dorasuta MTG vs Pokemon）确认是全站问题还是单类目问题
- **增量可补救全量**：全量失败时检查增量是否已恢复
- **龙星轮换维护**：龙星后台会轮换维护不同类目，状态可能不稳定
- **检查导出链路**：增量爬虫成功 ≠ 数据可用，必须检查 Parquet 是否生成

## 常见翻车点（避坑）

| 翻车点 | 正确做法 |
| :------- | :--------- |
| 只看爬虫是否成功，没检查当前网站状态 | 必须做实时状态检查 |
| 假设每页 50 条商品 | 龙星实际每页 40 条，先抽样验证 |
| 只检查 cocd=1（在库） | 爬虫抓 cocd=1/2/3（在库 + 缺货 + 预约） |
| 今日有数据 = 网站正常 | 今日有数据只说明凌晨正常，不代表现在正常 |
| 看到差异先猜测原因 | 先验证，再下结论 |
| **猜测 URL 路径** | **必须从爬虫代码提取**（gundam→gundam-gcg, dragonball→dbs-cardgame-fw 等） |
