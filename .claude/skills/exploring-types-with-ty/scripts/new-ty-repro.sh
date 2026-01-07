#!/usr/bin/env bash
set -euo pipefail

# Create a new ty reproduction file from the template.
#
# Usage:
#   bash .agents/skills/exploring-types-with-ty/scripts/new-ty-repro.sh demos/my_issue_ty_repro.py
#
# Then:
#   mise exec -- ty check demos/my_issue_ty_repro.py

if [ $# -ne 1 ]; then
  echo "Usage: new-ty-repro.sh <output-path>"
  echo "Example: new-ty-repro.sh demos/my_issue_ty_repro.py"
  exit 2
fi

out="$1"

if [ -e "$out" ]; then
  echo "Error: file already exists: $out"
  exit 1
fi

mkdir -p "$(dirname "$out")"

cat > "$out" <<'PY'
"""
Template: ty minimal reproduction (copy into demos/ and edit).

Goal: reproduce a type inference problem in < 60 lines and fix it by narrowing
dict literals via explicit TypedDict/type alias annotations.

Run:
  mise exec -- ty check demos/<file>.py
"""

from __future__ import annotations

from typing import TYPE_CHECKING


def build_params() -> object:
    """
    Replace `object` with the actual target type (TypedDict / TypeAlias), then:

    1) Type intermediate values first:
       item: SomeTypedDict = {...}
       items: SomeListAlias = [item]
       nested: SomeNestedTypedDict = {...}

    2) Type the final dict literal:
       params: SomeParamsTypedDict = {...}
       return params
    """
    raise NotImplementedError


if TYPE_CHECKING:
    # Put optional "bad examples" here, but keep them commented out so the file
    # still passes type checks by default.
    pass
PY

echo "Created: $out"
echo "Next: mise exec -- ty check $out"
