-- Top Contributors
-- Top SKUs driving value change
-- Variables: ${TODAY}, ${BASELINE}
--
-- Assumptions:
--   - Uses COALESCE(stock, 0) to match decomposition.sql caliber (strict mode)
--   - Excludes mercari (no stock data)
--   - Excludes placeholder prices (999999, 9999999)

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
  WHERE a.rn = 1 AND b.rn = 1
    AND a.price > 0 AND b.price > 0
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
LIMIT 20;
