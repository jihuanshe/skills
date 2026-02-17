# Turbopuffer Skill Templates

This directory contains **reference templates** for using turbopuffer with type-safe patterns.

## Usage

These templates are meant to be **copied and adapted** into your actual Python packages, not imported directly from this skill directory.

```bash
# Copy templates to your package
cp .agents/skills/turbopuffer/templates/*.py packages/core/src/core/search/
```

## Type Checking Notes

- The templates pass `ruff check` (linting) and `ty check`
- When you copy templates to a proper Python package, type checking will work correctly

## Templates

| File                       | Description                           |
| -------------------------- | ------------------------------------- |
| `basic_vector_search.py`   | Basic vector search example           |
| `batch_upsert.py`          | Parallel batch upsert                 |
| `conditional_writes.py`    | Optimistic concurrency patterns       |
| `hybrid_search.py`         | Vector + BM25 + RRF fusion            |
| `multi_tenant.py`          | Namespace-per-tenant pattern          |
| `schema_optimized.py`      | f16, UUID, filterable:false           |
| `verify_writes.py`         | Complete self-verification loop       |
