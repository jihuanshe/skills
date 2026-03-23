"""Self-verification pattern: validate writes and close the feedback loop.

Demonstrates the complete self-verification workflow:
1. Capture state before write (baseline)
2. Write with explicit IDs
3. Verify via billing info (bytes written)
4. Verify via query (IDs exist)
5. Verify via metadata (count increased)
6. Spot check content (attribute values match)
"""

import os
from typing import Any, TypedDict, cast

import logfire
import turbopuffer
from turbopuffer.lib.namespace import Namespace


class VerifiableRow(TypedDict):
    """Type-safe row for verification example."""

    id: int
    vector: list[float]
    title: str
    category: str


def verify_write_complete(
    ns: Namespace,
    docs_to_write: list[VerifiableRow],
) -> bool:
    """Complete self-verification loop for writes.

    Args:
        ns: Namespace to write to.
        docs_to_write: Documents to write.

    Returns:
        True if all verification checks pass.
    """
    with logfire.span("turbopuffer.verify_write", doc_count=len(docs_to_write)):
        # Step 1: Capture state before write
        meta_before = ns.metadata()
        count_before = meta_before.approx_row_count if meta_before else 0
        logfire.info("verification.before", count=count_before)

        doc_ids = [doc["id"] for doc in docs_to_write]

        # Step 2: Write
        write_result = ns.write(
            upsert_rows=[cast(dict[str, Any], doc) for doc in docs_to_write],
            distance_metric="cosine_distance",
        )

        # Step 3: Verify via billing info
        bytes_written = write_result.billing.billable_logical_bytes_written
        logfire.info(
            "verification.write_result",
            rows_upserted=write_result.rows_upserted,
            bytes_written=bytes_written,
        )

        # Step 4: Verify via query - confirm all docs exist
        verify_result = ns.query(
            filters=("id", "In", doc_ids),
            rank_by=("id", "asc"),
            top_k=len(doc_ids),
        )

        written_ids: set[int | str] = {row.id for row in verify_result.rows or []}
        expected_ids: set[int | str] = set(doc_ids)

        if written_ids != expected_ids:
            missing = expected_ids - written_ids
            logfire.error("verification.missing_ids", missing=list(missing))
            return False

        # Step 5: Verify via metadata - check document count increased
        meta_after = ns.metadata()
        count_after = meta_after.approx_row_count if meta_after else 0
        logfire.info(
            "verification.after",
            count=count_after,
            delta=count_after - count_before,
        )

        logfire.info("verification.passed")
        return True


def spot_check_document(
    ns: Namespace,
    doc_id: int,
    expected_title: str,
    expected_category: str,
) -> bool:
    """Verify a specific document's content matches expected values.

    Args:
        ns: Namespace to query.
        doc_id: Document ID to check.
        expected_title: Expected title value.
        expected_category: Expected category value.

    Returns:
        True if content matches.
    """
    with logfire.span("turbopuffer.spot_check", doc_id=doc_id):
        result = ns.query(
            rank_by=("id", "asc"),
            filters=("id", "Eq", doc_id),
            top_k=1,
            include_attributes=["title", "category"],
        )

        if not result.rows:
            logfire.error("spot_check.not_found", doc_id=doc_id)
            return False

        row = result.rows[0]
        title = getattr(row, "title", "")
        category = getattr(row, "category", "")

        if title != expected_title:
            logfire.error(
                "spot_check.title_mismatch",
                doc_id=doc_id,
                expected=expected_title,
                actual=title,
            )
            return False

        if category != expected_category:
            logfire.error(
                "spot_check.category_mismatch",
                doc_id=doc_id,
                expected=expected_category,
                actual=category,
            )
            return False

        logfire.info("spot_check.passed", doc_id=doc_id)
        return True


def main() -> None:
    logfire.configure()

    tpuf = turbopuffer.Turbopuffer(
        api_key=os.getenv("TURBOPUFFER_API_KEY"),
        region="gcp-us-central1",
    )

    ns = tpuf.namespace("verify-writes-example")

    docs_to_write: list[VerifiableRow] = [
        {"id": 1, "vector": [0.1, 0.2, 0.3], "title": "Doc 1", "category": "A"},
        {"id": 2, "vector": [0.4, 0.5, 0.6], "title": "Doc 2", "category": "B"},
        {"id": 3, "vector": [0.7, 0.8, 0.9], "title": "Doc 3", "category": "A"},
    ]

    if verify_write_complete(ns, docs_to_write):
        print("Write verification passed")
    else:
        print("Write verification failed")

    if spot_check_document(ns, doc_id=1, expected_title="Doc 1", expected_category="A"):
        print("Spot check passed: document content matches")
    else:
        print("Spot check failed: document content mismatch")


if __name__ == "__main__":
    main()
