# turbopuffer 文档索引

`https://turbopuffer.com/docs` 的完整索引及每个页面的内容摘要。

## 核心概念

### /docs（介绍）

- 架构图（客户端 → 缓存 → 对象存储）
- 基于对象存储的设计实现成本效益
- 1M 向量冷查询 p90=444ms，热查询 p50=8ms
- 专注于第一阶段检索

### /docs/architecture（架构）

- Rust 二进制文件路由到 S3/GCS
- NVMe SSD 缓存用于热查询
- 写前日志 (WAL) 保证持久性
- SPFresh 基于质心的 ANN 索引（非 HNSW）
- BM25 倒排索引用于全文搜索
- 默认强一致性（每次查询检查对象存储）
- 多租户服务，支持单租户/BYOC 选项

### /docs/guarantees（保证）

- **持久写入**：API 返回前已提交到对象存储
- **一致读取**：默认；可配置为最终一致性
- **原子批次**：upsert 中的所有写入同时应用
- **条件写入**：原子条件评估
- **ACID**：原子性、一致性、持久性（非完整隔离性）
- **CAP**：对象存储不可达时优先一致性

### /docs/tradeoffs（权衡）

- 高延迟写入（~200ms），高吞吐量（1000+ 次/秒）
- 专注于第一阶段检索（生成候选，客户端重排序）
- 针对准确性优化（90-100% 召回率）
- 一致性读取有 ~10ms 延迟下限
- 偶尔的冷查询（P999 在数百毫秒范围）
- 可扩展至数百万个 namespace
- 仅商业版（无免费层或开源）

### /docs/limits（限制）

| 指标                           | 限制                 |
| ------------------------------ | -------------------- |
| 最大文档数（每个 namespace）   | 500M / 2TB           |
| 最大维度                       | 10,752               |
| 最大写入批次大小               | 512 MB               |
| 最大写入批次频率               | 每个 namespace 1 批次/秒 |
| 每个 namespace 最大并发查询    | 16                   |
| 最大 top_k                     | 10,000               |
| 最大属性值大小                 | 8 MiB                |
| 最大可过滤值大小               | 4 KiB                |
| 最大文档大小                   | 64 MiB               |
| 最大 ID 大小                   | 64 字节              |
| 每个 namespace 最大属性名数量  | 256                  |
| 最大 namespace 名称长度        | 128 字节             |
| 最大 multi-query 子查询数      | 16                   |
| 最大聚合组数                   | 1,200                |

### /docs/regions（区域）

**GCP 区域**：us-central1, us-west1, us-east4, northamerica-northeast2, europe-west3, asia-southeast1, asia-northeast3

**AWS 区域**：ap-southeast-2, ca-central-1, eu-central-1, eu-west-1, us-east-1, us-east-2, us-west-2, ap-south-1

跨云延迟可接受（1-10ms）。出口费用 $0.05-0.09/GB，除非使用 PrivateLink。

### /docs/performance（性能）

优化建议：

1. 选择最近的区域
2. 使用 u64/UUID ID（非字符串 UUID）
3. 非查询属性设置 `filterable: false`（50% 折扣）
4. 使用小 namespace（按租户分区）
5. 使用 `hint_cache_warm` 预热 namespace
6. 较小的向量（512d 比 1536d 快）；f16 比 f32 快
7. 批量写入（最大 512MB）
8. 多进程并发写入
9. 只请求需要的属性
10. 避免 `Glob *pattern*`（全表扫描）；优先使用前缀 glob
11. 使用最终一致性以获得更高吞吐量
12. 避免频繁 patch 大属性

---

## 指南

### /docs/quickstart（快速入门）

Python、TypeScript、Go、Java、Ruby、curl 代码示例。

- 带向量和属性的 upsert
- FTS schema 配置
- 带过滤器的 ANN 查询
- BM25 查询
- 更新和删除

### /docs/vector（向量搜索）

向量搜索指南：

- 距离度量：`cosine_distance`、`euclidean_squared`
- SPFresh 索引（基于质心，针对对象存储优化）
- 自动调优 90-100% 召回率
- 可与过滤器组合

### /docs/fts（全文搜索）

- BM25 评分算法
- 在 schema 中配置 `full_text_search: true`
- 分词器：`word_v3`（默认，Unicode v17）、`word_v2`、`word_v1`、`word_v0`、`pre_tokenized_array`
- 选项：`case_sensitive`、`language`、`stemming`、`remove_stopwords`、`ascii_folding`
- BM25 参数：`k1`（词频饱和度）、`b`（长度归一化）
- 支持的语言：arabic、danish、dutch、english、finnish、french、german、greek、hungarian、italian、norwegian、portuguese、romanian、russian、spanish、swedish、tamil、turkish

### /docs/hybrid（混合搜索）

- 使用 multi-query 结合向量 + BM25
- 客户端排名融合（推荐 RRF）
- 可选重排序（Cohere、ZeroEntropy、MixedBread、Voyage）
- 构建 NDCG 评估套件
- 使用 LLM 进行查询重写
- 分块策略（LangChain、chonkie）
- 上下文检索（Anthropic）
- 多模态嵌入

### /docs/testing（测试）

- 测试时直接使用生产 turbopuffer
- Namespace 几乎免费
- 每次测试使用随机 namespace 名称，测试后删除
- 分离测试/生产组织
- 使用 `copy_from_namespace` 复制真实测试数据

---

## API 参考

### /docs/auth（认证）

- 在 Authorization header 中使用 Bearer token
- 推荐 Gzip 压缩（`Content-Encoding: gzip`、`Accept-Encoding: gzip`）
- 错误格式：`{"status": "error", "error": "message"}`
- 速率限制返回 HTTP 429

### /docs/write（写入 POST /v2/namespaces/:namespace）

**写入类型**：

- `upsert_rows` / `upsert_columns`：创建或覆盖
- `patch_rows` / `patch_columns`：更新特定属性
- `deletes`：按 ID 删除
- `delete_by_filter`：删除匹配文档
- `patch_by_filter`：patch 匹配文档
- `copy_from_namespace`：服务端复制（75% 折扣）

**条件写入**：

- `upsert_condition`、`patch_condition`、`delete_condition`
- 支持 `$ref_new` 引用比较新旧值

**Schema 配置**：

- 类型：`string`、`int`、`uint`、`float`、`uuid`、`datetime`、`bool`、以及各类型数组
- `filterable: false` 获得 50% 折扣
- `full_text_search: true` 用于 BM25
- `regex: true` 用于正则过滤
- 向量类型：`[dims]f32`、`[dims]f16`

**响应**：`rows_affected`、`rows_upserted`、`rows_patched`、`rows_deleted`、`billing`

### /docs/query（查询 POST /v2/namespaces/:namespace/query）

**查询类型**：

- 向量搜索 (ANN)：`["vector", "ANN", [0.1, ...]]`
- 精确搜索 (kNN)：`["vector", "kNN", [0.1, ...]]`（需要过滤器）
- BM25：`["text", "BM25", "query string"]`
- 按属性排序：`["timestamp", "desc"]`
- 聚合：`["Count"]`、`["Sum", "attr"]`

**FTS 运算符**：`Sum`、`Max`、`Product`（用于字段权重）

**过滤器**：

- 布尔：`And`、`Or`、`Not`
- 比较：`Eq`、`NotEq`、`Lt`、`Lte`、`Gt`、`Gte`
- 集合：`In`、`NotIn`、`Contains`、`NotContains`、`ContainsAny`、`NotContainsAny`
- 数组：`AnyLt`、`AnyLte`、`AnyGt`、`AnyGte`
- 模式：`Glob`、`NotGlob`、`IGlob`、`NotIGlob`、`Regex`
- 文本：`ContainsAllTokens`、`ContainsTokenSequence`

**Multi-query**：最多 16 个子查询原子执行

**一致性**：`{"level": "strong"}`（默认）或 `{"level": "eventual"}`

**多样化**：`limit.per` 限制每个属性值的结果数

**分页**：按属性排序查询时，推进 order 属性上的过滤器

### /docs/metadata（元数据 GET /v1/namespaces/:namespace/metadata）

返回：`schema`、`approx_logical_bytes`、`approx_row_count`、`created_at`、`updated_at`、`encryption`、`index`（status、unindexed_bytes）

### /docs/export（导出）

使用查询 API 分页，推进 `id` 过滤器：

```python
result = ns.query(rank_by=("id", "asc"), filters=("id", "Gt", last_id), top_k=1000)
```

### /docs/warm-cache（缓存预热 GET /v1/namespaces/:namespace/hint_cache_warm）

通知 turbopuffer 准备低延迟请求。如果已经热了则免费。

### /docs/namespaces（列出 namespace GET /v1/namespaces）

分页列出 namespace。参数：`cursor`、`prefix`、`page_size`（最大 1000）

### /docs/delete-namespace（删除 namespace DELETE /v2/namespaces/:namespace）

删除 namespace 及所有文档。不可恢复。

### /docs/recall（召回率 POST /v1/namespaces/:namespace/_debug/recall）

评估召回率：采样随机向量，比较 ANN 与穷举搜索。
参数：`num`（采样数）、`top_k`、`filters`、`queries`
返回：`avg_recall`、`avg_exhaustive_count`、`avg_ann_count`

---

## 企业功能

### /docs/security（安全）

- SOC 2 Type 2 认证
- GDPR 和 CCPA 合规（提供 DPA）
- HIPAA（提供 BAA）
- 传输加密（TLS 1.2+）和静态加密（AES-256）
- 客户托管加密密钥 (CMEK)
- 私有网络（PrivateLink、Private Service Connect）
- Dashboard SSO（Scale/Enterprise 计划）
- 子处理器：AWS、GCP

### /docs/cmek（客户托管加密密钥）

- Enterprise 计划功能
- 来自客户 KMS 的每个 namespace 加密密钥
- 支持 GCP Cloud KMS 和 AWS KMS
- 加密密钥在写入时设置，不可更改
- 密钥轮换：新写入使用最新版本；旧数据保持旧版本
- 通过 `copy_from_namespace` 使用不同密钥重新加密

### /docs/backups（跨区域备份）

- 使用 `copy_from_namespace` 进行服务端复制
- 75% 写入折扣
- 同一云提供商内跨区域
- 使用 cron 调度；清理旧备份

### /docs/private-networking（私有网络）

- AWS PrivateLink、GCP Private Service Connect
- 仅 Enterprise 计划
- 可选强制（阻止公共端点）
- 端点 URL：`https://privatelink.<region>.turbopuffer.com`

### /docs/vdp（漏洞披露）

- 范围：Dashboard、数据库 API、客户端 SDK
- 报告至 <security@turbopuffer.com>

---

## 路线图亮点 (/docs/roadmap)

**即将推出**：

- 新查询定价
- 更快的缓存预热
- Dashboard 改进
- 更多 FTS 功能（高亮、边输入边搜索）
- 更多聚合函数
- 后期交互支持
- 快照读取
- 多向量列
- 嵌套属性

**近期更新**（2025）：

- FTSv2（20 倍更快）
- kNN 精确搜索
- 跨区域备份
- 分组聚合
- 条件写入
- Multi-query API
- f16 向量
- Ruby、Go、Java 客户端
