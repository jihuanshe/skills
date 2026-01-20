---
name: feishu
description: 'Send messages to Feishu webhook. Triggers: notify feishu, feishu alert, feishu card.'
metadata:
  version: '1'
---

# Sending Feishu Message

通过飞书 Webhook 发送富文本卡片消息。

## 前置条件

环境变量 `FEISHU_WEBHOOK` 已配置为飞书机器人地址：

```bash
FEISHU_WEBHOOK=https://open.feishu.cn/open-apis/bot/v2/hook/xxx
```

## 快速使用

```python
import sys
sys.path.insert(0, 'scripts')  # relative to skill base directory
from feishu import send_card

# 简单通知
send_card(title="部署完成", content="v1.2.3 已上线")

# 带状态的卡片
send_card(
    title="Health Check Failed",
    content="3 spiders reported 0 items",
    template="red",  # red | yellow | green | blue
)

# Markdown 表格
send_card(
    title="Daily Report",
    content="""
| Metric | Value |
|:-------|------:|
| Success | 42 |
| Failed | 3 |
""",
)

# 带按钮
send_card(
    title="New Alert",
    content="Check details",
    buttons=[
        {"text": "View", "url": "https://example.com"},
        {"text": "Dismiss", "url": "https://example.com/dismiss"},
    ],
)
```

## API

```python
def send_card(
    title: str,
    content: str,
    *,
    subtitle: str = "",
    template: Literal["blue", "green", "yellow", "red"] = "blue",
    buttons: list[dict] | None = None,
    webhook_url: str | None = None,  # 默认读取 FEISHU_WEBHOOK
) -> None:
    """发送飞书卡片消息。"""
```

## Markdown 语法

**排版建议**：使用三级标题 `###` 配合表格，视觉层次更清晰。标题和表格之间需要空行：

```markdown
### Pueue Zero Items

| Spider | Task |
|:-------|:-----|
| xxx    | 1833 |
```

**转义字符**：`\` `` ` `` `[` `]` `_` `*` 需用 `\` 转义。表格内额外转义 `|`。

## 限制

- 整个 JSON payload ≤ 19KB
- 自动截断过长内容
