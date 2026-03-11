# YGO 卡牌验证流程

## 验证方式

直接使用 `web_search` + `read_web_page`，无需图片验证。

**原因**：Yugipedia 提供完整的多语言效果文本，不存在符号遗漏问题。

## 验证流程

### Step 1: 搜索卡牌

```text
site:yugipedia.com {卡牌名}
```

支持任意语言的卡牌名搜索（英文/日文/中文）。

### Step 2: 读取详情页

使用 `read_web_page` 获取卡牌详情。

URL 格式：

```text
https://yugipedia.com/wiki/{卡牌英文名}
```

### Step 3: 提取多语言文本

从 "Other languages" 表格提取：

| Language | Name | Card text |
|----------|------|-----------|
| Japanese | ブラック・マジシャン | 魔法使いとしては... |
| Simplified Chinese | 黑魔导 | 作为魔法使... |
| English | Dark Magician | The ultimate wizard... |

## 数据源

| 网站 | 用途 | 备注 |
|------|------|------|
| yugipedia.com | 主数据源 | 中日英韩多语言 |
| ygocdb.com | 备用 | 仅中文 |
| db.yugioh-card.com | 备用 | Konami 官方，需切换 locale |
