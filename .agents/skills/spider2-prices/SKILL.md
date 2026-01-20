---
name: spider2-prices
description: 'Analyze Spider2 price data. Triggers: price analysis, price trends, cross-site diff.'
metadata:
  version: '1'
---

# Spider2 Price Analysis

用 DuckDB 对爬虫 Parquet 数据进行价格/库存/趋势分析。

## 核心原则

1. **先验证数据质量，再做业务分析。** 否则 JOIN 膨胀、库存假设、格式变化会导致结论严重失真。
2. **输出报告时必须严格遵循 [docs/report_template.md](docs/report_template.md) 模板格式。** 不要自行发挥报告结构。

## Quick Start

```bash
# 使用默认日期（今天 vs 7天前）
./scripts/main.sh

# 指定日期
./scripts/main.sh 260117 260110
```

SQL 模板按功能拆分：

- [01_quality.sql](scripts/01_quality.sql) - 数据质量检查
- [02_trends.sql](scripts/02_trends.sql) - 价格变动分析
- [03_inventory.sql](scripts/03_inventory.sql) - 库存价值计算
- [04_decomposition.sql](scripts/04_decomposition.sql) - 价值分解
- [05_contributors.sql](scripts/05_contributors.sql) - Top 贡献者

报告模板见 [docs/report_template.md](docs/report_template.md)。

## 踩坑清单

### 1. 唯一键问题 ⚠️

`product_url` 不唯一，同一 URL 可能有多条记录。

| 站点 | 原因 | 正确唯一键 |
| :----- | :----- | :----------- |
| dorasuta | 同卡有多个品相 | `url + condition` |
| cardrush | 爬虫 bug 约 0.5% 重复 | `url` (需 DISTINCT) |
| 其他 | 天然唯一 | `url` |

### 2. 字段格式跨天变化 ⚠️

dorasuta 的 `product_condition` 格式在 260110 前后变化（`状態 A` → `状態A`）。

**修复**: 规范化时去除所有空白字符：

```sql
REGEXP_REPLACE(COALESCE(product_condition, ''), '\s+', '', 'g')
```

### 3. 库存字段假设错误 ⚠️

`COALESCE(stock, 1)` 会把缺失当成 1 件，导致库存价值高估。

| 站点 | 数值库存覆盖率 | 处理 |
| :----- | -------------: | :----- |
| cardrush | 99.1% | ✅ 可用 |
| yuyu-tei | 100% | ✅ 可用 |
| hareruya | 96% | ✅ 可用 |
| dorasuta | 42% | ⚠️ 需分口径 |
| mercari | 0% | ❌ 只能用 listing value |

**正确做法**: 输出三口径（$\text{listing\_value}$ / $\text{inventory\_strict}$ / $\text{stock\_coverage\_pct}$）

### 4. 扫全量目录会混入 hotfix ⚠️

`dump_parquet/all/**/*.parquet` 会读到 `260109_fix` 等目录。

**正确做法**: 用目录名读取 `FROM 'dump_parquet/all/260117/**/*.parquet'`

### 4b. ymd 是 DATE 类型 ⚠️

`ymd` 字段是 DATE 类型，不能直接用字符串函数：

```sql
-- ❌ 错误：Binder Error
WHERE ymd NOT LIKE '%_fix'

-- ✅ 正确：先 CAST
WHERE CAST(ymd AS VARCHAR) NOT LIKE '%_fix'
```

### 5. 占位价问题 ⚠️⚠️

cardrush 等存在占位价，严重污染库存价值和归因。

| 占位价 | 出现站点 | 数量 |
| -------: | :--------- | -----: |
| 99999 | cardrush_mtg, mercari_* | ~110 |
| 999999 | cardrush_mtg | ~9 |
| 9999999 | - | 0 |

**必须过滤**:

```sql
WHERE price NOT IN (99999, 999999, 9999999) AND price < 10000000
```

### 6. 极端价格

少量商品价格 $> 1000$ 万，影响均值计算。

**修复**: 用 $\text{median log return}$：

```sql
ROUND((EXP(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY LN(p_new * 1.0 / p_old))) - 1) * 100, 2)
```

### 7. 价值分解缺少交互项 ⚠️

标准价值分解恒等式：$\Delta(p \times s) = s_{\text{old}} \cdot \Delta p + p_{\text{old}} \cdot \Delta s + \Delta p \cdot \Delta s$

必须输出交互项 `delta_interaction`，否则 $\text{价格效应} + \text{数量效应} \neq \text{存量变化}$。

### 8. 口径不一致导致归因错误 ⚠️

同一份报告里混用 `COALESCE(stock, 0)` 和 `COALESCE(stock, 1)` 会导致数字对不上。

**正确做法**: 全流程使用同一口径。

## 常见错误速查

| 错误 | 后果 | 正确做法 |
| :----- | :----- | :--------- |
| 直接 JOIN on url | JOIN 膨胀 | 先确定唯一键 |
| COALESCE(stock, 1) | 库存高估 | 分口径输出 |
| 扫全量 + ymd 过滤 | hotfix 重复 | 用目录名读取 |
| AVG(pct_change) | 被极端值带偏 | $\text{median log return}$ |
| 不过滤占位价 | 归因失真 | 过滤 99999/999999/9999999 |
| 价值分解不含交互项 | 数学不闭合 | 加 $\Delta p \cdot \Delta s$ |
| 混用 stock 口径 | 数字对不上 | 全流程统一 |

## 发布前检查

在报告发布前，用以下命令验证 SQL 质量：

```bash
# 检查 stock 口径是否混用（应全用 0 或全用 1）
rg "COALESCE.*stock" /tmp/T-xxx.md

# 检查是否扫全量后按 ymd 过滤（应改用目录名）
rg "FROM.*all/\*\*.*WHERE.*ymd" /tmp/T-xxx.md

# 检查占位价是否过滤
rg "999999" /tmp/T-xxx.md
```

## DuckDB 常用语法

```sql
-- Parquet glob
FROM 'dump_parquet/all/260117/**/*.parquet'

-- 价格提取
TRY_CAST(REGEXP_REPLACE(product_price, '[^0-9]', '', 'g') AS BIGINT)

-- 去重取最高价
ROW_NUMBER() OVER (PARTITION BY key ORDER BY price DESC) as rn ... WHERE rn = 1

-- 分位数
PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY value)

-- 字符串规范化
REGEXP_REPLACE(COALESCE(field, ''), '\s+', '', 'g')
```

## 数据目录结构

```text
dump_parquet/
├── all/           # 全量快照
│   ├── 260117/    # 日期目录
│   ├── 260110/
│   └── 260109_fix/  # hotfix（需排除）
└── increment/     # 增量数据
```

## 相关技能

- `spider2-health-check`: 爬虫健康检查
- `spider2-troubleshoot`: 爬虫问题排查
