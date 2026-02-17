"""Optimized schema configuration for cost and performance.

Demonstrates:
- f16 vectors (faster and cheaper than f32)
- UUID type (16 bytes vs 36 bytes for string)
- filterable: false for 50% storage discount
- Full-text search configuration
"""

import os
from typing import Any, TypedDict, cast

import turbopuffer
from turbopuffer.types import AttributeSchemaParam


class OptimizedRow(TypedDict):
    """Type-safe row with all optimized schema fields."""

    id: int
    vector: list[float]
    title: str
    searchable_text: str
    raw_content: str
    category: str
    created_at: str
    user_id: str
    tags: list[str]


def build_optimized_schema() -> dict[str, AttributeSchemaParam]:
    """Build optimized schema with proper types.

    Returns schema configuration with cost optimizations:
    - f16 vectors (faster and cheaper)
    - UUID type (16 bytes vs 36)
    - filterable: false for storage discount
    """
    return {
        # f16 vectors: faster and cheaper than f32
        "vector": cast(AttributeSchemaParam, {"type": "[512]f16", "ann": True}),
        # UUID type: 16 bytes vs 36 bytes for string
        "user_id": "uuid",
        # Datetime type: proper date handling
        "created_at": "datetime",
        # Full-text search with custom tokenizer
        "searchable_text": cast(
            AttributeSchemaParam,
            {
                "type": "string",
                "full_text_search": {
                    "tokenizer": "word_v3",
                    "language": "english",
                    "stemming": True,
                    "remove_stopwords": True,
                },
            },
        ),
        # Title searchable with BM25
        "title": cast(AttributeSchemaParam, {"type": "string", "full_text_search": True}),
        # Non-filterable attribute: 50% storage discount
        "raw_content": cast(AttributeSchemaParam, {"type": "string", "filterable": False}),
        # Standard filterable string
        "category": "string",
        # Array type
        "tags": "[]string",
    }


def main() -> None:
    tpuf = turbopuffer.Turbopuffer(
        api_key=os.getenv("TURBOPUFFER_API_KEY"),
        region="gcp-us-central1",
    )

    ns = tpuf.namespace("optimized-schema-example")

    rows: list[OptimizedRow] = [
        {
            "id": 1,
            "vector": [0.1] * 512,
            "title": "Document Title",
            "searchable_text": "This text is searchable via BM25",
            "raw_content": "Large content blob not used for filtering...",
            "category": "technical",
            "created_at": "2025-01-20T10:30:00Z",
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
            "tags": ["python", "search", "vectors"],
        },
    ]

    schema = build_optimized_schema()

    result = ns.write(
        upsert_rows=[cast(dict[str, Any], r) for r in rows],
        schema=schema,
        distance_metric="cosine_distance",
    )
    print(f"Written {result.rows_upserted} rows")
    print(f"Billable bytes: {result.billing.billable_logical_bytes_written}")

    # Query with filters and BM25
    query_result = ns.query(
        rank_by=(
            "Sum",
            [
                ("Product", 2.0, ("title", "BM25", "document")),
                ("searchable_text", "BM25", "searchable"),
            ],
        ),
        top_k=10,
        filters=(
            "And",
            [
                ("category", "Eq", "technical"),
                ("created_at", "Gte", "2025-01-01T00:00:00Z"),
                ("tags", "Contains", "python"),
            ],
        ),
        include_attributes=["title", "category"],
    )

    for row in query_result.rows or []:
        dist = row["$dist"]
        title = getattr(row, "title", "")
        print(f"ID: {row.id}, Score: {dist}, Title: {title}")


if __name__ == "__main__":
    main()
