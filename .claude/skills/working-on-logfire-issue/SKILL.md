---
name: working-on-logfire-issue
description: 'Debug and fix issues using Logfire traces. Triggers: Logfire trace ID or URL provided for debugging.'
metadata:
  version: '1'
---

# Work on Logfire Issue

根据 Logfire 中的 trace ID 分析并生成修复方案。

## 使用场景

- 当需要根据 Logfire 中的 trace 调试问题时
- 分析特定 span 的错误或异常

## 运行

从 skill 目录执行：

```bash
bash scripts/work-on-logfire-issue.sh <trace-id>
```

## 参数

- `<trace-id>`: Logfire 中的 trace ID

## 脚本功能

调用 `logfire prompt` 命令获取 trace 上下文并生成修复建议。
