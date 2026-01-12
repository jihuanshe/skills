#!/usr/bin/env bash
set -euo pipefail

if [ $# -eq 0 ]; then
	echo "Usage: work-on-logfire-issue <trace-id>"
	echo "Example: work-on-logfire-issue abc123def456"
	exit 2
fi

TRACE_ID="$1"

if ! command -v mise &> /dev/null; then
	echo "Error: mise not found. Please install mise first."
	exit 1
fi

mise exec uv@latest -- uvx logfire prompt --project jihuanshe/python --codex fix-span-issue:"$TRACE_ID"
