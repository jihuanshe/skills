"""Multi-tenant pattern with namespace-per-tenant.

Demonstrates:
- Namespace isolation for tenants
- Cache warming per tenant
- Type-safe document operations
"""

import os
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, TypedDict, cast

import logfire
import turbopuffer

if TYPE_CHECKING:
    from turbopuffer.lib.namespace import Namespace


class TenantDocumentRow(TypedDict):
    """Type-safe row for tenant documents."""

    id: int
    vector: list[float]
    title: str


class TenantSearchService:
    """Search service with namespace-per-tenant pattern.

    Benefits of namespace-per-tenant:
    - Natural data isolation (no filter required)
    - Better query performance (smaller index per tenant)
    - Independent scaling and cache warming
    - Simplified access control
    """

    def __init__(self, region: str = "gcp-us-central1") -> None:
        self.tpuf = turbopuffer.Turbopuffer(
            api_key=os.getenv("TURBOPUFFER_API_KEY"),
            region=region,
        )

    def _namespace(self, tenant_id: str) -> "Namespace":
        """Get namespace for tenant."""
        return self.tpuf.namespace(f"tenant-{tenant_id}")

    def warm_cache(self, tenant_id: str) -> None:
        """Prewarm cache for tenant when session starts."""
        with logfire.span("turbopuffer.warm_cache", tenant_id=tenant_id):
            ns = self._namespace(tenant_id)
            ns.hint_cache_warm()

    def upsert_documents(
        self,
        tenant_id: str,
        documents: Sequence[TenantDocumentRow],
    ) -> int:
        """Upsert documents for tenant.

        Args:
            tenant_id: Tenant identifier.
            documents: List of documents with id, vector, and attributes.

        Returns:
            Number of rows affected.
        """
        with logfire.span(
            "turbopuffer.upsert",
            tenant_id=tenant_id,
            doc_count=len(documents),
        ):
            ns = self._namespace(tenant_id)
            result = ns.write(
                upsert_rows=[cast(dict[str, Any], doc) for doc in documents],
                distance_metric="cosine_distance",
            )
            return result.rows_affected

    def search(
        self,
        tenant_id: str,
        query_vector: Sequence[float],
        top_k: int = 10,
    ) -> list[dict[str, int | str | float]]:
        """Search documents for tenant.

        Args:
            tenant_id: Tenant identifier.
            query_vector: Query embedding.
            top_k: Number of results to return.

        Returns:
            List of result dicts with id, dist, and title.
        """
        with logfire.span(
            "turbopuffer.search",
            tenant_id=tenant_id,
            top_k=top_k,
        ):
            ns = self._namespace(tenant_id)
            result = ns.query(
                rank_by=("vector", "ANN", list(query_vector)),
                top_k=top_k,
                include_attributes=["title"],
            )
            results: list[dict[str, int | str | float]] = []
            for row in result.rows or []:
                dist = row["$dist"]
                title = getattr(row, "title", "")
                results.append({"id": row.id, "dist": float(dist), "title": str(title)})
            return results

    def delete_tenant_data(self, tenant_id: str) -> None:
        """Delete all data for tenant (e.g., on account deletion)."""
        with logfire.span("turbopuffer.delete_namespace", tenant_id=tenant_id):
            ns = self._namespace(tenant_id)
            ns.delete_all()


def main() -> None:
    logfire.configure()

    service = TenantSearchService()
    tenant_id = "acme-corp"

    service.warm_cache(tenant_id)

    documents: list[TenantDocumentRow] = [
        {"id": 1, "vector": [0.1, 0.2, 0.3], "title": "Doc 1"},
        {"id": 2, "vector": [0.4, 0.5, 0.6], "title": "Doc 2"},
    ]

    affected = service.upsert_documents(tenant_id, documents)
    print(f"Upserted {affected} docs")

    results = service.search(
        tenant_id=tenant_id,
        query_vector=[0.1, 0.2, 0.3],
        top_k=5,
    )

    print("Results:")
    for hit in results:
        print(f"  ID: {hit['id']}, Dist: {hit['dist']}, Title: {hit['title']}")


if __name__ == "__main__":
    main()
