---
name: opening-pr
description: 'Create or update GitHub PRs with proper title and summary. Triggers: open PR, update PR description, write change summary.'
metadata:
  version: '1'
---

# Opening OR Updating PR

## Quick Reference

### gh pr 常用命令

```bash
gh pr view [<number>|<url>|<branch>]                # 查看 PR 详情
gh pr view --json title,body,state,url              # JSON 输出
gh pr list                                          # 列出当前仓库 PR
gh pr status                                        # 当前分支 PR 状态
gh pr checks                                        # 查看 CI 状态
gh pr create --base main --title "..." --body "..." # 创建 PR
gh pr create --draft                                # 创建草稿 PR
gh pr edit [<number>] --title "..."                 # 修改标题
gh pr edit [<number>] --body "..."                  # 修改正文
gh pr edit [<number>] --body-file pr_body.md        # 从文件读取正文
gh pr ready                                         # 标记为 Ready for Review
gh pr merge --squash                                # Squash merge
gh pr comment --body "..."                          # 添加评论
```

### linear issue 常用命令

```bash
linear issue id                                    # 当前分支关联的 issue ID
linear issue view [issueId]                        # 查看 issue 详情
linear issue view [issueId] --json                 # JSON 输出
linear issue url [issueId]                         # 获取 issue URL
linear issue list                                  # 列出我的 issues
linear issue start [issueId]                       # 开始处理 issue（切换状态+创建分支）
linear issue update [issueId] --state "..."        # 更新状态
linear issue update [issueId] --title "..."        # 更新标题
linear issue update [issueId] --description "..."  # 更新描述
linear issue create                                # 创建新 issue
linear issue comment add [issueId] --body "..."    # 添加评论
```

---

## Step 1: Sync with origin/main

**必须先同步，否则 diff 会包含不属于此 PR 的内容。**

```bash
# Fetch latest origin/main
git fetch origin main

# Rebase current branch onto origin/main
git rebase origin/main
# If conflicts, resolve them before continuing
```

## Step 2: Check PR Status

```bash
# Check if current branch already has a PR
gh pr view --json number,title,url

# Check if current branch is linked to linear issue
linear issue id
```

- Success -> PR exists, use `gh pr edit` to update
- Error -> No PR yet, use `gh pr create`

## Step 3: Collect Info

```bash
# Git: commits and diff (now accurate after rebase)
git log --oneline origin/main..HEAD
git diff --stat origin/main..HEAD
git diff origin/main..HEAD  # full diff if needed

# Linear (optional): get issue context if branch is linked
linear issue view AI-XXX

# Amp Threads (optional): find related threads that touched these files or discussed the issue
# Use find_thread tool with file: or keyword queries
```

### Find Related Amp Threads

Search for Amp threads that contributed to this PR:

1. By modified files: `file:path/to/changed/file.py`
2. By Linear issue: Search for the issue ID (e.g., `AI-565`)
3. By keywords: Search for relevant feature/bug keywords
4. By recent activity: `author:me after:7d`

Include the most relevant thread URL in the PR body as metadata for traceability.

## Step 4: Write Title & Change Summary

1. Read `.github/pull_request_template.md` for format requirements.
2. Write Title & Change Summary based on commits, diff, and issue context.

## Step 5: Create or Update PR

### Create New PR

```bash
# Ensure local changes are pushed
git push -u origin HEAD

# Or with explicit title/body
gh pr create --base main --title "..." --body "..."

# Create as draft
gh pr create --base main --draft
```

### Update Existing PR

```bash
# Update title
gh pr edit --title "..."

# Update body
gh pr edit --body "..."

# Update body from file (for long content)
gh pr edit --body-file pr_body.md
```

## Step 6: Sync Linear Issue (if linked)

确保 Linear issue 和 PR 内容同步：

```bash
# Update state to "In Review"
linear issue update AI-XXX --state "In Review"

# Update description with PR link and change summary
linear issue update AI-XXX --description "## 变更内容

...

## PR

https://github.com/xxx/xxx/pull/NNN"
```

### 同步检查清单

- [ ] GitHub PR Title 与变更内容匹配
- [ ] GitHub PR Body 包含准确的 Change Summary
- [ ] Linear Issue Description 与 PR Body 一致
- [ ] Linear Issue State 为 "In Review"
- [ ] PR Body 包含 `Closes AI-XXX` 以便自动关联
