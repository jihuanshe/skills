# Skills

目前以 Amp 作为一等公民优化 Skill 所以在 Skill 中可能出现 Amp 的特性，比如 Amp 自带的工具调用，Amp 特有的动态加载 MCP。

## 安装 Logfire Agent Skill

```markdown
# 安装 Logfire Agent Skill

## 前置条件

- 当前目录必须是 Git 仓库

## 步骤

### 安装

- `amp skill add jihuanshe/skills/.agents/skills/logfire --target .agents/skills --overwrite`

### 验证

- `amp skill list`

### 配置 MCP 依赖

- 读取模板 `mcp.tpl.json` 比如 `.agents/skills/logfire/mcp.tpl.json`
- 确认 Shell 环境有 uv 依赖（如果没有则提示用户安装，如果是 macOS 则可以用 uv 安装，如果用户电脑里有 mise 则可以用 mise 来安装）
- 确认 Logfire 基础配置 `uvx logfire whoami`，有可能需要用户登录 `uvx logfire auth` 这个命令是交互式命令要用户来操作
- 获得真实的 Token 后替换模板后保存同路径的 `mcp.json` 比如 `.agents/skills/logfire/mcp.json`
- 最后把 `.agents/skills/logfire/mcp.json` 添加到 `.gitignore`
```

## 安装 Linear Agent Skill (TODO)

```markdown
https://raw.githubusercontent.com/schpet/linear-cli/refs/heads/main/README.md
```
