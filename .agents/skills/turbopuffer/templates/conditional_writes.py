"""Conditional writes for optimistic concurrency control.

Demonstrates:
- Version-based optimistic concurrency
- Timestamp-based last-write-wins
- Insert-if-not-exists
- Conditional delete and patch
"""

import os
from typing import Any, TypedDict, cast

import turbopuffer
from turbopuffer.types import RowParam


class VersionedRow(TypedDict):
    """Row with version for optimistic concurrency."""

    id: int
    vector: list[float]
    title: str
    version: int
    updated_at: str


class TimestampRow(TypedDict):
    """Row with timestamp for last-write-wins."""

    id: int
    vector: list[float]
    title: str
    updated_at: str


class SimpleRow(TypedDict):
    """Simple row with title."""

    id: int
    vector: list[float]
    title: str


class StatusRow(TypedDict):
    """Row with status field."""

    id: int
    vector: list[float]
    status: str


class DraftRow(TypedDict):
    """Row with status and title."""

    id: int
    vector: list[float]
    status: str
    title: str


def main() -> None:
    tpuf = turbopuffer.Turbopuffer(
        api_key=os.getenv("TURBOPUFFER_API_KEY"),
        region="gcp-us-central1",
    )

    ns = tpuf.namespace("conditional-writes-example")

    # Initial document with version
    initial_row: list[VersionedRow] = [
        {
            "id": 1,
            "vector": [0.1, 0.2, 0.3],
            "title": "Original Title",
            "version": 1,
            "updated_at": "2025-01-20T10:00:00Z",
        },
    ]
    ns.write(
        upsert_rows=[cast(dict[str, Any], r) for r in initial_row],
        distance_metric="cosine_distance",
    )

    # Pattern 1: Version-based optimistic concurrency
    # Only update if new version > existing version
    version_update_row: list[VersionedRow] = [
        {
            "id": 1,
            "vector": [0.1, 0.2, 0.3],
            "title": "Updated Title",
            "version": 2,
            "updated_at": "2025-01-20T11:00:00Z",
        },
    ]
    result = ns.write(
        upsert_rows=[cast(dict[str, Any], r) for r in version_update_row],
        upsert_condition=("version", "Lt", {"$ref_new": "version"}),
        distance_metric="cosine_distance",
    )
    print(f"Version update: {result.rows_affected} rows affected")

    # Pattern 2: Timestamp-based last-write-wins
    timestamp_row: list[TimestampRow] = [
        {
            "id": 2,
            "vector": [0.4, 0.5, 0.6],
            "title": "New Document",
            "updated_at": "2025-01-20T12:00:00Z",
        },
    ]
    result = ns.write(
        upsert_rows=[cast(dict[str, Any], r) for r in timestamp_row],
        upsert_condition=(
            "Or",
            [
                ("updated_at", "Lt", {"$ref_new": "updated_at"}),
                ("updated_at", "Eq", None),
            ],
        ),
        distance_metric="cosine_distance",
    )
    print(f"Timestamp update: {result.rows_affected} rows affected")

    # Pattern 3: Insert-if-not-exists
    insert_rows: list[SimpleRow] = [
        {"id": 1, "vector": [0.7, 0.8, 0.9], "title": "Should Not Insert"},
        {"id": 3, "vector": [0.7, 0.8, 0.9], "title": "Should Insert"},
    ]
    result = ns.write(
        upsert_rows=[cast(dict[str, Any], r) for r in insert_rows],
        upsert_condition=("id", "Eq", None),
        distance_metric="cosine_distance",
    )
    print(f"Insert-if-not-exists: {result.rows_affected} rows affected")

    # Pattern 4: Conditional delete
    archived_row: list[StatusRow] = [
        {"id": 4, "vector": [0.1, 0.2, 0.3], "status": "archived"},
    ]
    ns.write(
        upsert_rows=[cast(dict[str, Any], r) for r in archived_row],
        distance_metric="cosine_distance",
    )

    result = ns.write(
        deletes=[4],
        delete_condition=("status", "Eq", "archived"),
    )
    print(f"Conditional delete: {result.rows_deleted} rows deleted")

    # Pattern 5: Conditional patch
    draft_row: list[DraftRow] = [
        {"id": 5, "vector": [0.1, 0.2, 0.3], "status": "draft", "title": "Draft"},
    ]
    ns.write(
        upsert_rows=[cast(dict[str, Any], r) for r in draft_row],
        distance_metric="cosine_distance",
    )

    # Cast needed because ty doesn't handle Union[TypedDict, Dict] well
    patch_data: list[RowParam] = [cast(RowParam, {"id": 5, "status": "published"})]
    result = ns.write(
        patch_rows=patch_data,
        patch_condition=("status", "Eq", "draft"),
    )
    print(f"Conditional patch: {result.rows_patched} rows patched")


if __name__ == "__main__":
    main()
