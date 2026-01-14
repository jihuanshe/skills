# Skills

## Logfire Agent Skill

```markdown
# 安装 Skill

## 前置条件

- 当前目录必须是 Git 仓库

## 步骤

### 安装 skill

`amp skill add jihuanshe/skills/.agents/skills/using-logfire --target .agents/skills --overwrite`

### 验证安装

`amp skill list`

### 配置 MCP

- 读取模板：`.agents/skills/using-logfire/mcp.tpl.json`
- 模板中的 env 值包含获取真实 token 的命令提示，执行该命令获取真实值
- 替换后保存为：`.agents/skills/using-logfire/mcp.json`
```
