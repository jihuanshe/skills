"""Basic vector search with turbopuffer.

A minimal example demonstrating:
- Client initialization
- Document upsert with type-safe rows
- ANN vector search with filters
"""

import os
from typing import Any, TypedDict, cast

import turbopuffer


class DocumentRow(TypedDict):
    """Type-safe row definition for this example."""

    id: int
    vector: list[float]
    title: str
    category: str


def main() -> None:
    tpuf = turbopuffer.Turbopuffer(
        api_key=os.getenv("TURBOPUFFER_API_KEY"),
        region="gcp-us-central1",
    )

    ns = tpuf.namespace("example-namespace")

    # Type-safe rows
    rows: list[DocumentRow] = [
        {
            "id": 1,
            "vector": [0.1, 0.2, 0.3],
            "title": "Document 1",
            "category": "A",
        },
        {
            "id": 2,
            "vector": [0.4, 0.5, 0.6],
            "title": "Document 2",
            "category": "B",
        },
    ]

    ns.write(
        upsert_rows=[cast(dict[str, Any], row) for row in rows],
        distance_metric="cosine_distance",
    )

    # Query with ANN
    query_vector = [0.1, 0.2, 0.3]
    result = ns.query(
        rank_by=("vector", "ANN", query_vector),
        top_k=10,
        include_attributes=["title", "category"],
    )

    for row in result.rows or []:
        dist = row["$dist"]
        title = getattr(row, "title", "")
        print(f"ID: {row.id}, Distance: {dist}, Title: {title}")


if __name__ == "__main__":
    main()
