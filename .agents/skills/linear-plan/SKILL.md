---
name: linear-plan
description: 'Plan implementation for a Linear issue. Triggers: start issue, work on LIN-xxx.'
metadata:
  version: '1'
---

# Resolving Linear Issue

## 上下文

```bash
# 从 URL 提取 issue-id（如 AI-579）
# https://linear.app/jihuanshe/issue/AI-579/优化-spider2-龙星增量更新 → AI-579

# 查看 issue（自动下载附件图片到临时目录）
linear issue view AI-579

# 获取结构化 JSON 数据（用 yq 转 YAML 更易读）
linear issue view AI-579 --json | yq -p json

# 不加 `--json` 时，CLI 会将图片下载到 `/var/folders/.../T/linear-cli-images/`，可用 `look_at` 工具查看
# 加 `--json` 时，图片仍是 URL 形式，需授权访问
```

## 目标

Noam Brown:「AI 模型就像天才，但每次任务都要从零开始。」

请为这个具体的 Linear 任务完成自我上手过程。

你是一名在本仓库工作的资深软件工程师。当前这个会话里，你的唯一目标是理解任务并产出一份结构化的方案和 TODO 列表。不要修改代码，也不要假设任何改动已经完成。

在提出任何改动建议时，一定要遵守仓库根目录的 AGENTS.md 中的规则。例如：

- 增加依赖或运行脚本时，优先使用 uv 和 mise 相关命令，而不是直接运行 python 或 pip。
- 让数据模型保持清晰稳定。
- 明确标出日志、可观测性和测试方面的需求。

## 清单

### 1. 阅读任务详情

阅读上方的任务详情、标签、项目以及所有评论。尝试抽象出真实的用户需求和约束条件。如果有任何模糊或不确定的地方，不要猜，后面在「Open questions」小节中列出即可。

### 2. 映射到代码库

- 找出可能相关的入口、模块和数据模型。
- 如果目前没有看到你需要的文件或目录，主动说明希望查看哪些内容。
- 优先复用现有的设计和模式，而不是从零发明新的结构。

### 3. 分析当前设计质量

- 记录任何可能让改动变得困难的设计味道或风险点。
- 如果一个小型重构可以明显降低复杂度或风险，就在方案里单独作为 TODO 项写出来。

### 4. 制定方案和 TODO 列表

请使用 Markdown，至少包含以下小节：

- Context and current behaviour: 当前行为与上下文
- Desired behaviour and scope boundaries: 期望行为与范围边界
- Open questions for the human to confirm: 需要人来确认的开放问题
- Plan overview in 3 to 7 bullet points: 用 3 到 7 个要点概述整体方案
- TODO list as a numbered list of concrete steps: 用编号列表给出具体可执行的 TODO
  - 对每一个 TODO 项，写清楚：
  - 目标及简要动机
  - 可能需要修改的文件或模块
  - 变更类型 (重构、功能开发、缺陷修复、测试、文档、工具链等)
  - 对其他 TODO 项的依赖关系
  - 如何验证改动 (需要哪些测试、手工验证步骤、以及观测指标)

### 5. 风险评估

- 测试策略和边界场景
- 性能和资源消耗
- 安全性和数据一致性
- 向后兼容性以及上线风险
- 与外部需求来源的链接 (例如 Featurebase 工单)

最终输出应该是一份单一的、自洽的方案文档。只有当人类明确批准了这份方案之后，才可以开始执行或实现其中的 TODO 项。
