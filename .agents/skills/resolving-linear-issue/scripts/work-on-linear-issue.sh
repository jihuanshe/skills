#!/usr/bin/env bash
set -euo pipefail

# Check if issue argument is provided
if [ $# -eq 0 ]; then
	echo "Usage: work-on-issue <issue-abbreviation>"
	echo "Examples:"
	echo "  work-on-issue AB-123"
	echo "  work-on-issue https://linear.app/abc/issue/AB-123/issue-title"
	exit 2
fi

ISSUE_ARG="$1"
# shellcheck disable=SC2034
TEAM_ID="jihuanshe" # Default team ID, can be modified

# Find repository root directory
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
if [ -z "$REPO_ROOT" ]; then
	echo "Error: Not in a git repository"
	exit 1
fi

# Try to load .env file from repo root
if [ -f "$REPO_ROOT/.env" ]; then
	set -a
	# shellcheck disable=SC1091
	source "$REPO_ROOT/.env"
	set +a
fi

# Extract issue abbreviation if URL is provided
if [[ "$ISSUE_ARG" == *"linear.app"* ]]; then
	ISSUE_ABBREV=$(echo "$ISSUE_ARG" | grep -oE '[A-Z]+-[0-9]+')
else
	ISSUE_ABBREV="$ISSUE_ARG"
fi

# Validate issue format
if [[ ! "$ISSUE_ABBREV" =~ ^[A-Z]+-[0-9]+$ ]]; then
	echo "Error: Invalid issue format. Expected format: TEAM-123"
	exit 1
fi

# Check if LINEAR_API_KEY is set
if [ -z "$LINEAR_API_KEY" ]; then
	echo "Error: LINEAR_API_KEY environment variable not set"
	echo "Please set your Linear API key: export LINEAR_API_KEY=your_token_here"
	exit 1
fi

# GraphQL query for Linear issue - search by identifier (shorthand)
read -r -d '' QUERY <<'EOF' || true
query($number: Float!) {
  issues(filter: { number: { eq: $number } }) {
    nodes {
      id
      identifier
      title
      description
      priority
      state {
        name
        type
      }
      assignee {
        name
        email
      }
      creator {
        name
        email
      }
      team {
        name
        key
      }
      labels {
        nodes {
          name
          color
        }
      }
      project {
        name
      }
      estimate
      url
      createdAt
      updatedAt
      comments {
        nodes {
          body
          user {
            name
          }
          createdAt
        }
      }
    }
  }
}
EOF

# Extract just the number part from MC-91 format
ISSUE_NUMBER=$(echo "$ISSUE_ABBREV" | grep -oE '[0-9]+$')

# Execute query - escape the query properly
JSON_PAYLOAD=$(jq -n --arg query "$QUERY" --argjson number "$ISSUE_NUMBER" \
	'{query: $query, variables: {number: $number}}')

RESPONSE=$(curl -fsS -X POST https://api.linear.app/graphql \
	-H "Authorization: $LINEAR_API_KEY" \
	-H "Content-Type: application/json" \
	-d "$JSON_PAYLOAD") || {
	echo "Error: Could not fetch issue $ISSUE_ABBREV from Linear API"
	exit 1
}

# Check for API errors
if echo "$RESPONSE" | jq -e '.errors' >/dev/null 2>&1; then
	echo "Error: Linear API returned an error:"
	echo "$RESPONSE" | jq -r '.errors[].message'
	exit 1
fi

# Extract issue data
ISSUE_DATA=$(echo "$RESPONSE" | jq -r '.data.issues.nodes[0]')
if [ "$ISSUE_DATA" == "null" ]; then
	echo "Error: Issue $ISSUE_ABBREV not found"
	exit 1
fi

# Extract fields
TITLE=$(echo "$ISSUE_DATA" | jq -r '.title')
DESCRIPTION=$(echo "$ISSUE_DATA" | jq -r '.description // ""')
IDENTIFIER=$(echo "$ISSUE_DATA" | jq -r '.identifier')
PRIORITY=$(echo "$ISSUE_DATA" | jq -r '.priority // "None"')
STATE=$(echo "$ISSUE_DATA" | jq -r '.state.name')
ASSIGNEE=$(echo "$ISSUE_DATA" | jq -r '.assignee.name // "Unassigned"')
CREATOR=$(echo "$ISSUE_DATA" | jq -r '.creator.name')
TEAM=$(echo "$ISSUE_DATA" | jq -r '.team.name')
URL=$(echo "$ISSUE_DATA" | jq -r '.url')
ESTIMATE=$(echo "$ISSUE_DATA" | jq -r '.estimate // "Not estimated"')

# Output formatted content
cat <<EOF
Deep dive into this Linear issue and the surrounding codebase. Then propose a structured plan and TODO list for addressing it.

# $TITLE ($IDENTIFIER)

**Team:** $TEAM
**State:** $STATE
**Priority:** $PRIORITY
**Assignee:** $ASSIGNEE
**Creator:** $CREATOR
**Estimate:** $ESTIMATE
**URL:** $URL

## Description

$DESCRIPTION

EOF

# Add labels if present
LABELS=$(echo "$ISSUE_DATA" | jq -r '.labels.nodes[] | .name' | tr '\n' ', ' | sed 's/, $//')
if [ -n "$LABELS" ]; then
	echo "**Labels:** $LABELS"
	echo
fi

# Add project if present
PROJECT=$(echo "$ISSUE_DATA" | jq -r '.project.name // empty')
if [ -n "$PROJECT" ]; then
	echo "**Project:** $PROJECT"
	echo
fi

# Add comments if present
COMMENTS=$(echo "$ISSUE_DATA" | jq -r '.comments.nodes[] | "**@\(.user.name)** (\(.createdAt | split("T")[0])):\n\(.body)\n"')
if [ -n "$COMMENTS" ]; then
	echo "## Comments"
	echo
	echo "$COMMENTS"
fi

cat <<'EOF'
---

Noam Brown:「AI 模型就像天才，但每次任务都要从零开始。」

请为这个具体的 Linear 任务完成自我上手过程。

你是一名在本仓库工作的资深软件工程师。当前这个会话里，你的唯一目标是理解任务并产出一份结构化的方案和 TODO 列表。不要修改代码，也不要假设任何改动已经完成。

在提出任何改动建议时，一定要遵守仓库根目录的 AGENTS.md 中的规则。例如：

- 增加依赖或运行脚本时，优先使用 uv 和 mise 相关命令，而不是直接运行 python 或 pip。
- 让数据模型保持清晰稳定。
- 明确标出日志、可观测性和测试方面的需求。

请按下面的顺序工作：

1. 阅读上方的任务详情、标签、项目以及所有评论。尝试抽象出真实的用户需求和约束条件。
   如果有任何模糊或不确定的地方，不要猜，后面在「Open questions」小节中列出即可。

2. 把问题映射到代码库中。
   - 找出可能相关的入口、模块和数据模型。
   - 如果目前没有看到你需要的文件或目录，主动说明希望查看哪些内容。
   - 优先复用现有的设计和模式，而不是从零发明新的结构。

3. 分析当前设计质量。
   - 记录任何可能让改动变得困难的设计味道或风险点。
   - 如果一个小型重构可以明显降低复杂度或风险，就在方案里单独作为 TODO 项写出来。

4. 为解决该任务制定详细的方案和 TODO 列表。请使用 Markdown, 至少包含以下小节：
   - Context and current behaviour: 当前行为与上下文
   - Desired behaviour and scope boundaries: 期望行为与范围边界
   - Open questions for the human to confirm: 需要人来确认的开放问题
   - Plan overview in 3 to 7 bullet points: 用 3 到 7 个要点概述整体方案
   - TODO list as a numbered list of concrete steps: 用编号列表给出具体可执行的 TODO
   - 对每一个 TODO 项，写清楚：
     - 目标及简要动机
     - 可能需要修改的文件或模块
     - 变更类型 (重构、功能开发、缺陷修复、测试、文档、工具链等)
     - 对其他 TODO 项的依赖关系
     - 如何验证改动 (需要哪些测试、手工验证步骤、以及观测指标)

5. 仔细思考以下方面：
   - 测试策略和边界场景
   - 性能和资源消耗
   - 安全性和数据一致性
   - 向后兼容性以及上线风险
   - 与外部需求来源的链接 (例如 Featurebase 工单)

最终输出应该是一份单一的、自洽的方案文档。只有当人类明确批准了这份方案之后，才可以开始执行或实现其中的 TODO 项。
EOF
