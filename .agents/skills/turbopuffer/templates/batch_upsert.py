"""Batch upsert pattern for high-throughput ingestion.

Demonstrates:
- Batching documents for efficient writes
- Parallel upsert with ThreadPoolExecutor
- logfire span instrumentation
"""

import os
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any, TypedDict, cast

import logfire
import turbopuffer

if TYPE_CHECKING:
    from turbopuffer.lib.namespace import Namespace


class DocumentRow(TypedDict):
    """Type-safe row definition for batch upsert."""

    id: int
    vector: list[float]
    title: str


def batch_documents(
    documents: Sequence[DocumentRow],
    batch_size: int = 1000,
) -> list[list[DocumentRow]]:
    """Split documents into batches."""
    doc_list = list(documents)
    return [doc_list[i : i + batch_size] for i in range(0, len(doc_list), batch_size)]


def upsert_batch(
    ns: "Namespace",
    batch: Sequence[DocumentRow],
    batch_idx: int,
) -> int:
    """Upsert a single batch of documents."""
    with logfire.span("turbopuffer.upsert_batch", batch_idx=batch_idx, size=len(batch)):
        result = ns.write(
            upsert_rows=[cast(dict[str, Any], row) for row in batch],
            distance_metric="cosine_distance",
        )
        return result.rows_affected


def parallel_upsert(
    ns: "Namespace",
    documents: Sequence[DocumentRow],
    batch_size: int = 1000,
    max_workers: int = 4,
) -> int:
    """Upsert documents in parallel batches.

    Uses ThreadPoolExecutor to parallelize upserts across batches.

    Args:
        ns: Namespace to upsert into.
        documents: List of all documents.
        batch_size: Documents per batch (max 512MB total per batch).
        max_workers: Number of parallel workers.

    Returns:
        Total rows affected.
    """
    batches = batch_documents(documents, batch_size)

    with logfire.span(
        "turbopuffer.parallel_upsert",
        total_docs=len(documents),
        batch_count=len(batches),
        max_workers=max_workers,
    ):
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(upsert_batch, ns, batch, idx) for idx, batch in enumerate(batches)]
            results = [f.result() for f in futures]

        return sum(results)


def main() -> None:
    logfire.configure()

    tpuf = turbopuffer.Turbopuffer(
        api_key=os.getenv("TURBOPUFFER_API_KEY"),
        region="gcp-us-central1",
    )

    ns = tpuf.namespace("batch-upsert-example")

    # Generate sample documents
    documents: list[DocumentRow] = []
    for i in range(10000):
        doc: DocumentRow = {"id": i, "vector": [float(i % 10) / 10] * 128, "title": f"Doc {i}"}
        documents.append(doc)

    total = parallel_upsert(ns, documents, batch_size=1000, max_workers=4)
    print(f"Upserted {total} documents")


if __name__ == "__main__":
    main()
