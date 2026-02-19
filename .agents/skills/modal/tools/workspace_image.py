"""Reusable Modal image builder for uv workspace packages.

Build a Modal Image that includes local workspace packages and their
third-party dependencies.  The heavy lifting (dependency extraction,
non-PyPI filtering) is encapsulated in `build_workspace_image` so that
any Modal app in this repo can call it instead of duplicating the logic.

Self-test entrypoint::

    modal run .agents/skills/modal/tools/workspace_image.py

Notes
-----
1. **Dependency resolution must run locally** — the helpers read
   ``pyproject.toml`` from the local filesystem, so any call to
   ``_extract_third_party_deps`` or ``_find_repo_root`` must be guarded
   by ``modal.is_local()``.

2. **Filters workspace members and git-sourced packages** — these are
   not published on PyPI and cannot be ``pip install``-ed. The builder
   automatically strips them from the dependency list.

3. **``add_local_python_source()`` must be the last step** in the image
   chain (unless ``copy=True``).  No ``.uv_pip_install()`` calls are
   allowed after it.

4. **Extra deps pattern** — ``build_workspace_image()`` only installs
   the package's own declared dependencies.  If a service needs
   additional packages (e.g., ``fastapi``, ``logfire``), install them
   *before* ``add_local_python_source``::

        if modal.is_local():
            import sys
            from pathlib import Path

            sys.path.insert(0, str(Path(__file__).resolve().parents[N] / ".agents/skills/modal/tools"))
            from workspace_image import _extract_third_party_deps, _find_repo_root

            _EXTRA_DEPS = ["fastapi[standard]>=0.115.0"]
            _third_party = _extract_third_party_deps(_find_repo_root() / "pyproject.toml", "core")
            image = (
                modal.Image.debian_slim(python_version="3.13")
                .uv_pip_install(*_third_party, *_EXTRA_DEPS)  # all pip install before
                .add_local_python_source("core")  # mount last
            )
        else:
            image = modal.Image.debian_slim()

5. **``modal.is_local()`` guard** — Module-level code runs inside
   remote containers too.  Local-only logic (reading ``pyproject.toml``,
   git commands) must be wrapped in an ``if modal.is_local():`` block.
   The ``else`` branch **must** provide placeholder values for every
   variable used later, otherwise the remote container raises
   ``NameError``.
"""

from __future__ import annotations

import re
import tomllib
from importlib import import_module
from pathlib import Path

import modal

MODAL_APP_NAME: str = "workspace-image"


def _find_repo_root() -> Path:
    """Walk up from this file to find the repo root (has ``[tool.uv.workspace]``)."""
    current = Path(__file__).resolve().parent
    while current != current.parent:
        pyproject = current / "pyproject.toml"
        if pyproject.exists():
            data = tomllib.loads(pyproject.read_text())
            if "workspace" in data.get("tool", {}).get("uv", {}):
                return current
        current = current.parent
    raise RuntimeError("Cannot locate repo root with [tool.uv.workspace]")


def _normalize(name: str) -> str:
    """PEP 503 normalize: lowercase, replace [-_.] with underscore."""
    return re.sub(r"[-_.]+", "_", name).lower()


def _parse_root_pyproject(root_pyproject: Path) -> tuple[frozenset[str], dict[str, Path]]:
    """Parse root pyproject.toml to extract non-PyPI packages and member directory map.

    Returns:
        non_pypi: Normalized names of packages not on PyPI (workspace + git sources).
        member_map: Mapping from normalized package name to its directory (relative to repo root).
    """
    data = tomllib.loads(root_pyproject.read_text())
    uv = data.get("tool", {}).get("uv", {})

    sources: dict[str, dict] = uv.get("sources", {})
    non_pypi = frozenset(_normalize(name) for name, spec in sources.items() if spec.get("workspace") or spec.get("git"))

    member_map: dict[str, Path] = {}
    for member_dir in uv.get("workspace", {}).get("members", []):
        member_pyproject = root_pyproject.parent / member_dir / "pyproject.toml"
        if member_pyproject.exists():
            member_data = tomllib.loads(member_pyproject.read_text())
            name = member_data.get("project", {}).get("name")
            if name:
                member_map[_normalize(name)] = root_pyproject.parent / member_dir

    return non_pypi, member_map


def _extract_third_party_deps(root_pyproject: Path, *package_names: str) -> list[str]:
    """Extract third-party dependencies for given workspace packages.

    Automatically locates each package's pyproject.toml via the workspace member map
    and filters out non-PyPI packages (workspace members + git sources).
    """
    non_pypi, member_map = _parse_root_pyproject(root_pyproject)
    all_deps: dict[str, str] = {}

    for pkg in package_names:
        pkg_dir = member_map.get(_normalize(pkg))
        if not pkg_dir:
            raise ValueError(f"Package '{pkg}' not found in workspace members")
        pkg_pyproject = pkg_dir / "pyproject.toml"
        data = tomllib.loads(pkg_pyproject.read_text())
        for spec in data.get("project", {}).get("dependencies", []):
            match = re.match(r"^([a-zA-Z0-9][-a-zA-Z0-9_.]*)", spec)
            if match:
                normalized = _normalize(match.group(1))
                if normalized not in non_pypi:
                    all_deps[normalized] = spec

    return sorted(all_deps.values())


def build_workspace_image(*package_names: str, python_version: str = "3.13") -> modal.Image:
    """Build a Modal Image with local workspace packages mounted.

    Automatically resolves third-party dependencies from pyproject.toml
    and filters out workspace members and git-sourced packages.
    """
    repo_root = _find_repo_root()
    third_party_deps = _extract_third_party_deps(repo_root / "pyproject.toml", *package_names)
    return (
        modal.Image.debian_slim(python_version=python_version)
        .uv_pip_install(*third_party_deps)
        .add_local_python_source(*package_names)
    )


# ---------------------------------------------------------------------------
# Self-test entrypoint: modal run .agents/skills/modal/tools/workspace_image.py
# ---------------------------------------------------------------------------

_LOCAL_PACKAGES: tuple[str, ...] = ("deck", "core")

app: modal.App = modal.App(MODAL_APP_NAME)

# Image building and dep resolution only run locally — the container
# receives the pre-built image and doesn't need pyproject.toml.
if modal.is_local():
    _third_party_deps: list[str] = _extract_third_party_deps(_find_repo_root() / "pyproject.toml", *_LOCAL_PACKAGES)
    image: modal.Image = build_workspace_image(*_LOCAL_PACKAGES)
else:
    _third_party_deps = []
    image = modal.Image.debian_slim()


@app.function(image=image, timeout=120)
def verify_imports() -> dict[str, str | list[str]]:
    """Verify that local packages are importable and inspect their contents."""
    results: dict[str, str | list[str]] = {}

    game_module = import_module("core.models.game")
    GameKey = game_module.__dict__["GameKey"]

    results["core_GameKey"] = str(GameKey)

    core = import_module("core")

    results["core_location"] = core.__file__ or "unknown"

    deck_root = Path("/root/deck")
    results["deck_location"] = str(deck_root)
    results["deck_files_exist"] = str(deck_root.exists() and (deck_root / "__init__.py").exists())

    deck_submodules: list[str] = []
    for py_file in sorted(deck_root.rglob("*.py")):
        rel = py_file.relative_to(deck_root.parent)
        mod_path = str(rel).replace("/", ".").removesuffix(".py")
        if mod_path.endswith(".__init__"):
            mod_path = mod_path.removesuffix(".__init__")
            deck_submodules.append(f"[pkg] {mod_path}")
        else:
            deck_submodules.append(f"[mod] {mod_path}")
    results["deck_submodules"] = deck_submodules
    results["deck_py_file_count"] = str(len(list(deck_root.rglob("*.py"))))

    return results


@app.local_entrypoint()
def main():
    print("=" * 60)
    print("Running local package import test in Modal container")
    print(f"Third-party deps resolved: {len(_third_party_deps)}")
    for dep in _third_party_deps:
        print(f"  - {dep}")
    print("=" * 60)

    result = verify_imports.remote()

    print(f"\n✅ core GameKey:        {result['core_GameKey']}")
    print(f"✅ core location:      {result['core_location']}")
    print(f"✅ deck location:      {result['deck_location']}")
    print(f"✅ deck files exist:   {result['deck_files_exist']}")
    print(f"✅ deck .py files:     {result['deck_py_file_count']}")
    print(f"\n📦 deck modules ({len(result['deck_submodules'])}):")
    for sub in result["deck_submodules"]:
        print(f"   {sub}")

    print("\n" + "=" * 60)
    print("All imports verified successfully! 🎉")
    print("=" * 60)
