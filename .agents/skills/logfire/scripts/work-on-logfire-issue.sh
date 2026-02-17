#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 2 ]; then
	echo "Usage: work-on-logfire-issue <project> <trace-id>"
	echo "Example: work-on-logfire-issue jp abc123def456"
	echo ""
	echo "Available projects: cn, jp, us"
	echo "Run 'uvx logfire projects list' to see all projects"
	exit 2
fi

PROJECT="$1"
TRACE_ID="$2"

if ! command -v mise &> /dev/null; then
	echo "Error: mise not found. Please install mise first."
	exit 1
fi

mise exec uv@latest -- uvx logfire prompt --project "jihuanshe/$PROJECT" --codex fix-span-issue:"$TRACE_ID"
