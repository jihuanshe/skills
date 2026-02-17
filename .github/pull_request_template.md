# Pull Request

<!-- Thank you for your contribution! -->

## Title

建议 PR 标题遵循下列格式：

`<type>(<scope>): <subject>`

- type
  - `feat` 新功能或对外行为变化
  - `fix` Bug 修复
  - `refactor` 重构，不改变对外行为
  - `chore` 工程杂务 (依赖升级、脚手架、配置等)
  - `ci` CI、构建、质量检查
  - `docs` 文档
  - `test` 测试
  - `perf` 性能优化
  - `revert` 回滚
- scope
  - 例如：deck, eye, search, news, tcgen, spider, core, playground, infra, docs
- subject
  - 一句话说明做了什么 / 目的是什么，不写实现细节
  - 中文或中英混排都可以，避免句号结尾
  - 控制在 72 字符内，细节放正文

## Change Summary

<!-- Please give a short summary of the changes. -->

## Related Amp Threads

<!-- Optional: Link to Amp threads that contributed to this PR for context and traceability. -->
<!-- Example: https://ampcode.com/threads/T-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx -->

## Checklist

- [ ] PR 的标题能精确地压缩变更信息（模块、类型、意图都清晰）
- [ ] PR 中新增的行为（新功能或修复）有相应的测试
- [ ] 本地运行 `mise format`、`mise lint` 与 `mise test` 并通过

### AI Review

- [ ] 使用 `gpt-5.2-pro` 或 `gemini-3-pro-preview` 检查过代码，建议 2/2 Pass，提示词可用 Repo Prompt 构建
  - AI 的正确建议：请修复
  - AI 的错误建议：请添加必要的注释
    - AI 是不懂业务的 Junior 程序员，如果它给出了错误建议，大概率你代码无法「自解释」，即很有其中有业务相关的魔法，为确保「一切与代码相关的都在 Monorepo 中跟踪」的原则，请麻烦添加注释
- [ ] 使用 Amp 或 Codex 的 `gpt-5.2 xhigh` 的 `/review` 命令检查过代码（如可用），建议 3/3 Pass
