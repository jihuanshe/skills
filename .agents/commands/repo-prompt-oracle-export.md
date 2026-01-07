---
description: Token-efficient reminder to use RepoPrompt MCP tools (file_search, read_file, apply_edits, file_actions) instead of built-in alternatives.
---

> [!IMPORTANT]
> Read Repo Prompt SKILL first.

# Oracle Export

Export a comprehensive prompt with full context for consultation with an external oracle.

## How It Works

Describe the task or question you need the oracle to solve. The context_builder agent will:

1. Analyze your request and explore the codebase
2. Select the most relevant files within a token budget
3. Write a detailed prompt explaining the task and context

You don't need to specify which files to include—just describe what you need help with.

## Workflow

### 1. Build Context

```json
{"tool":"context_builder","args":{
  "instructions":"<the task/question above>",
  "response_type":"clarify"
}}
```

Wait for context_builder to complete. It will explore the codebase and build optimal context.

### 2. Export Prompt

Confirm the export path with the user (default: `~/Downloads/oracle-prompt.md`), then export:

```json
{"tool":"prompt","args":{"op":"export","path":"<confirmed path>"}}
```

Report the export path and token count to the user.
