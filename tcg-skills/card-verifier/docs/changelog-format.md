# 变更日志格式

变更日志文件命名：`{原文件名}.changelog.md`

示例：`21278__69771dc3-c8f0-8321-a3b1-5171a39ddbd0.md` → `21278__69771dc3-c8f0-8321-a3b1-5171a39ddbd0.changelog.md`

## 文件结构

```markdown
---
source_file: 21278__69771dc3-c8f0-8321-a3b1-5171a39ddbd0.md
checked_at: 2026-02-06T10:30:00+08:00
total_cards_checked: 5
corrections_made: 2
unverified: 1
---

# Fact Check Changelog

## Summary

- **验证卡牌数**: 5
- **修正数**: 2
- **无法验证**: 1

## Corrections

### 1. ドラパルト ex - 技能效果

- **原文**: 『ダメカン 6 個を、相手のベンチポケモンに好きなようにのせる。』
- **官方**: 『相手のベンチポケモンに、ダメカンを合計 6 個好きなようにのせる。』
- **来源**: https://www.pokemon-card.com/card-search/details.php/card/12345
- **修正位置**: L49

### 2. メガルカリオ ex - HP

- **原文**: HP 280
- **官方**: HP 270
- **来源**: https://www.pokemon-card.com/card-search/details.php/card/67890
- **修正位置**: L188

## Unverified

### ロケット団のドンカラス

- **原因**: 官方数据库搜索无结果
- **建议**: 手动验证或等待数据库更新

## Verified (No Changes)

- サマヨール (カースドボム) ✓
- ヨノワール (カースドボム) ✓
- ヨルノズク (ほうせきさがし) ✓
```

## 字段说明

### Frontmatter

| 字段 | 类型 | 说明 |
|------|------|------|
| `source_file` | string | 原始 MD 文件名 |
| `checked_at` | ISO8601 | 校验时间 |
| `total_cards_checked` | int | 验证的卡牌总数 |
| `corrections_made` | int | 修正数量 |
| `unverified` | int | 无法验证的数量 |

### Corrections 条目

每个修正包含：

- **原文**: 原始 MD 中的内容
- **官方**: 官方数据源的正确内容
- **来源**: 官方数据 URL
- **修正位置**: 原文件行号（L{n}）

### Unverified 条目

无法验证的卡牌，记录原因和建议。
