---
name: pr-comments
description: 'Resolve PR review feedback. Triggers: fix PR comments, address review.'
metadata:
  version: '1'
---

# Resolve PR Comments

获取 GitHub PR 的所有评审意见并生成结构化解决方案。

## 使用场景

- 收到 PR 评审意见后需要系统性处理时
- 需要将评审反馈转化为具体操作计划时

## 环境要求

需要配置 `gh` CLI 并完成认证。

## 运行

从 skill 目录执行：

```bash
bash scripts/resolve-pr-comments.sh <pr-number-or-url>
```

## 参数

- `<pr-number-or-url>`: PR 编号或完整 URL

## 示例

```bash
builtin://skills/scripts/resolve-pr-comments.sh 123
builtin://skills/scripts/resolve-pr-comments.sh https://github.com/owner/repo/pull/123
```

## 输出

脚本会获取 PR 详情和所有评审意见，并输出一份指导 prompt，引导 agent：

1. 搭建对 PR 的整体认知
2. 分析所有反馈并分类（bug、design、performance、security、tests 等）
3. 为每条反馈提出解决方案
4. 制定实施计划
5. 起草给评审者的回复模版

最终输出包含：

- PR summary
- Open questions
- Feedback analysis
- Resolution proposals (by comment)
- Implementation plan
- Suggested reviewer replies
