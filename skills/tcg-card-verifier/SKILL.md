---
name: tcg-card-verifier
description: 'Verify and correct AI-generated card guide MD files against official sources. Triggers: verify card, fact check, correct guide, card verifier.'
metadata:
  version: '4'
---

# TCG Fact Check

验证并修正 TCG 卡牌攻略 Markdown 文件中的事实性错误。

## 触发场景

支持两类文件：

- `data/local/deck/{game}/{env}/{lang}/*.md` — AI 生成的 deck guide（最常见）
- `packages/deck/src/deck/infra/templates/shared/env_brief/{env}/*.md` — 环境概览模板

当用户提供的路径不明确（如只说"验证 pkm 330"）时，**用 `AskUserQuestion` 确认**：

- 验证 `data/local/` 下的 deck guide 文件？
- 验证 `templates/shared/env_brief/` 下的环境概览？
- 两者都验证？

## 执行方式

**始终使用 `Task` 工具委托 sub-agent 执行验证**。主 agent 负责：

1. 识别待验证文件（单个或批量）
2. 根据 `game_key` 选择对应 prompt 模板
3. 启动 sub-agent 并汇总结果

### 卡牌分级验证策略

为避免全量网页验证耗时过长，sub-agent 应对卡牌进行分级：

- **必须网页验证**：文件中引用了具体效果数值（伤害值、能量数、ダメカン数等）的卡牌
- **免验证（well-known）**：通用泛用卡（ボスの指令、ふしぎなアメ、ジャッジマン 等），在 changelog 中标记 `[WELL-KNOWN]`

## Sub-agent Prompt 模板

### PKM (Pokemon TCG)

``` Markdown
验证 Pokemon TCG 卡牌报告：{FILE_PATH}

## 禁止事项

- **禁止使用 `WebSearch` 工具** - 搜索结果会返回 pokemon-card.com，该网站文本丢失能量符号
- **禁止直接引用 pokemon-card.com 网页文本** - 能量图标无法被 WebFetch 读取，会导致验证错误
- **禁止猜测 URL** - 必须通过搜索页面获取实际卡牌页面链接

> ✅ 允许使用 `WebFetch` 工具直接访问带搜索参数的 URL（如 `limitlesstcg.com/cards?q={name}`），这与 `WebSearch` 工具不同。

## 数据源（按顺序执行，前一个成功则停止）

### 1. Limitless TCG（首选）

搜索卡牌：用 `WebFetch` 访问 `https://limitlesstcg.com/cards?q={卡牌名}&lang={lang}`

根据卡牌名语言选择 `lang` 参数：
- 日文名 → `lang=jp`
- 英文名 → `lang=en`
- 其他语言 → 先尝试 `lang=en`，无结果再尝试 `lang=jp`

从搜索结果进入卡牌详情页，能量格式示例：
- `[C]` = 無色, `[R]` = 炎, `[W]` = 水, `[L]` = 雷
- `[P]` = 超, `[F]` = 闘, `[D]` = 悪, `[M]` = 鋼, `[G]` = 草

**关键**：如果效果文本包含 `[F] Energy` 则是「基本闘エネルギー」限定，不是「基本エネルギー」。

### 2. 52poke 百科（Limitless 找不到时）

用 `WebFetch` 访问 https://wiki.52poke.com/wiki/{卡牌中文名}（TCG）

### 3. 找不到时：标记为无法验证

如果 Limitless 和 52poke 都没有该卡牌（如新发售的卡包）：
- 在 changelog 中标记 `[UNVERIFIED]`，记录原因
- **不做修正**，保留原文

> ⚠️ pokemon-card.com 不可用：搜索页是 JS 渲染，详情页丢失能量符号

## 卡牌分级验证策略

- **必须网页验证**：引用了具体效果数值（伤害值、能量数、ダメカン数等）的卡牌
- **免验证（well-known）**：通用泛用卡（ボスの指令、ふしぎなアメ、ジャッジマン 等），在 changelog 中标记 `[WELL-KNOWN]`

## 执行流程

1. 读取文件，列出所有卡牌效果声明
2. 按分级策略，对需验证的卡按上述顺序查询（Limitless → 52poke → 标记无法验证）
3. 对比时重点检查能量类型限定（常见错误：遗漏「闘」「草」「鋼」「悪」等）
4. 用 `Edit` 工具修正错误
5. 创建 `{原文件名}.changelog.md`（格式见下方完整示例）

## Changelog 完整示例

```markdown
---
source_file: 21278__69771dc3-c8f0-8321-a3b1-5171a39ddbd0.md
checked_at: '2026-02-09T12:00:00+00:00'
total_cards_checked: 19
corrections_made: 1
unverified: 0
---

# Fact Check Changelog

## Corrections

### メガルカリオ ex - はどうづき (Line 189) [CORRECTED]

- **Before:** `『トラッシュから「基本エネルギー」を3枚まで…ベンチポケモンに好きなようにつける』`
- **After:** `『トラッシュから「基本闘エネルギー」を3枚まで…ベンチポケモンに好きなようにつける』`
- **Reason:** Official card text specifies `基本[F]エネルギー` (Basic Fighting Energy), not generic `基本エネルギー`.
- **Source:** [メガルカリオ ex M1L/29](https://limitlesstcg.com/cards/jp/M1L/29)

## Verified (No Changes)

| Card | Effect | Source | Result |
|------|--------|--------|--------|
| ドラパルト ex - ファントムダイブ | 200 + ダメカン 6 個 | [TWM/130](https://limitlesstcg.com/cards/TWM/130) | Correct |
| サマヨール - カースドボム | 自滅 + ダメカン 5 個 | [SFA/19](https://limitlesstcg.com/cards/SFA/19) | Correct |

## Well-Known Cards [WELL-KNOWN]

ボスの指令，ふしぎなアメ，ジャッジマン，なかよしポフィン，夜のタンカ
``` Markdown

## 返回

验证卡牌数: X | 修正数: X | 无法验证: X
修正内容简述

```

### YGO (Yu-Gi-Oh!)

``` Markdown
验证 Yu-Gi-Oh! 卡牌报告：{FILE_PATH}

## 数据源

1. **首选 db.ygorganization.com** - 官方数据库
2. **备选 yugipedia.com** - 社区维基

## 执行流程

1. 读取文件，提取卡牌效果声明
2. 查询官方数据对比
3. 用 `Edit` 工具修正错误
4. 创建 changelog.md（格式同 PKM 模板中的完整示例）

返回：验证卡牌数 | 修正数 | 无法验证数
```

### LoL (Runeterra)

``` Markdown
验证 Legends of Runeterra 卡牌报告：{FILE_PATH}

## 数据源

1. **首选 runeterra.ar** - 社区数据库
2. **备选 mobalytics.gg/lor**

## 执行流程

同 PKM 流程，创建 changelog.md（格式同 PKM 模板中的完整示例）

返回：验证卡牌数 | 修正数 | 无法验证数
```

## 批量验证

当用户要求验证某个环境下的所有 meta 文件时，**并发启动多个 sub-agent**：

1. 用 `Glob` 收集目标目录下所有 `.md` 文件（排除 `.changelog.md`）
2. 在单条消息中并发启动多个 `Task`（每个 sub-agent 处理一个文件）
3. 单次并发上限 5 个 sub-agent，超过则分批等待前一批完成后启动下一批
4. 所有 sub-agent 完成后，主 agent 汇总结果

``` python
# 伪代码
files = Glob("data/local/deck/{game}/{env}/{lang}/*.md", exclude="*.changelog.md")

for batch in chunks(files, 5):
    # 在同一条消息中并发启动（Claude Code 支持单消息多 Task 调用）
    parallel [Task(prompt=TEMPLATE.format(FILE_PATH=f)) for f in batch]
    # 等待本批完成后启动下一批
```

## 注意事项

- 攻略分析、策略建议属于主观内容，不作为"错误"修正
- 若官方数据无法确认，标记为 `[UNVERIFIED]` 而非直接修正
- 搜索失败时记录原因，继续处理下一张卡
