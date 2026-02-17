---
name: pr-open
description: 'Create or update GitHub PRs. Triggers: open PR, create PR, update PR.'
metadata:
  version: '4'
---

# Opening OR Updating PR

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

### 是否需要 Rebase？

> ⚠️ **Rebase 不是必须的**，因为 PR 最终用 squash merge，中间历史无所谓。

**何时需要 rebase**：

- 上游 main 有**与本 PR 相关的变更**（API 变更、依赖更新等），需要基于新代码继续开发
- 存在**冲突**，GitHub 无法自动合并

**何时不需要 rebase**：

- 只是"落后 main 几个 commit"但无冲突、无相关变更
- 为了"让历史干净"——squash merge 后历史本来就只有一个 commit

```bash
# 如果确实需要 rebase
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

## Step 2: Gather All Context

> ⚠️ **先收集所有上下文，再动笔写 PR / 更新 Linear。** 跳过任何一个来源都可能导致描述不完整或与实际偏移。

以下 4 个来源**尽量并行获取**（互不依赖）：

### 2a. Code diff

```bash
# 分支上所有变更（... = merge-base 视角，最接近 PR diff）
git diff --stat origin/main...HEAD
git diff origin/main...HEAD

# 分支上的所有 commits（可能有之前的 wip commits）
git log --oneline origin/main..HEAD
```

**常见错误**：只看 `git status`（uncommitted changes），忽略分支上已有的 commits，导致 PR 描述不完整。

### 2b. Existing PR（如果已有）

```bash
gh pr view --json number,url,state,title,body
```

已有 OPEN PR 时，读取当前 title/body 作为基线——后续只需增量更新，而非从零重写。

### 2c. Existing Linear Issue

```bash
linear issue view $(linear issue-id)
```

读取当前 issue 标题和描述，后续用来判断是否与实际变更偏移。

### 2d. Amp Threads（Amp 必做，Claude Code 可跳过）

> ⚠️ 必须使用 `find_thread` 搜索相关 threads，不能偷懒只写当前 thread。

**识别当前 Thread 并追溯**：

1. **当前 Thread**：你正在工作的这个（必须包含）
2. **Handoff 来源**：如果当前 Thread 是从其他 Thread handoff 过来的，追溯上游
3. **Cluster 搜索**：用 `find_thread` 工具的 `cluster_of:` 过滤器查找同一任务的相关 threads

| 搜索场景 | query 参数 |
| :--------- | :----------- |
| 同 cluster 的 threads | `cluster_of:T-当前thread-id` |
| 关联 Linear issue | `task:AI-596` |
| 包含依赖任务 | `task:AI-596+` |
| 按关键词 + 时间范围 | `skills migration after:7d` |

对每个候选 Thread，用 `read_thread` 验证是否真正相关：

- ✅ 讨论了本 PR 要解决的问题 / 包含设计决策 / 是直接前置任务
- ❌ 只是碰巧修改了同一文件 / 完全独立的功能开发

### 2e. PR 模板

```bash
cat .github/pull_request_template.md
```

## Step 3: Push & Create/Update PR + Linear

> ⚠️ **PR 和 Linear 在同一步骤内一起写出**，确保两者内容对齐、来源一致。

### 3a. Push

```bash
git push -u origin HEAD --force-with-lease
```

### 3b. 判断 PR create vs edit

> ⚠️ **必须检查 PR 的 state，不能只看 PR 是否存在！**
>
> Squash merge 后，本地分支名可能与已合并 PR 的分支名相同。
> 如果不检查 state 就执行 `gh pr edit`，会错误地修改历史 PR 的内容。

| `gh pr view` 结果 | 操作 |
| :---------------- | :--- |
| 不存在 PR | `gh pr create` |
| state = `OPEN` | `gh pr edit` 更新现有 PR |
| state = `MERGED` 或 `CLOSED` | `gh pr create` 创建新 PR |

### 3c. 写出 PR

基于 Step 2 收集的全部上下文（diff + 现有 PR/Linear + Amp threads），按 PR 模板撰写 title 和 body。

PR body 必须包含 `## Related Amp Threads` 部分（只添加真正相关的 threads，并注明关系）：

```markdown
## Related Amp Threads

- https://ampcode.com/threads/T-xxx - 当前实现线程
- https://ampcode.com/threads/T-yyy - 方案设计讨论（handoff 来源）
```

如果没有找到相关 threads，只写当前 thread 即可。

```bash
# 创建新 PR
gh pr create --base main --title "..." --body "..."

# 更新现有 OPEN 状态的 PR
gh pr edit --title "..." --body "..."
```

### 3d. 同步 Linear Issue

对比 Step 2c 获取的现有 issue 标题/描述与 PR 最终内容，判断是否偏移：

- issue 标题是否仍能准确概括 PR 的变更？
- issue 描述是否覆盖了 PR 的所有关键变更？
- 是否有 PR 中做了但 issue 里没提的工作？

**如果存在偏移**，更新 issue 标题和描述：

```bash
linear issue update <issue-id> \
  --title "新标题（准确概括实际变更）" \
  --description "## 变更范围

### 1. ...
### 2. ...

## PR

- https://github.com/<org>/<repo>/pull/<number>

## Amp Threads

- https://ampcode.com/threads/T-xxx - 主线程"
```

**如果无偏移**，添加 comment 关联 PR 和 Threads：

```bash
linear issue comment add <issue-id> -b "## Related Amp Threads

PR #<number> 相关的 Amp 工作线程：

- https://ampcode.com/threads/T-xxx - 主线程

**PR**: https://github.com/<org>/<repo>/pull/<number>"
```

**原则**：

- Issue 标题 = PR 标题的中文版（或等价语义）
- Issue 描述 = PR body 的精简版，聚焦「做了什么」而非「怎么做的」
- 不要保留过时的原始描述——直接覆盖，Git 有历史

**为什么 PR + Linear 必须一起写出**：

- 保证两者描述一致，避免分步骤写导致信息漂移
- 保留完整的决策上下文和讨论记录
- 便于后续回溯问题根因
- 新成员可快速了解功能演进历史

## Quick Reference

```bash
# 查看当前分支 PR
gh pr view --json number,title,url,state,body

gh pr create --base main --title "..." --body "..."

gh pr edit --title "..." --body "..."

# 当前分支关联的 issue-id
linear issue-id

# 查看 issue 详情
linear issue view <issue-id>

# 更新 issue
linear issue update <issue-id> --title "..." --description "..."
```

## Troubleshooting

### Repository not found

如果 `git fetch/push` 遇到 `Repository not found`，可能是 GitHub 账户不匹配：

```bash
# 检查当前登录的账户
gh auth status

# 切换到正确的账户
gh auth switch
```

## Amp 工具参考

| 工具 | 用途 | 备注 |
| :----- | :----- | :----- |
| `find_thread` | 搜索 Threads | 支持 `file:`, `task:`, `cluster_of:`, `after:` 等过滤器 |
| `read_thread` | 读取并摘要 Thread | 需提供 threadID 和 goal 参数 |
| `handoff` | 移交到新 Thread | 当前 Thread 的工作由新 Thread 继续 |
