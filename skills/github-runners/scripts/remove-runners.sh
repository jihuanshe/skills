#!/usr/bin/env bash
set -euo pipefail

# ============================================================
#  GitHub Actions Self-Hosted Runner Batch Removal Script
#
#  Usage:
#    bash remove-runners.sh [options]
#
#  Options:
#    -t, --token   TOKEN    Remove token (required)
#    -o, --org     ORG      GitHub organization (required)
#    -n, --count   N        Number of runners, default 10
#    -u, --user    USER     Linux user for runners, default "actions"
#    -h, --help             Show help
#
#  How to obtain a token:
#    gh api -X POST /orgs/<ORG>/actions/runners/remove-token --jq .token
#
#  Examples:
#    bash remove-runners.sh -t ABCDEF123 -o jihuanshe -n 10
# ============================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}>>> $*${NC}"; }
ok()    { echo -e "${GREEN}✓ $*${NC}"; }
warn()  { echo -e "${YELLOW}⚠ $*${NC}"; }
err()   { echo -e "${RED}✗ $*${NC}" >&2; }

TOKEN=""
ORG=""
COUNT=10
RUNNER_USER="actions"

while [[ $# -gt 0 ]]; do
    case "$1" in
        -t|--token)   TOKEN="$2";       shift 2 ;;
        -o|--org)     ORG="$2";         shift 2 ;;
        -n|--count)   COUNT="$2";       shift 2 ;;
        -u|--user)    RUNNER_USER="$2"; shift 2 ;;
        -h|--help)    sed -n '2,/^# =====/p' "$0" | grep '^#' | sed 's/^# \?//'; exit 0 ;;
        *)            err "Unknown option: $1"; exit 1 ;;
    esac
done

if [[ -z "$ORG" ]]; then
    err "Missing required option: --org"
    exit 1
fi

if [[ -z "$TOKEN" ]]; then
    err "Missing required option: --token"
    echo ""
    echo "How to obtain a remove token:"
    echo "  gh api -X POST /orgs/${ORG}/actions/runners/remove-token --jq .token"
    exit 1
fi

BASE="$(eval echo "~${RUNNER_USER}")"
REMOVED=0

for N in $(seq 1 "$COUNT"); do
    DIR="${BASE}/actions-runner-${N}"
    if [[ ! -d "$DIR" ]]; then
        continue
    fi

    info "Removing runner-${N} (${DIR})"

    cd "$DIR"
    ./svc.sh stop 2>/dev/null || true
    ./svc.sh uninstall 2>/dev/null || true
    sudo -u "${RUNNER_USER}" bash -c "cd '${DIR}' && ./config.sh remove --token '${TOKEN}'" 2>/dev/null || true
    rm -rf "$DIR"

    ok "runner-${N} removed"
    REMOVED=$((REMOVED + 1))
done

echo ""
echo "======================================"
echo "  Removal complete: ${REMOVED} runner(s)"
echo "======================================"
systemctl list-units --type=service | grep "actions.runner" || echo "  No remaining runner services"
