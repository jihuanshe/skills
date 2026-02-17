from __future__ import annotations

import subprocess
import sys
from typing import Any

import httpx


class LinearAPIError(Exception):
    """Raised when Linear GraphQL API returns errors."""


_auth_token_cache: str | None = None
_http_client: httpx.Client | None = None


def log(*args: object) -> None:
    print(*args, file=sys.stderr)


def get_auth_token() -> str:
    global _auth_token_cache
    if _auth_token_cache is None:
        _auth_token_cache = subprocess.check_output(["linear", "auth", "token"]).decode().strip()
    return _auth_token_cache


def get_http_client() -> httpx.Client:
    """Get or create a shared httpx.Client for connection pooling."""
    global _http_client
    if _http_client is None:
        _http_client = httpx.Client(timeout=30.0)
    return _http_client


def run_query(
    query: str,
    *,
    variables: dict[str, Any] | None = None,
    query_name: str | None = None,
    strict: bool = True,
    debug: bool = False,
) -> dict[str, Any]:
    token = get_auth_token()
    client = get_http_client()
    if debug:
        name = query_name or "unnamed"
        log(f"[linear] query={name}")
        if variables:
            log(f"[linear] variables={variables}")
    resp = client.post(
        "https://api.linear.app/graphql",
        headers={"Authorization": token, "Content-Type": "application/json"},
        json={"query": query, "variables": variables or {}},
    )
    if resp.status_code >= 400:
        log(f"[linear] HTTP {resp.status_code}: {resp.text[:500]}")
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        name = query_name or "unnamed"
        log(f"[linear] GraphQL errors in {name}: {data['errors']}")
        if strict:
            raise LinearAPIError(f"GraphQL Errors: {data['errors']}")
    return data
