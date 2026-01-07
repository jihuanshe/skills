---
name: using-linear-cli
description: 'Reference for linearis CLI commands. Triggers: Linear management via CLI.'
metadata:
  version: '1'
---

# Using Linear CLI

```bash
# 学习 linearis 工具的能力边界
linearis usage

# 获得当前 git 分支名
git branch --show-current
# 如果分支名类似 `alex/ai-488` 则对应 issue ID 为 `AI-448` 注意大写

# 在知道 issue id 后获取完整上下文
# 用 yq 工具可节省阅读结果的 tokens 因为 JSON 需要转义
linearis issues read AI-448 | yq -p json -o yaml
```
