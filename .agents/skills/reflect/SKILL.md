---
name: reflect
description: 'Reflect on code review suggestions. Triggers: reflect review, verify suggestions, check review.'
metadata:
  version: '3'
---

# Reflect Review

## Context Gathering

If the user asks to review PR / GitHub review comments but has not yet provided a list of suggestions:

1. Auto-detect the current branch's PR: `gh pr view --json number,url 2>/dev/null`
2. Load the `pr-comments` skill to collect PR review data, or manually fetch via `gh api repos/{owner}/{repo}/pulls/{number}/comments`
3. Once collected, feed the suggestion list as input to the `<context>` block below and proceed with the reflection workflow

If the user pastes suggestion text directly, skip collection and proceed straight to reflection.

<context>
$ARGUMENTS
</context>

## Task Definition

The report above is a list of suggestions produced by a reviewer who statically read the code, the diff, and searched web resources. The suggestions may be real issues or hallucinations.

You are an Agent working inside the actual code repository. Your task is: **deep-search and deep-think on each suggestion, render your judgment, and propose a minimal fix**.

## Output Requirements

For each suggestion, produce the following structure:

```markdown
### Data

### Warrant

### Claim

1. Real issue
2. Hallucination / over-optimization
3. Pending (needs more context)

### Severity

1. Crash / severe data loss / data corruption
2. High-probability bug
3. Edge case / low probability
4. Pure optimization

### Recommended Action

- Real issue: provide a **minimal-risk fix** (prefer small patch over refactor) and note possible side effects
- Hallucination / over-optimization: explain why no change is needed; if the misidentification stems from missing business context in the code, suggest adding a clarifying comment
- Pending: add to the Questions section at the end; specify what information is needed to reach a verdict
```

After reflection is complete, act according to the conclusions:

- **Real issues found**: ask the user whether to fix, or directly provide a minimal patch
- **All hallucinations**: leave a summary comment on the PR explaining the rejection rationale for each suggestion
- **Need to resolve review threads**: refer to the gh API gotchas documented in the `pr-comments` skill

## Reference Tools

The following means are available for verification:

- Run Linter / Tester
- Read source code
  - Including dependency source code in `.venv`
- Consult web search
- Consult codebase explorer
- Consult sub-agents
