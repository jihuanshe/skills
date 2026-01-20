-- Inventory Value Analysis
-- Variables: ${TODAY}

-- 1. Inventory value by site (3-tier)
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
ORDER BY inventory_strict_B DESC;

-- 2. Inventory value comparison across dates (30d, 7d, today)
-- Update dates as needed
WITH calc AS (
  SELECT
    ymd,
    CASE
      WHEN crawler LIKE 'dorasuta%' THEN 'dorasuta'
      WHEN crawler LIKE 'cardrush%' THEN 'cardrush'
      WHEN crawler LIKE 'yuyu-tei%' THEN 'yuyu-tei'
      WHEN crawler LIKE 'hareruya%' THEN 'hareruya'
      WHEN crawler LIKE 'mercari%' THEN 'mercari'
    END as site,
    TRY_CAST(REGEXP_REPLACE(product_price, '[^0-9]', '', 'g') AS BIGINT) as price,
    COALESCE(TRY_CAST(product_onsell_count AS INTEGER), 0) as stock
  FROM 'dump_parquet/all/**/*.parquet'
  WHERE product_price IS NOT NULL AND product_price != ''
    AND ymd IN ('${BASELINE_30D}', '${BASELINE}', '${TODAY}')
),
daily AS (
  SELECT
    ymd, site,
    SUM(stock) as total_units,
    SUM(price * stock) as inventory_value
  FROM calc
  WHERE price > 0 AND stock > 0
    AND price NOT IN (99999, 999999, 9999999)
  GROUP BY ymd, site
)
SELECT
  site,
  ROUND(MAX(CASE WHEN ymd = '${BASELINE_30D}' THEN inventory_value END) / 1e9, 2) as value_30d_B,
  ROUND(MAX(CASE WHEN ymd = '${BASELINE}' THEN inventory_value END) / 1e9, 2) as value_7d_B,
  ROUND(MAX(CASE WHEN ymd = '${TODAY}' THEN inventory_value END) / 1e9, 2) as value_now_B,
  ROUND((MAX(CASE WHEN ymd = '${TODAY}' THEN inventory_value END) - MAX(CASE WHEN ymd = '${BASELINE}' THEN inventory_value END)) / 1e9, 2) as delta_7d_B
FROM daily
GROUP BY site
ORDER BY value_now_B DESC;
