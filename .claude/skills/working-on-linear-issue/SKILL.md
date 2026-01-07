---
name: working-on-linear-issue
description: 'Fetch Linear issue and generate structured implementation plan. Triggers: Linear issue ID or URL to start working on.'
metadata:
  version: '1'
---

# Work on Linear Issue

获取 Linear issue 详情并生成结构化实施方案。

## 使用场景

- 开始处理一个新的 Linear issue 时
- 需要深入理解任务并制定实施计划时

## 环境要求

需要设置 `LINEAR_API_KEY` 环境变量。

## 运行

从 skill 目录执行：

```bash
bash scripts/work-on-linear-issue.sh <issue-id>
```

## 参数

- `<issue-id>`: Linear issue 的缩写（如 `AB-123`）或完整 URL

## 示例

```bash
builtin://skills/scripts/work-on-linear-issue.sh MC-91
builtin://skills/scripts/work-on-linear-issue.sh https://linear.app/team/issue/MC-91/issue-title
```

## 输出

脚本会获取 issue 详情（标题、描述、状态、评论等），并输出一份指导 prompt，引导 agent：

1. 理解任务需求和约束
2. 映射到代码库相关模块
3. 分析当前设计质量
4. 制定详细方案和 TODO 列表

方案文档至少包含：

- Context and current behaviour
- Desired behaviour and scope boundaries
- Open questions for the human to confirm
- Plan overview (3-7 bullet points)
- Numbered TODO list with dependencies and verification steps
