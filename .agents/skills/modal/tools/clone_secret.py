"""Migrate (rename / clone) a Modal secret with zero noise.

Uses a diff approach: runs a baseline function (no secret) and a function with
the target secret injected, then diffs env vars to extract only the secret's
actual key-value pairs — immune to base image changes.

Both functions use serialized=True to avoid dependency mismatch between
local (has sys.argv) and remote (no sys.argv) environments.

Usage:
    # Dry run (default): show what would be migrated
    modal run .agents/skills/modal/tools/clone_secret.py --old-name foo --new-name bar

    # Execute migration
    modal run .agents/skills/modal/tools/clone_secret.py --old-name foo --new-name bar --no-dry-run

    # Cross-environment: read from prod, write to dev
    modal run .agents/skills/modal/tools/clone_secret.py --old-name foo --new-name bar --from-env prod --to-env dev --no-dry-run

Notes:
    1. **Secret env vars priority**: Secret env vars override image ``.env()``.
       Only put real secrets (token, key, password) in Secrets. Config like
       ``ENV``, ``SERVICE_NAME`` goes in image ``.env()`` or runtime derivation.

    2. **Cross-env clone pitfall**: Non-secret fields carry the source
       environment's values (e.g., ``ENV=dev`` cloned to prod → prod container
       sees ``ENV=dev``).

    3. **MODAL_ENVIRONMENT**: Modal auto-injects this into containers, equals
       the ``--env`` value. Use it as the single source of truth for
       environment identity.

    4. **CLI limitations**: ``modal secret list/create/delete`` only — no
       export. This script's diff approach is the recommended workaround.

    4b. **Key-diff limitation**: This script only captures **newly introduced
        env keys**. If a Secret overrides an existing env var key (e.g.,
        ``DATABASE_URL`` already set by the base image), that key will **not**
        appear in the diff. Keep Secrets to pure credentials to avoid this.

    5. **Programmatic create**:
       ``modal.Secret.objects.create(name, env_dict, environment_name=..., allow_existing=False)``
       — see SDK source ``secret.py`` for full API.

    6. **serialized=True usage**: This script uses ``serialized=True`` because
       the secret binding depends on module-level ``sys.argv`` parsing.
       ``serialized=True`` pickles the function so the container doesn't
       re-import and re-evaluate the conditional. NOT compatible with
       ``@modal.asgi_app()`` / ``@modal.wsgi_app()`` — use ``from_name`` for
       web services instead.

    7. **from_local_environ vs from_name**: ``from_local_environ`` grabs env
       vars locally, needs ``serialized=True``, doesn't work with ASGI apps.
       ``from_name`` resolves on both sides, no serialization needed, works
       everywhere — but requires the secret to be pre-created via
       ``modal secret create``.  For multi-person teams, ``from_name`` is
       preferred because the secret lives in the workspace; ``from_local_environ``
       requires every developer to have the env vars locally.
       Web services should use ``from_name``.

    8. **modal secret delete**: Use ``modal secret delete <name> -y`` to skip
       the confirmation prompt.  Alternatively, use SDK deletion
       (``modal.Secret.objects.delete(name)``).
"""

from __future__ import annotations

import sys

import modal

MODAL_APP_NAME: str = "clone-secret"

# ---------------------------------------------------------------------------
# Parse flags at module level so we can bind the secret before Modal
# serializes. serialized=True on both functions prevents the container
# from re-evaluating this conditional.
# ---------------------------------------------------------------------------
_old_name: str = ""
_from_env: str = ""
for _i, _arg in enumerate(sys.argv):
    if _arg == "--old-name" and _i + 1 < len(sys.argv):
        _old_name = sys.argv[_i + 1]
    if _arg == "--from-env" and _i + 1 < len(sys.argv):
        _from_env = sys.argv[_i + 1]

app: modal.App = modal.App(MODAL_APP_NAME)

_secrets: list[modal.Secret] = []
if _old_name:
    _secrets = [
        modal.Secret.from_name(_old_name, environment_name=_from_env)
        if _from_env
        else modal.Secret.from_name(_old_name)
    ]


@app.function(serialized=True)
def _baseline() -> dict[str, str]:
    """Capture env vars WITHOUT any user secret (system baseline)."""
    import os

    return dict(os.environ)


@app.function(secrets=_secrets, serialized=True)
def _with_secret() -> dict[str, str]:
    """Capture env vars WITH the target secret injected."""
    import os

    return dict(os.environ)


@app.local_entrypoint()
def main(
    old_name: str = "",
    new_name: str = "",
    from_env: str = "",
    to_env: str = "",
    dry_run: bool = True,
):
    if not old_name or not new_name:
        print("❌ Both --old-name and --new-name are required.")
        print(__doc__)
        raise SystemExit(1)

    baseline_env = _baseline.remote()
    secret_env = _with_secret.remote()

    # Diff: keys present only when the secret is injected
    secret_keys = set(secret_env) - set(baseline_env)
    kvs = {k: secret_env[k] for k in sorted(secret_keys)}

    src_label = f"'{old_name}'" + (f" (env={from_env})" if from_env else "")
    dst_label = f"'{new_name}'" + (f" (env={to_env})" if to_env else "")

    print(f"\n📦 Read {len(kvs)} keys from {src_label}:")
    for k in kvs:
        print(f"   {k}=***")

    if not kvs:
        print("⚠️  No secret keys found. Check that the secret name is correct.")
        return

    if dry_run:
        print(f"\n🔒 Dry run — would create {dst_label} with {len(kvs)} keys.")
        print("   Re-run with --no-dry-run to apply.")
        return

    create_kwargs: dict = {}
    if to_env:
        create_kwargs["environment_name"] = to_env

    modal.Secret.objects.create(new_name, kvs, **create_kwargs)
    print(f"\n✅ Secret {dst_label} created with {len(kvs)} keys.")
