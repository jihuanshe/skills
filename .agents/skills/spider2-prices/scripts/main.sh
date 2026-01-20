#!/usr/bin/env bash
# =============================================================================
# Parquet Price Analysis Runner
# Usage: ./main.sh [TODAY] [BASELINE]
# Example: ./main.sh 260117 260110
# =============================================================================

set -euo pipefail

# Cross-platform date calculation
get_date_offset() {
  local offset=$1
  if date --version >/dev/null 2>&1; then
    # GNU date (Linux)
    date -d "${offset} days" +%y%m%d
  else
    # BSD date (macOS)
    date -v"${offset}d" +%y%m%d
  fi
}

# Default dates
TODAY="${1:-$(date +%y%m%d)}"
BASELINE="${2:-$(get_date_offset -7)}"

OUTPUT_DIR="data/analysis/${TODAY}"
mkdir -p "$OUTPUT_DIR"

echo "=== Parquet Price Analysis ==="
echo "Today: $TODAY, Baseline: $BASELINE"
echo "Output: $OUTPUT_DIR"
echo ""

# -----------------------------------------------------------------------------
# 1. Data Quality Check
# -----------------------------------------------------------------------------
echo ">>> 1. Data Quality Check"
duckdb -csv -c "
SELECT
  crawler,
  COUNT(*) AS rows,
  COUNT(DISTINCT product_url) AS distinct_url,
  ROUND(COUNT(*) * 1.0 / NULLIF(COUNT(DISTINCT product_url), 0), 3) AS dup_ratio
FROM 'dump_parquet/all/${TODAY}/**/*.parquet'
GROUP BY crawler
ORDER BY dup_ratio DESC
" > "$OUTPUT_DIR/01_dup_ratio.csv"
echo "  -> $OUTPUT_DIR/01_dup_ratio.csv"

# -----------------------------------------------------------------------------
# 2. Stock Coverage by Site
# -----------------------------------------------------------------------------
echo ">>> 2. Stock Coverage by Site"
duckdb -csv -c "
SELECT
  CASE
    WHEN crawler LIKE 'dorasuta%' THEN 'dorasuta'
    WHEN crawler LIKE 'cardrush%' THEN 'cardrush'
    WHEN crawler LIKE 'yuyu-tei%' THEN 'yuyu-tei'
    WHEN crawler LIKE 'hareruya%' THEN 'hareruya'
    WHEN crawler LIKE 'mercari%' THEN 'mercari'
    ELSE 'other'
  END as site,
  COUNT(*) AS total,
  SUM(CASE WHEN product_onsell_count IS NOT NULL AND product_onsell_count != '' AND TRY_CAST(product_onsell_count AS INTEGER) > 0 THEN 1 ELSE 0 END) AS has_stock,
  ROUND(SUM(CASE WHEN product_onsell_count IS NOT NULL AND product_onsell_count != '' AND TRY_CAST(product_onsell_count AS INTEGER) > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS coverage_pct
FROM 'dump_parquet/all/${TODAY}/**/*.parquet'
GROUP BY 1
ORDER BY coverage_pct DESC
" > "$OUTPUT_DIR/02_stock_coverage.csv"
echo "  -> $OUTPUT_DIR/02_stock_coverage.csv"

# -----------------------------------------------------------------------------
# 3. Price Changes by Game (7d)
# -----------------------------------------------------------------------------
echo ">>> 3. Price Changes by Game (7d)"
duckdb -csv -c "
WITH baseline AS (
  SELECT
    CASE
      WHEN crawler LIKE '%pokemon%' THEN 'Pokemon'
      WHEN crawler LIKE '%yugioh%' THEN 'Yu-Gi-Oh'
      WHEN crawler LIKE '%mtg%' THEN 'MTG'
      WHEN crawler LIKE '%onepiece%' THEN 'One Piece'
      WHEN crawler LIKE '%weiss%' THEN 'Weiss Schwarz'
      WHEN crawler LIKE '%vanguard%' THEN 'Vanguard'
      WHEN crawler LIKE '%duel%' THEN 'Duel Masters'
      WHEN crawler LIKE '%digimon%' THEN 'Digimon'
      ELSE 'Other'
    END as game,
    CASE WHEN crawler LIKE 'dorasuta%' THEN product_url || '|' || REGEXP_REPLACE(COALESCE(product_condition, ''), '\s+', '', 'g') ELSE product_url END as k,
    TRY_CAST(REGEXP_REPLACE(product_price, '[^0-9]', '', 'g') AS INTEGER) as price
  FROM 'dump_parquet/all/${BASELINE}/**/*.parquet'
  WHERE product_price IS NOT NULL AND product_price != ''
),
today AS (
  SELECT
    CASE
      WHEN crawler LIKE '%pokemon%' THEN 'Pokemon'
      WHEN crawler LIKE '%yugioh%' THEN 'Yu-Gi-Oh'
      WHEN crawler LIKE '%mtg%' THEN 'MTG'
      WHEN crawler LIKE '%onepiece%' THEN 'One Piece'
      WHEN crawler LIKE '%weiss%' THEN 'Weiss Schwarz'
      WHEN crawler LIKE '%vanguard%' THEN 'Vanguard'
      WHEN crawler LIKE '%duel%' THEN 'Duel Masters'
      WHEN crawler LIKE '%digimon%' THEN 'Digimon'
      ELSE 'Other'
    END as game,
    CASE WHEN crawler LIKE 'dorasuta%' THEN product_url || '|' || REGEXP_REPLACE(COALESCE(product_condition, ''), '\s+', '', 'g') ELSE product_url END as k,
    TRY_CAST(REGEXP_REPLACE(product_price, '[^0-9]', '', 'g') AS INTEGER) as price
  FROM 'dump_parquet/all/${TODAY}/**/*.parquet'
  WHERE product_price IS NOT NULL AND product_price != ''
)
SELECT
  t.game,
  COUNT(*) AS matched,
  ROUND((EXP(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY LN(t.price * 1.0 / b.price))) - 1) * 100, 2) AS median_pct,
  SUM(CASE WHEN t.price >= b.price * 1.1 THEN 1 ELSE 0 END) AS up_10pct,
  SUM(CASE WHEN t.price <= b.price * 0.9 THEN 1 ELSE 0 END) AS down_10pct,
  ROUND(SUM(CASE WHEN t.price >= b.price * 1.1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS up_rate,
  ROUND(SUM(CASE WHEN t.price <= b.price * 0.9 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS down_rate
FROM today t
JOIN baseline b ON t.k = b.k AND t.game = b.game
WHERE b.price >= 100 AND t.price > 0
  AND b.price NOT IN (99999, 999999, 9999999) AND t.price NOT IN (99999, 999999, 9999999)
GROUP BY t.game
ORDER BY median_pct DESC
" > "$OUTPUT_DIR/03_price_by_game.csv"
echo "  -> $OUTPUT_DIR/03_price_by_game.csv"

# -----------------------------------------------------------------------------
# 4. Inventory Value (3-tier)
# -----------------------------------------------------------------------------
echo ">>> 4. Inventory Value (3-tier)"
duckdb -csv -c "
WITH calc AS (
  SELECT
    CASE
      WHEN crawler LIKE 'dorasuta%' THEN 'dorasuta'
      WHEN crawler LIKE 'cardrush%' THEN 'cardrush'
      WHEN crawler LIKE 'yuyu-tei%' THEN 'yuyu-tei'
      WHEN crawler LIKE 'hareruya%' THEN 'hareruya'
      WHEN crawler LIKE 'mercari%' THEN 'mercari'
      ELSE 'other'
    END as site,
    TRY_CAST(REGEXP_REPLACE(product_price, '[^0-9]', '', 'g') AS BIGINT) as price,
    COALESCE(TRY_CAST(product_onsell_count AS INTEGER), 0) as stock
  FROM 'dump_parquet/all/${TODAY}/**/*.parquet'
  WHERE product_price IS NOT NULL AND product_price != ''
)
SELECT
  site,
  COUNT(*) AS sku,
  ROUND(SUM(price) / 1e9, 3) AS listing_value_B,
  ROUND(SUM(CASE WHEN stock > 0 THEN price * stock ELSE 0 END) / 1e9, 3) AS inventory_strict_B,
  ROUND(SUM(CASE WHEN stock > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS stock_coverage_pct
FROM calc
WHERE price > 0
  AND price NOT IN (99999, 999999, 9999999)
GROUP BY site
ORDER BY inventory_strict_B DESC
" > "$OUTPUT_DIR/04_inventory_value.csv"
echo "  -> $OUTPUT_DIR/04_inventory_value.csv"

# -----------------------------------------------------------------------------
# 5. Value Decomposition
# -----------------------------------------------------------------------------
echo ">>> 5. Value Decomposition"
duckdb -csv -c "
WITH t0 AS (
  SELECT
    crawler,
    CASE
      WHEN crawler LIKE 'dorasuta%' THEN 'dorasuta'
      WHEN crawler LIKE 'cardrush%' THEN 'cardrush'
      WHEN crawler LIKE 'yuyu-tei%' THEN 'yuyu-tei'
      WHEN crawler LIKE 'hareruya%' THEN 'hareruya'
      ELSE 'other'
    END as site,
    product_url,
    product_title,
    CASE WHEN crawler LIKE 'dorasuta%' THEN product_url || '|' || REGEXP_REPLACE(COALESCE(product_condition, ''), '\s+', '', 'g') ELSE product_url END as k,
    TRY_CAST(REGEXP_REPLACE(product_price, '[^0-9]', '', 'g') AS BIGINT) as price,
    COALESCE(TRY_CAST(product_onsell_count AS INTEGER), 0) as stock,
    ROW_NUMBER() OVER (PARTITION BY CASE WHEN crawler LIKE 'dorasuta%' THEN product_url || '|' || REGEXP_REPLACE(COALESCE(product_condition, ''), '\s+', '', 'g') ELSE product_url END ORDER BY TRY_CAST(REGEXP_REPLACE(product_price, '[^0-9]', '', 'g') AS BIGINT) DESC) as rn
  FROM 'dump_parquet/all/${TODAY}/**/*.parquet'
  WHERE product_price IS NOT NULL AND crawler NOT LIKE 'mercari%'
),
t7 AS (
  SELECT
    crawler,
    CASE
      WHEN crawler LIKE 'dorasuta%' THEN 'dorasuta'
      WHEN crawler LIKE 'cardrush%' THEN 'cardrush'
      WHEN crawler LIKE 'yuyu-tei%' THEN 'yuyu-tei'
      WHEN crawler LIKE 'hareruya%' THEN 'hareruya'
      ELSE 'other'
    END as site,
    product_url,
    CASE WHEN crawler LIKE 'dorasuta%' THEN product_url || '|' || REGEXP_REPLACE(COALESCE(product_condition, ''), '\s+', '', 'g') ELSE product_url END as k,
    TRY_CAST(REGEXP_REPLACE(product_price, '[^0-9]', '', 'g') AS BIGINT) as price,
    COALESCE(TRY_CAST(product_onsell_count AS INTEGER), 0) as stock,
    ROW_NUMBER() OVER (PARTITION BY CASE WHEN crawler LIKE 'dorasuta%' THEN product_url || '|' || REGEXP_REPLACE(COALESCE(product_condition, ''), '\s+', '', 'g') ELSE product_url END ORDER BY TRY_CAST(REGEXP_REPLACE(product_price, '[^0-9]', '', 'g') AS BIGINT) DESC) as rn
  FROM 'dump_parquet/all/${BASELINE}/**/*.parquet'
  WHERE product_price IS NOT NULL AND crawler NOT LIKE 'mercari%'
),
matched AS (
  SELECT
    a.site,
    a.k,
    b.price as p_old,
    a.price as p_new,
    b.stock as s_old,
    a.stock as s_new,
    b.stock * (a.price - b.price) as delta_price,
    b.price * (a.stock - b.stock) as delta_stock,
    (a.price - b.price) * (a.stock - b.stock) as delta_interaction,
    b.price * b.stock as old_val,
    a.price * a.stock as new_val
  FROM t0 a
  JOIN t7 b ON a.k = b.k AND a.site = b.site
  WHERE a.rn = 1 AND b.rn = 1 AND a.price > 0 AND b.price > 0
    AND a.price NOT IN (99999, 999999, 9999999) AND b.price NOT IN (99999, 999999, 9999999)
),
new_items AS (
  SELECT a.site, a.price * a.stock as new_val
  FROM t0 a
  LEFT JOIN t7 b ON a.k = b.k AND a.site = b.site
  WHERE a.rn = 1 AND b.k IS NULL AND a.price > 0
    AND a.price NOT IN (99999, 999999, 9999999)
),
removed_items AS (
  SELECT b.site, b.price * b.stock as old_val
  FROM t7 b
  LEFT JOIN t0 a ON a.k = b.k AND a.site = b.site
  WHERE b.rn = 1 AND a.k IS NULL AND b.price > 0
    AND b.price NOT IN (99999, 999999, 9999999)
)
SELECT
  m.site,
  COUNT(DISTINCT m.k) as matched_sku,
  ROUND(SUM(m.delta_price) / 1e6, 1) as delta_price_M,
  ROUND(SUM(m.delta_stock) / 1e6, 1) as delta_stock_M,
  ROUND(SUM(m.delta_interaction) / 1e6, 1) as delta_inter_M,
  ROUND((SUM(m.new_val) - SUM(m.old_val)) / 1e6, 1) as matched_delta_M,
  (SELECT COUNT(*) FROM new_items n WHERE n.site = m.site) as new_sku,
  (SELECT ROUND(SUM(new_val) / 1e6, 1) FROM new_items n WHERE n.site = m.site) as new_value_M,
  (SELECT COUNT(*) FROM removed_items r WHERE r.site = m.site) as removed_sku,
  (SELECT ROUND(SUM(old_val) / 1e6, 1) FROM removed_items r WHERE r.site = m.site) as removed_value_M
FROM matched m
GROUP BY m.site
ORDER BY matched_sku DESC
" > "$OUTPUT_DIR/05_decomposition.csv"
echo "  -> $OUTPUT_DIR/05_decomposition.csv"

# -----------------------------------------------------------------------------
# 6. Top 20 Value Contributors
# Note: Uses COALESCE(stock, 0) to match decomposition caliber (strict mode)
# -----------------------------------------------------------------------------
echo ">>> 6. Top 20 Value Contributors"
duckdb -csv -c "
WITH t0 AS (
  SELECT
    crawler,
    product_title,
    CASE WHEN crawler LIKE 'dorasuta%' THEN product_url || '|' || REGEXP_REPLACE(COALESCE(product_condition, ''), '\s+', '', 'g') ELSE product_url END as k,
    TRY_CAST(REGEXP_REPLACE(product_price, '[^0-9]', '', 'g') AS BIGINT) as price,
    COALESCE(TRY_CAST(product_onsell_count AS INTEGER), 0) as stock,
    ROW_NUMBER() OVER (PARTITION BY CASE WHEN crawler LIKE 'dorasuta%' THEN product_url || '|' || REGEXP_REPLACE(COALESCE(product_condition, ''), '\s+', '', 'g') ELSE product_url END ORDER BY TRY_CAST(REGEXP_REPLACE(product_price, '[^0-9]', '', 'g') AS BIGINT) DESC) as rn
  FROM 'dump_parquet/all/${TODAY}/**/*.parquet'
  WHERE product_price IS NOT NULL AND crawler NOT LIKE 'mercari%'
),
t7 AS (
  SELECT
    CASE WHEN crawler LIKE 'dorasuta%' THEN product_url || '|' || REGEXP_REPLACE(COALESCE(product_condition, ''), '\s+', '', 'g') ELSE product_url END as k,
    TRY_CAST(REGEXP_REPLACE(product_price, '[^0-9]', '', 'g') AS BIGINT) as price,
    COALESCE(TRY_CAST(product_onsell_count AS INTEGER), 0) as stock,
    ROW_NUMBER() OVER (PARTITION BY CASE WHEN crawler LIKE 'dorasuta%' THEN product_url || '|' || REGEXP_REPLACE(COALESCE(product_condition, ''), '\s+', '', 'g') ELSE product_url END ORDER BY TRY_CAST(REGEXP_REPLACE(product_price, '[^0-9]', '', 'g') AS BIGINT) DESC) as rn
  FROM 'dump_parquet/all/${BASELINE}/**/*.parquet'
  WHERE product_price IS NOT NULL AND crawler NOT LIKE 'mercari%'
),
changes AS (
  SELECT
    a.crawler,
    LEFT(a.product_title, 45) as title,
    b.price as p_old,
    a.price as p_new,
    b.stock as s_old,
    a.stock as s_new,
    a.price * a.stock - b.price * b.stock as delta_value
  FROM t0 a
  JOIN t7 b ON a.k = b.k
  WHERE a.rn = 1 AND b.rn = 1 AND a.price > 0 AND b.price > 0
    AND a.stock > 0 AND b.stock > 0
    AND a.price NOT IN (99999, 999999, 9999999) AND b.price NOT IN (99999, 999999, 9999999)
)
SELECT
  crawler,
  title,
  p_old,
  p_new,
  s_old,
  s_new,
  delta_value,
  ROUND(delta_value / 1000.0, 0) as delta_K
FROM changes
ORDER BY ABS(delta_value) DESC
LIMIT 20
" > "$OUTPUT_DIR/06_top_contributors.csv"
echo "  -> $OUTPUT_DIR/06_top_contributors.csv"

# -----------------------------------------------------------------------------
# 7. Validation Checks
# -----------------------------------------------------------------------------
echo ""
echo "=== Validation Checks ==="

echo ">>> Check 1: Placeholder prices"
duckdb -c "
SELECT
  crawler,
  SUM(CASE WHEN price IN (99999, 999999, 9999999) THEN 1 ELSE 0 END) as placeholder_count
FROM (
  SELECT crawler, TRY_CAST(REGEXP_REPLACE(product_price, '[^0-9]', '', 'g') AS BIGINT) as price
  FROM 'dump_parquet/all/${TODAY}/**/*.parquet'
)
GROUP BY crawler
HAVING placeholder_count > 0
ORDER BY placeholder_count DESC
"

echo ""
echo ">>> Check 2: Value decomposition consistency"
duckdb -c "
SELECT
  site,
  ROUND(delta_price_M + delta_stock_M + delta_inter_M, 1) as decomposed,
  matched_delta_M as actual,
  ROUND(ABS(delta_price_M + delta_stock_M + delta_inter_M - matched_delta_M), 2) as diff
FROM read_csv('$OUTPUT_DIR/05_decomposition.csv')
WHERE ABS(delta_price_M + delta_stock_M + delta_inter_M - matched_delta_M) > 0.1
"

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
echo ""
echo "=== Analysis Complete ==="
echo "Output files:"
ls -la "$OUTPUT_DIR"
