-- Value Decomposition
-- Decompose value change: price effect vs stock effect vs interaction vs new/removed
-- Variables: ${TODAY}, ${BASELINE}

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
    -- Price effect: s_old × Δp (无条件计算以保持恒等式)
    b.stock * (a.price - b.price) as delta_price,
    -- Stock effect: p_old × Δs
    b.price * (a.stock - b.stock) as delta_stock,
    -- Interaction: Δp × Δs
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
ORDER BY matched_sku DESC;
