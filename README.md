# Skills

## Logfire

```markdown
# 安装 Logfire Agent Skill

## 前置条件

- 当前目录必须是 Git 仓库

## 步骤

### 安装

- `amp skill add jihuanshe/skills/.agents/skills/using-logfire --target .agents/skills --overwrite`

### 验证

- `amp skill list`

### 配置 MCP 依赖

- 读取模板 `mcp.tpl.json` 比如 `.agents/skills/using-logfire/mcp.tpl.json`
- 确认 Shell 环境有 uv 依赖（如果没有则提示用户安装，如果是 macOS 则可以用 uv 安装，如果用户电脑里有 mise 则可以用 mise 来安装）
- 确认 Logfire 基础配置 `uvx logfire whoami`，有可能需要用户登录 `uvx logfire auth`
- 获得真实的 Token 后替换模板后保存同路径的 `mcp.json` 比如 `.agents/skills/using-logfire/mcp.json`
```
