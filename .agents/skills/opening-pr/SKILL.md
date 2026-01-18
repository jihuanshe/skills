---
name: opening-pr
description: 'Create or update GitHub PRs with proper title and summary. Triggers: open PR, update PR description, write change summary.'
metadata:
  version: '2'
---

# Opening OR Updating PR

## Quick Reference

```bash
# 查看当前分支 PR
gh pr view --json number,title,url

gh pr create --base main --title "..." --body "..."

gh pr edit --title "..." --body "..."

# 当前分支关联的 issue-id
linear issue-id

# 查看 issue 详情
linear issue view <issue-id>
```

## Step 0: Start from main

```bash
# 如果用户已经在处理某个 Linear Issue 那你应该先拿到相关的 issue-id 然后检查当前分支是不是 main
# 如果是 main，则需要拉取 origin 后切出
# 在切出分支前，请你在本地以及 Remote 分支里检查 issue-id 相关的 issue 是否存在
# 如果存在，则询问用户如何操作
# 如果不存在，则创建规范

# 自动创建 <user>/<issue-id> 格式分支，并将 issue 状态改为 In Progress
linear issue start <issue-id> --from-ref origin/main
```

**如果是 main 且无法判断，则提问用户具体处理方式。**

## Step 1: Sync & Prepare

```bash
# 0) 确认工作区干净（有未提交改动时不要 rebase）
git status --porcelain  # 必须为空

# 1) 先同步远程引用
git fetch origin
BRANCH=$(git branch --show-current)

# 2) 风控：远程分支是否有人更新（多人协作场景）
git log --oneline HEAD..origin/"$BRANCH" 2>/dev/null

# 3) 风控：自己是否落后 main
git log --oneline HEAD..origin/main
```

**如果有风险，暂停让用户确认后再继续。**

### Rebase 到 main

```bash
# PR 合并用 squash merge，本地不需要手动 squash，直接 rebase 即可
git rebase origin/main
```

#### ⚠️ 禁止使用 reset --soft origin/main

```bash
# ❌ 绝对不要这样做
git reset --soft origin/main
git commit -m "..."

# 原因：会把分支上的旧代码覆盖 main 上后续 PR 的修改
```

#### 冲突解决

```bash
# ⚠️ rebase 的 ours/theirs 与 merge 相反！
# - ours = origin/main（正在 rebase onto 的目标）
# - theirs = 你的提交（正在被应用的 commit）

# 本分支是新功能 → git checkout --theirs <file>
# main 上是修复 → git checkout --ours <file>
git add <resolved-files>
git rebase --continue
```

## Step 2: Review Changes

```bash
# 查看变更（用 ... 更符合 PR 视角，显示 merge-base 到 HEAD 的差异）
git diff --stat origin/main...HEAD
git diff origin/main...HEAD

# 获取 issue 上下文（如果分支关联了 Linear）
linear issue view $(linear issue-id)

# 读取 PR 模板
cat .github/pull_request_template.md
```

## Step 3: Create or Update PR

```bash
# Push（rebase/squash 后需要 force）
git push -u origin HEAD --force-with-lease

# 检查是否已有 PR
gh pr view --json number,url

# 创建新 PR
gh pr create --base main --title "..." --body "..."

# 或更新现有 PR
gh pr edit --title "..." --body "..."
```

## Step 4: Link Related Amp Threads（关键步骤）

**每次创建或更新 PR 时，必须搜索并关联真正相关的 Amp Threads。**

### 4.1 识别当前 Thread 链

首先，**从当前 Thread 开始追溯**。一个任务可能经历多次 handoff（从一个 Thread 移交到另一个 Thread 继续工作）：

1. **当前 Thread**：你正在工作的这个（必须包含）
2. **Handoff 来源**：如果当前 Thread 是从其他 Thread handoff 过来的，追溯上游
3. **Cluster 搜索**：用 `find_thread` 工具的 `cluster_of:` 过滤器查找同一任务的相关 threads

使用 `find_thread` 工具搜索相关 threads：

| 搜索场景 | query 参数 |
| :--------- | :----------- |
| 同 cluster 的 threads | `cluster_of:T-当前thread-id` |
| 关联 Linear issue | `task:AI-596` |
| 包含依赖任务 | `task:AI-596+` |
| 按关键词 + 时间范围 | `skills migration after:7d` |

### 4.2 验证相关性（必须）

> ⚠️ **不要只按文件路径搜索**（`file:xxx`）。修改同一文件的 threads 不一定相关。

对每个候选 Thread，用 `read_thread` 工具验证是否真正相关：

- **threadID**: `T-candidate-id`
- **goal**: "这个 thread 是否与本 PR 的目标相关？提取关键决策和上下文。"

**相关性判断标准**：

- ✅ 讨论了本 PR 要解决的问题
- ✅ 包含本 PR 的设计决策或方案讨论
- ✅ 是本 PR 工作的直接前置任务
- ❌ 只是碰巧修改了同一文件（不相关）
- ❌ 是完全独立的功能开发（不相关）

### 4.3 更新 PR Body

只添加**真正相关**的 threads，并注明关系：

```markdown
## Related Amp Threads

- https://ampcode.com/threads/T-xxx - 当前实现线程
- https://ampcode.com/threads/T-yyy - 方案设计讨论（handoff 来源）
- https://ampcode.com/threads/T-zzz - 问题排查（发现了本 PR 要修复的 bug）
```

**如果没有找到相关 threads，只写当前 thread 即可**——不要为了"看起来完整"而添加不相关的链接。

### 4.4 同步到 Linear Issue（可选）

```bash
# 获取关联的 issue-id
linear issue-id

# 添加 comment 到 Linear Issue
linear issue comment add <issue-id> -b "## Related Amp Threads

PR #<number> 相关的 Amp 工作线程：

- https://ampcode.com/threads/T-xxx - 主线程
- https://ampcode.com/threads/T-yyy - 功能规划

**PR**: https://github.com/<org>/<repo>/pull/<number>"
```

**为什么这步很重要**：

- 保留完整的决策上下文和讨论记录
- 便于后续回溯问题根因
- 新成员可快速了解功能演进历史

## Amp 工具参考

| 工具 | 用途 | 备注 |
| :----- | :----- | :----- |
| `find_thread` | 搜索 Threads | 支持 `file:`, `task:`, `cluster_of:`, `after:` 等过滤器 |
| `read_thread` | 读取并摘要 Thread | 需提供 threadID 和 goal 参数 |
| `handoff` | 移交到新 Thread | 当前 Thread 的工作由新 Thread 继续 |

## Troubleshooting

### Repository not found

如果 `git fetch/push` 遇到 `Repository not found`，可能是 GitHub 账户不匹配：

```bash
# 检查当前登录的账户
gh auth status

# 切换到正确的账户
gh auth switch
```
