---
name: opening-pr
description: 'Create or update GitHub PRs with proper title and summary. Triggers: open PR, update PR description, write change summary.'
metadata:
  version: '1'
---

# Opening OR Updating PR

## Step 1: Check PR Status

```bash
# Check if current branch already has a PR
gh pr view --json number,title,url

# Check if current branch is linked to linear issue
linear issue id
```

- Success -> PR exists, use `gh pr edit` to update
- Error -> No PR yet, use `gh pr create`

## Step 2: Collect Info

```bash
# Git: commits and diff
git log --oneline origin/main..HEAD
git diff --stat origin/main..HEAD
git diff origin/main..HEAD  # full diff if needed

# Linear (optional): get issue context if branch is linked
linear issue view --help
```

## Step 3: Write Title & Change Summary

1. Read `.github/pull_request_template.md` for format requirements.
2. Write Title & Change Summary based on commits, diff, and issue context.

## Step 4: Create or Update PR

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
