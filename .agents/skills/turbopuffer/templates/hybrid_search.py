"""Hybrid search (vector + BM25) with client-side rank fusion.

Demonstrates:
- Multi-query API for atomic vector + BM25 search
- Reciprocal Rank Fusion (RRF) for score combination
- FTS schema configuration
"""

import os
from collections import defaultdict
from collections.abc import Sequence
from typing import Any, TypedDict, cast

import turbopuffer
from turbopuffer.types import Row


class SearchableRow(TypedDict):
    """Row with FTS-enabled fields."""

    id: int
    vector: list[float]
    title: str
    content: str


def reciprocal_rank_fusion(
    result_lists: Sequence[Sequence[Row]],
    k: int = 60,
) -> list[tuple[int | str, float]]:
    """Fuse multiple result lists using reciprocal rank fusion.

    RRF is a simple but effective rank fusion algorithm that combines
    results from multiple ranking signals without requiring score normalization.

    Args:
        result_lists: List of result lists, each containing Row objects.
        k: Constant to prevent high scores for top ranks (default 60).

    Returns:
        List of (id, score) tuples sorted by fused score descending.
    """
    scores: dict[int | str, float] = defaultdict(float)

    for result_list in result_lists:
        for rank, row in enumerate(result_list, start=1):
            scores[row.id] += 1 / (k + rank)

    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


def main() -> None:
    tpuf = turbopuffer.Turbopuffer(
        api_key=os.getenv("TURBOPUFFER_API_KEY"),
        region="gcp-us-central1",
    )

    ns = tpuf.namespace("hybrid-search-example")

    # Upsert documents with vectors and text for BM25
    rows: list[SearchableRow] = [
        {
            "id": 1,
            "vector": [0.1, 0.2, 0.3],
            "title": "Introduction to Python",
            "content": "Python is a versatile programming language.",
        },
        {
            "id": 2,
            "vector": [0.4, 0.5, 0.6],
            "title": "Machine Learning Basics",
            "content": "Machine learning enables computers to learn from data.",
        },
        {
            "id": 3,
            "vector": [0.7, 0.8, 0.9],
            "title": "Deep Learning with Python",
            "content": "Deep learning is a subset of machine learning using neural networks.",
        },
    ]
    ns.write(
        upsert_rows=[cast(dict[str, Any], r) for r in rows],
        schema={
            "content": {"type": "string", "full_text_search": True},
            "title": {"type": "string", "full_text_search": True},
        },
        distance_metric="cosine_distance",
    )

    # Multi-query: vector + BM25 executed atomically
    query_vector = [0.1, 0.2, 0.3]
    query_text = "python programming"

    result = ns.multi_query(
        queries=[
            {
                "rank_by": ("vector", "ANN", query_vector),
                "top_k": 20,
                "include_attributes": ["title"],
            },
            {
                "rank_by": (
                    "Sum",
                    [
                        ("Product", 2.0, ("title", "BM25", query_text)),
                        ("content", "BM25", query_text),
                    ],
                ),
                "top_k": 20,
                "include_attributes": ["title"],
            },
        ],
    )

    # Client-side rank fusion
    vector_results = result.results[0].rows or []
    bm25_results = result.results[1].rows or []

    fused = reciprocal_rank_fusion([vector_results, bm25_results])

    print("Fused results:")
    for doc_id, score in fused[:10]:
        print(f"  ID: {doc_id}, RRF Score: {score:.4f}")


if __name__ == "__main__":
    main()
