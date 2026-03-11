#!/usr/bin/env bash
#MISE description="检查 git 邮箱配置（CI 兼容）"

set -euo pipefail

if [[ "${CI:-}" == "true" ]]; then
    exit 0
fi

email=$(git config user.email)
if [[ ! "$email" =~ @jihuanshe\.com$ ]]; then
    echo "Error: git user.email must be @jihuanshe.com (current: $email)"
    exit 1
fi
