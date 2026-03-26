#!/usr/bin/env bash
set -euo pipefail

# ============================================================
#  GitHub Actions Self-Hosted Runner Batch Setup Script
#
#  Register multiple runner instances on a single machine
#  for concurrent job execution. Each runner uses its own
#  directory, sharing a single Linux user.
#
#  Usage:
#    bash setup-runners.sh [options]
#
#  Options:
#    -t, --token   TOKEN    Registration token (required)
#    -o, --org     ORG      GitHub organization (required)
#    -n, --count   N        Number of runners, default 4
#    -l, --label   LABEL    Custom label, defaults to hostname
#    -g, --group   GROUP    Runner group, default "Default"
#    -p, --prefix  PREFIX   Runner name prefix, defaults to label
#    -u, --user    USER     Linux user for runners, default "actions"
#    -h, --help             Show help
#
#  Examples:
#    bash setup-runners.sh -t ABCDEF123 -o jihuanshe -n 10 -l hetzner-ax41 -g "AI Lab"
#    bash setup-runners.sh -t ABCDEF123 -o myorg
#
#  How to obtain a token (pick one):
#    1. Web UI: GitHub → Org Settings → Actions → Runners → New runner → copy the token
#    2. CLI:    gh api -X POST /orgs/<ORG>/actions/runners/registration-token --jq .token
# ============================================================

# ---- Colors ----
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}>>> $*${NC}"; }
ok()    { echo -e "${GREEN}✓ $*${NC}"; }
warn()  { echo -e "${YELLOW}⚠ $*${NC}"; }
err()   { echo -e "${RED}✗ $*${NC}" >&2; }

# ---- Defaults ----
TOKEN=""
ORG=""
COUNT=4
LABEL=""
GROUP="Default"
PREFIX=""
RUNNER_USER="actions"

# ---- Help ----
usage() {
    sed -n '2,/^# =====/p' "$0" | grep '^#' | sed 's/^# \?//'
    exit 0
}

# ---- Argument parsing ----
while [[ $# -gt 0 ]]; do
    case "$1" in
        -t|--token)   TOKEN="$2";       shift 2 ;;
        -o|--org)     ORG="$2";         shift 2 ;;
        -n|--count)   COUNT="$2";       shift 2 ;;
        -l|--label)   LABEL="$2";       shift 2 ;;
        -g|--group)   GROUP="$2";       shift 2 ;;
        -p|--prefix)  PREFIX="$2";      shift 2 ;;
        -u|--user)    RUNNER_USER="$2"; shift 2 ;;
        -h|--help)    usage ;;
        *)            err "Unknown option: $1"; usage ;;
    esac
done

# ---- Argument validation ----
if [[ -z "$ORG" ]]; then
    err "Missing required option: --org"
    echo ""
    echo "Usage: bash setup-runners.sh -t <TOKEN> -o <ORG> [options]"
    echo "Run bash setup-runners.sh --help for full help"
    exit 1
fi

if [[ -z "$TOKEN" ]]; then
    err "Missing required option: --token"
    echo ""
    echo "How to obtain a registration token:"
    echo ""
    echo "  Method 1 — Web UI:"
    echo "    GitHub → https://github.com/organizations/${ORG}/settings/actions/runners/new"
    echo "    The page shows --token XXXXX, copy it"
    echo ""
    echo "  Method 2 — CLI (requires gh login with org admin permissions):"
    echo "    gh api -X POST /orgs/${ORG}/actions/runners/registration-token --jq .token"
    echo ""
    echo "  Note: Token expires in 1 hour. Regenerate if expired."
    exit 1
fi

if ! [[ "$COUNT" =~ ^[0-9]+$ ]] || [[ "$COUNT" -lt 1 ]] || [[ "$COUNT" -gt 50 ]]; then
    err "Runner count must be an integer between 1 and 50, got: $COUNT"
    exit 1
fi

# ---- Derive defaults ----
HOSTNAME_SHORT="$(hostname -s | tr '[:upper:]' '[:lower:]')"
if [[ -z "$LABEL" ]]; then
    LABEL="$HOSTNAME_SHORT"
    warn "--label not specified, using hostname: ${LABEL}"
fi
if [[ -z "$PREFIX" ]]; then
    PREFIX="$LABEL"
fi

# ---- Check if Linux user exists ----
if ! id "$RUNNER_USER" &>/dev/null; then
    err "Linux user '${RUNNER_USER}' does not exist"
    echo "  Create user: sudo useradd -m -s /bin/bash ${RUNNER_USER}"
    exit 1
fi

BASE="$(eval echo "~${RUNNER_USER}")"
ORG_URL="https://github.com/${ORG}"

# ---- Fetch latest runner version ----
info "Checking latest GitHub Actions Runner version..."
RUNNER_VER="$(curl -sSL https://api.github.com/repos/actions/runner/releases/latest \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['tag_name'].lstrip('v'))" 2>/dev/null \
    || echo "2.332.0")"
PKG="actions-runner-linux-x64-${RUNNER_VER}.tar.gz"
PKG_PATH="${BASE}/${PKG}"

info "Runner version: v${RUNNER_VER}"
echo ""

# ---- Configuration summary ----
echo "======================================"
echo "  Configuration Summary"
echo "======================================"
echo "  Organization:   ${ORG}"
echo "  Runner count:   ${COUNT}"
echo "  Name prefix:    ${PREFIX}-{1..${COUNT}}"
echo "  Label:          ${LABEL}"
echo "  Group:          ${GROUP}"
echo "  Linux user:     ${RUNNER_USER}"
echo "  Install dir:    ${BASE}/actions-runner-{1..${COUNT}}"
echo "  Runner version: v${RUNNER_VER}"
echo "======================================"
echo ""
read -rp "Confirm configuration? [Y/n] " CONFIRM
if [[ "${CONFIRM,,}" == "n" ]]; then
    echo "Cancelled."
    exit 0
fi

# ---- Download runner package ----
if [[ ! -f "$PKG_PATH" ]]; then
    info "Downloading runner v${RUNNER_VER}..."
    curl -sSL -o "$PKG_PATH" \
        "https://github.com/actions/runner/releases/download/v${RUNNER_VER}/${PKG}"
    chown "${RUNNER_USER}:${RUNNER_USER}" "$PKG_PATH"
    ok "Download complete"
else
    ok "Runner package already exists, skipping download"
fi

# ---- Create runner instances ----
CREATED=0
SKIPPED=0

for N in $(seq 1 "$COUNT"); do
    DIR="${BASE}/actions-runner-${N}"
    NAME="${PREFIX}-${N}"

    echo ""
    echo "=============================="
    info "Configuring runner: ${NAME} (${DIR})"
    echo "=============================="

    if [[ -f "${DIR}/.runner" ]]; then
        warn "Already exists, skipping. To rebuild, first run: bash remove-runners.sh"
        SKIPPED=$((SKIPPED + 1))
        continue
    fi

    sudo -u "${RUNNER_USER}" mkdir -p "$DIR"
    sudo -u "${RUNNER_USER}" tar xzf "$PKG_PATH" -C "$DIR"

    sudo -u "${RUNNER_USER}" bash -c "
        cd '${DIR}' && \
        ./config.sh --unattended \
            --url '${ORG_URL}' \
            --token '${TOKEN}' \
            --name '${NAME}' \
            --runnergroup '${GROUP}' \
            --labels '${LABEL}' \
            --work '_work' \
            --replace
    "

    cd "$DIR"
    ./svc.sh install "${RUNNER_USER}"
    ./svc.sh start

    ok "${NAME} started successfully"
    CREATED=$((CREATED + 1))
done

# ---- Summary ----
echo ""
echo "======================================"
echo "  Deployment Complete"
echo "======================================"
echo "  Created: ${CREATED}  Skipped: ${SKIPPED}"
echo ""
echo "  Workflow usage:"
echo "    runs-on: [self-hosted, ${LABEL}]"
echo ""
echo "  Management commands:"
echo "    Check status:  systemctl list-units 'actions.runner.*' --type=service"
echo "    Stop all:      for i in \$(seq 1 ${COUNT}); do sudo systemctl stop actions.runner.${ORG}.${PREFIX}-\$i.service; done"
echo "    Start all:     for i in \$(seq 1 ${COUNT}); do sudo systemctl start actions.runner.${ORG}.${PREFIX}-\$i.service; done"
echo "======================================"
echo ""

systemctl list-units --type=service | grep "actions.runner" || true
