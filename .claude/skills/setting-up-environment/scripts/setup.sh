#!/usr/bin/env sh

set -e
set -u

script_name="$(basename "${0}")"

OS_NAME="$(uname -s)"
if [ "${OS_NAME}" != "Linux" ]; then
  echo "ERROR: ${script_name} can only be run on Linux. Detected: ${OS_NAME}." >&2
  exit 1
fi

if ! command -v git >/dev/null 2>&1; then
  echo "ERROR: git is required to run ${script_name}." >&2
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "ERROR: curl is required to run ${script_name}." >&2
  exit 1
fi

if ! repo_root="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  echo "ERROR: Failed to find git repository root for ${script_name}." >&2
  exit 1
fi

cd "${repo_root}"

echo "INFO: Installing mise via official installer..."
curl https://mise.run | MISE_INSTALL_PATH=/usr/local/bin/mise sh

echo "INFO: Trusting mise configuration..."
mise trust --yes

echo "INFO: Running init task..."
mise install --yes
mise use -g prek
mise exec -- prek install --overwrite
mise exec -- uv sync --frozen

echo "INFO: ${script_name} completed."

exit 0
