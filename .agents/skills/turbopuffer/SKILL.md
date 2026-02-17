---
name: turbopuffer
description: '构建向量与全文搜索。触发词: turbopuffer, vector search, BM25, hybrid search, embedding search。'
metadata:
  version: '1'
---

# 使用 turbopuffer 构建搜索 (Python)

turbopuffer 是基于对象存储的高速向量 + 全文搜索引擎，支持混合搜索、过滤，可扩展至 1000 亿+ 向量。

## 文档参考

查询 `https://turbopuffer.com/docs/<page>`:

| 页面                     | 描述                               |
| ------------------------ | ---------------------------------- |
| `/docs`                  | 介绍与架构概述                     |
| `/docs/quickstart`       | 快速入门代码示例                   |
| `/docs/architecture`     | WAL、缓存、SPFresh 索引内部机制    |
| `/docs/guarantees`       | 持久性、一致性、ACID 属性          |
| `/docs/tradeoffs`        | 设计取舍与适用场景                 |
| `/docs/limits`           | 速率限制、大小限制、配额           |
| `/docs/regions`          | 可用区域 (AWS/GCP)                 |
| `/docs/performance`      | 性能优化建议                       |
| `/docs/security`         | SOC2、HIPAA、CMEK、私有网络        |
| **指南**                 |                                    |
| `/docs/vector`           | 向量搜索指南                       |
| `/docs/fts`              | 全文搜索 (BM25) 指南               |
| `/docs/hybrid`           | 混合搜索 (向量 + BM25)             |
| `/docs/testing`          | 测试策略                           |
| **API**                  |                                    |
| `/docs/auth`             | 认证与编码                         |
| `/docs/write`            | 写入 API (upsert, patch, delete, schema) |
| `/docs/query`            | 查询 API (ANN, kNN, BM25, filters, aggregations) |
| `/docs/metadata`         | Namespace 元数据端点               |
| `/docs/export`           | 导出文档                           |
| `/docs/warm-cache`       | 缓存预热以降低延迟                 |
| `/docs/namespaces`       | 列出 namespaces                    |
| `/docs/delete-namespace` | 删除 namespace                     |
| `/docs/recall`           | 召回率评估端点                     |
| **企业功能**             |                                    |
| `/docs/cmek`             | 客户托管加密密钥                   |
| `/docs/backups`          | 跨区域备份                         |
| `/docs/private-networking` | PrivateLink / Private Service Connect |
| `/docs/roadmap`          | 更新日志与即将推出的功能           |

## 黄金路径：基础向量搜索

```python
import turbopuffer
import os

tpuf = turbopuffer.Turbopuffer(
    api_key=os.getenv("TURBOPUFFER_API_KEY"),
    region="gcp-us-central1",  # 选择最近的区域
)

ns = tpuf.namespace("my-namespace")

# 写入文档
ns.write(
    upsert_rows=[
        {"id": 1, "vector": [0.1, 0.2, ...], "title": "Doc 1", "category": "A"},
        {"id": 2, "vector": [0.3, 0.4, ...], "title": "Doc 2", "category": "B"},
    ],
    distance_metric="cosine_distance",
)

# 向量搜索 + 过滤
result = ns.query(
    rank_by=("vector", "ANN", query_vector),
    top_k=10,
    filters=("category", "Eq", "A"),
    include_attributes=["title"],
)
```

## 最佳实践

### 1. Namespace 设计（证据：/docs/performance, /docs/tradeoffs）

**结论**：使用多个小 namespace，而非一个大 namespace。

**证据**：

- "经验法则是让 namespace 尽可能小，除非需要频繁同时查询多个"
- "更小的 namespace 查询和索引都更快"
- "turbopuffer 可扩展至数万亿文档、数亿个 namespace"
- 单个 namespace 上限：500M 文档 / 2TB

**实践**：

```python
# ✅ 正确：每个租户一个 namespace
ns = tpuf.namespace(f"tenant-{tenant_id}")

# ❌ 错误：单一 namespace + 租户过滤
ns = tpuf.namespace("all-tenants")
ns.query(filters=("tenant_id", "Eq", tenant_id), ...)
```

### 2. 缓存预热（证据：/docs/warm-cache, /docs/architecture）

**结论**：在延迟敏感查询前预热 namespace。

**证据**：

- 冷查询：1M 文档 p50=343ms
- 热查询：1M 文档 p50=8ms
- "许多应用可以预热 namespace，让用户永远不会遇到冷延迟"

**实践**：

```python
# 用户会话开始时预热缓存
ns.hint_cache_warm()

# 或发送预查询
ns.query(rank_by=("id", "asc"), top_k=1)
```

### 3. 批量写入（证据：/docs/write, /docs/performance, /docs/limits）

**结论**：将文档批量写入以提高吞吐量并节省成本。

**证据**：

- 写入延迟 500kB 批次 p50=285ms
- 最大批次大小：512MB
- "强烈建议使用大批量写入以最大化吞吐量并最小化成本"
- 批量写入可享受高达 50% 折扣

**实践**：

```python
# ✅ 正确：批量写入多个文档
ns.write(upsert_rows=documents_batch)  # 最大 512MB

# ❌ 错误：逐条写入
for doc in documents:
    ns.write(upsert_rows=[doc])
```

### 4. Schema 配置（证据：/docs/write, /docs/performance）

**结论**：将不需要过滤的属性标记为 `filterable: false`，可获得 50% 存储折扣。

**证据**：

- "未过滤的属性不会建立索引，因此按 50% 折扣计费"
- "对于大型属性值，如存储原始文本块或图片，这可以显著提高性能并降低成本"

**实践**：

```python
ns.write(
    upsert_rows=[...],
    schema={
        "raw_content": {"type": "string", "filterable": False},  # 50% 折扣
        "searchable_text": {"type": "string", "full_text_search": True},
    },
    distance_metric="cosine_distance",
)
```

### 5. ID 类型（证据：/docs/performance, /docs/write）

**结论**：使用 u64 或原生 UUID 类型，而非字符串 ID。

**证据**：

- "UUID 编码为字符串是 36 字节，而原生 UUID 类型是 16 字节"
- "u64 更小，只有 8 字节"
- "ID 越小，速度越快"

**实践**：

```python
# ✅ 正确：使用整数 ID
ns.write(upsert_rows=[{"id": 1, ...}])

# ✅ 正确：在 schema 中使用 UUID 类型
ns.write(
    upsert_rows=[{"id": "550e8400-e29b-41d4-a716-446655440000", ...}],
    schema={"id": "uuid"},
)

# ❌ 错误：字符串 UUID 但没有指定 schema
ns.write(upsert_rows=[{"id": "550e8400-e29b-41d4-a716-446655440000", ...}])
```

### 6. 向量维度（证据：/docs/performance, /docs/write）

**结论**：优先使用较小的向量和 f16 而非 f32，以提高速度和降低成本。

**证据**：

- "较小的向量搜索更快，如 512 维比 1536 维更快"
- "f16 比 f32 更快"
- "对于支持量化感知训练的模型，int8 输出与 f32 精度相当"

**实践**：

```python
# 使用 f16 向量（需要在首次写入时指定 schema）
ns.write(
    upsert_rows=[...],
    schema={"vector": {"type": "[512]f16", "ann": True}},
    distance_metric="cosine_distance",
)
```

### 7. 一致性权衡（证据：/docs/query, /docs/tradeoffs）

**结论**：当需要低于 10ms 延迟时，使用最终一致性。

**证据**：

- 强一致性：~10ms 下限（对象存储检查）
- 最终一致性：99.9923% 的查询完全一致
- "数据可能最多延迟 60 秒"

**实践**：

```python
# 默认：强一致性
result = ns.query(rank_by=..., consistency={"level": "strong"})

# 高吞吐量：最终一致性
result = ns.query(rank_by=..., consistency={"level": "eventual"})
```

### 8. 混合搜索（证据：/docs/hybrid, /docs/hybrid-search）

**结论**：使用 multi-query 结合向量 + BM25，然后在客户端进行融合/重排序。

**证据**：

- "将搜索逻辑保存在 `{search.py, search.ts}` 中"
- "使用 turbopuffer 进行初步检索，将数百万结果缩减到数十个，然后进行排名融合和重排序"
- Multi-query API 可原子执行最多 16 个查询

**实践**：

```python
# Multi-query 混合搜索
result = ns.query(
    queries=[
        {"rank_by": ("vector", "ANN", query_vector), "top_k": 20},
        {"rank_by": ("text", "BM25", query_text), "top_k": 20},
    ],
)

# 客户端 Reciprocal Rank Fusion
def rrf_score(ranks: list[int], k: int = 60) -> float:
    return sum(1 / (k + r) for r in ranks)
```

### 9. 属性选择（证据：/docs/query, /docs/performance）

**结论**：只请求需要的属性。

**证据**：

- "返回的数据越多，速度越慢"
- "确保只指定你需要的属性"

**实践**：

```python
# ✅ 正确：只请求需要的属性
result = ns.query(
    rank_by=...,
    include_attributes=["title", "url"],
)

# ❌ 错误：请求所有属性
result = ns.query(
    rank_by=...,
    include_attributes=True,
)
```

### 10. 过滤器设计（证据：/docs/query, /docs/performance）

**结论**：使用对倒排索引友好的过滤器；避免昂贵的模式。

**证据**：

- 倒排索引使大型交集查询快速
- "`Glob tpuf*` 被编译为优化的前缀扫描"
- "`Glob *tpuf*` 或 `IGlob` 可能会扫描每个文档"

**实践**：

```python
# ✅ 正确：前缀 glob
filters=("path", "Glob", "docs/*")

# ❌ 错误：中缀 glob（全表扫描）
filters=("path", "Glob", "*docs*")

# ✅ 正确：使用 In 进行多个精确匹配
filters=("category", "In", ["A", "B", "C"])
```

## 反模式

### ❌ 单一巨型 Namespace

```python
# 错误：所有数据放在一个 namespace
ns = tpuf.namespace("all-data")
ns.query(filters=("tenant", "Eq", tenant_id))
```

### ❌ 逐条写入文档

```python
# 错误：N 次网络往返
for doc in documents:
    ns.write(upsert_rows=[doc])
```

### ❌ 请求所有属性

```python
# 错误：返回所有内容包括向量
ns.query(include_attributes=True)
```

### ❌ 忽略缓存预热

```python
# 错误：用户遇到冷查询延迟
result = ns.query(...)  # 首次查询很慢
```

## 测试策略

**证据**：/docs/testing

- 测试时直接使用生产环境 turbopuffer（创建 namespace 几乎免费）
- 每次测试使用随机 namespace 名称，测试后删除
- 在 dashboard 中分离测试/生产组织
- 使用 `copy_from_namespace` 复制生产数据用于测试

```python
import uuid

def test_search():
    ns = tpuf.namespace(f"test-{uuid.uuid4()}")
    try:
        ns.write(upsert_rows=[...])
        result = ns.query(...)
        assert len(result.rows) > 0
    finally:
        ns.delete_all()
```

## 自验证循环（Self-Verification Loop）

**结论**：写入后不能仅依赖返回值，必须通过查询闭环验证数据正确落库。

**证据**：

- `/docs/guarantees`："API 返回前已提交到对象存储"——但这只保证持久性，不保证字段/类型/过滤可用性符合预期
- `/docs/write`：`rows_affected` 返回受影响行数，但不验证内容正确性

**实践**：

```python
from .templates import write_with_verification, query_with_retry

# 写入并验证
result = write_with_verification(
    ns,
    rows=rows_to_sdk_payload(documents),
    distance_metric="cosine_distance",
    verify=True,  # 启用验证
)

if not result.verified:
    raise RuntimeError(f"Write verification failed: {result.verified_ids}")

# 或手动验证
doc_ids = [doc["id"] for doc in documents]
ns.write(upsert_rows=documents, distance_metric="cosine_distance")

# 闭环验证：查询回写入的 ID
verify_result = ns.query(
    filters=("id", "In", doc_ids),
    rank_by=("id", "asc"),
    top_k=len(doc_ids),
)
verified_ids = {row.id for row in verify_result.rows or []}
assert verified_ids == set(doc_ids), f"Missing: {set(doc_ids) - verified_ids}"
```

**验证层次**：

1. **billing info**：`result.billing.billable_logical_bytes_written` 确认有数据写入
2. **ID 存在性**：查询 `("id", "In", doc_ids)` 确认所有文档存在
3. **内容抽样**：随机抽取文档验证字段值正确
4. **元数据增量**：`ns.metadata().approx_row_count` 确认文档数增加

## 错误处理与重试

**结论**：使用指数退避重试处理瞬态错误。

**实践**：

```python
from .templates import with_retry, TurbopufferWriteError
import turbopuffer

try:
    result = with_retry(
        lambda: ns.write(upsert_rows=documents),
        max_attempts=3,
        base_delay=1.0,
    )
except TurbopufferWriteError as e:
    logfire.error("turbopuffer.write_failed", error=str(e))
    raise

# 或手动处理
try:
    ns.query(rank_by=..., top_k=10)
except turbopuffer.RateLimitError:
    # 429: 等待后重试
    time.sleep(backoff)
except turbopuffer.AuthenticationError:
    # 401: API key 无效
    raise
except turbopuffer.NotFoundError:
    # 404: namespace 不存在，需要先写入
    ns.write(upsert_rows=[...])
```

## 可观测性

使用 logfire span 包装 turbopuffer 调用：

```python
import logfire

with logfire.span("turbopuffer.query", namespace=ns_name, top_k=10):
    result = ns.query(rank_by=..., top_k=10)
```

## 限制快速参考

| 指标                          | 限制         |
| ----------------------------- | ------------ |
| 每个 namespace 最大文档数     | 500M / 2TB   |
| 最大维度                      | 10,752       |
| 最大批次大小                  | 512 MB       |
| 每个 namespace 最大并发查询   | 16           |
| 最大 top_k                    | 10,000       |
| 最大属性值大小                | 8 MiB        |
| 每个 namespace 最大属性名数量 | 256          |

## 审查规则

审查代码时，**必须**：

1. **逐项检查下方清单**，每项报告 ✅ 或 ❌
2. **同时报告合规项和问题项**，不能只报问题
3. **引用证据**：每个建议必须引用本 skill 中的"证据"章节

输出格式示例：

```text
| 检查项 | 状态 | 说明 |
|--------|------|------|
| namespace 设计 | ✅ | 按 game_key 分 namespace（证据：§1）|
| 批量写入 | ✅ | BATCH_SIZE=1000（证据：§3）|
| filterable: false | ❌ | 未配置（证据：§4）|
| ... | ... | ... |
```

## 检查清单

| #  | 检查项                               | 证据章节         |
| -- | ------------------------------------ | ---------------- |
| 1  | 按租户/自然分区划分 namespace        | §1 Namespace 设计 |
| 2  | 批量写入（而非逐条）                 | §3 批量写入       |
| 3  | 非查询属性设置 `filterable: false`   | §4 Schema 配置    |
| 4  | 使用 u64/UUID 类型作为 ID            | §5 ID 类型        |
| 5  | 使用 f16 向量（若精度允许）          | §6 向量维度       |
| 6  | 只请求需要的属性                     | §9 属性选择       |
| 7  | 延迟敏感流程进行缓存预热             | §2 缓存预热       |
| 8  | 混合搜索使用客户端 RRF 融合          | §8 混合搜索       |
| 9  | logfire span 包装 turbopuffer 调用   | 可观测性          |
| 10 | 写入后有自验证循环                   | 自验证循环        |
| 11 | 瞬态错误有重试机制                   | 错误处理与重试    |
| 12 | 无反模式（单一大 namespace / 逐条写入 / 请求所有属性） | 反模式 |

## 模板文件

| 模板                            | 用途                                |
| ------------------------------- | ----------------------------------- |
| `templates/basic_vector_search.py` | 基础向量搜索                       |
| `templates/batch_upsert.py`        | 批量写入（并行）                   |
| `templates/conditional_writes.py`  | 条件写入（乐观并发）               |
| `templates/hybrid_search.py`       | 混合搜索（向量 + BM25 + RRF）      |
| `templates/multi_tenant.py`        | 多租户（namespace-per-tenant）     |
| `templates/schema_optimized.py`    | Schema 优化（f16、UUID、filterable:false） |
| `templates/verify_writes.py`       | 完整自验证循环示例                 |
