---
name: repo-prompt
description: 'Use Repo Prompt MCP tools. Triggers: repo prompt, context builder, file search.'
metadata:
  version: '1'
---

# Repo Prompt Skill

## Available Tools

- `manage_selection` - Manage the current selection used by all tools.
- `file_actions` - Create, delete, or move files.
- `get_code_structure` - Return code structure (codemaps) for files and directories.
- `get_file_tree` - ASCII directory tree of the project.
- `read_file` - Read file contents, optionally specifying a starting line and number of lines.
- `file_search` - Search by file path and/or file content.
- `workspace_context` - Snapshot of this window's workspace: prompt, selection, code structure (codemaps).
- `prompt` - Get or modify the shared prompt (instructions/notes). Ops: get | set | append | clear | export | list_presets | select_preset
- `apply_edits` - Apply direct file edits (rewrite or search/replace).
- `list_models` - List available model presets (id, name, description, supported modes).
- `chat_send` - Start a new chat or continue an existing conversation. Modes: `chat` | `plan` | `edit`.
- `chats` - List chats or view a chat's history. Actions: list | log
- `context_builder` - Intelligently explore the codebase and build optimal file context for a task.
- `list_windows` - List all RepoPrompt windows with workspace & roots
- `select_window` - Bind all subsequent tool calls of THIS client to the given window ID.
- `manage_workspaces` - Manage workspaces across RepoPrompt windows.
