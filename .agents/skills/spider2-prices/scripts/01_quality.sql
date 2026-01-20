-- Data Quality Checks
-- Run first to validate data before analysis
--
-- Assumptions:
--   - Query 1-2 intentionally scan all/**/* to discover date ranges (including hotfix dirs)
--   - Query 3+ use ${TODAY} to analyze a specific snapshot
--   - Hotfix directories (e.g., 260109_fix) are included in range discovery but excluded in analysis

-- 1. Check available date ranges (scans all dirs including hotfix)
SELECT
  MIN(ymd) as earliest,
  MAX(ymd) as latest,
  COUNT(DISTINCT ymd) as total_days
FROM 'dump_parquet/all/**/*.parquet';

-- 2. Daily record counts - detect anomalies (scans all dirs including hotfix)
SELECT
  ymd,
  COUNT(*) as records,
  COUNT(DISTINCT crawler) as crawlers
FROM 'dump_parquet/all/**/*.parquet'
GROUP BY ymd
ORDER BY ymd DESC
LIMIT 35;

-- 3. Check unique key duplicates per crawler
SELECT
  crawler,
  COUNT(*) AS rows,
  COUNT(DISTINCT product_url) AS distinct_url,
  ROUND(COUNT(*) * 1.0 / NULLIF(COUNT(DISTINCT product_url), 0), 3) AS dup_ratio
FROM 'dump_parquet/all/${TODAY}/**/*.parquet'
GROUP BY crawler
ORDER BY dup_ratio DESC;

-- 4. Check dorasuta url+condition uniqueness
SELECT
  crawler,
  COUNT(*) as total,
  COUNT(DISTINCT product_url || '|' || REGEXP_REPLACE(COALESCE(product_condition,''), '\s+', '', 'g')) as unique_keys,
  ROUND(COUNT(*) * 1.0 / NULLIF(COUNT(DISTINCT product_url || '|' || REGEXP_REPLACE(COALESCE(product_condition,''), '\s+', '', 'g')), 0), 3) as dup_ratio
FROM 'dump_parquet/all/${TODAY}/**/*.parquet'
WHERE crawler LIKE 'dorasuta%'
GROUP BY crawler;

-- 5. Check for nulls/zeros in key fields
SELECT
  crawler,
  COUNT(*) as total,
  SUM(CASE WHEN product_title IS NULL OR product_title = '' THEN 1 ELSE 0 END) as null_title,
  SUM(CASE WHEN product_price IS NULL OR product_price = '' THEN 1 ELSE 0 END) as null_price,
  SUM(CASE WHEN product_url IS NULL OR product_url = '' THEN 1 ELSE 0 END) as null_url,
  SUM(CASE WHEN TRY_CAST(REGEXP_REPLACE(product_price, '[^0-9]', '', 'g') AS INTEGER) = 0 THEN 1 ELSE 0 END) as zero_price,
  SUM(CASE WHEN TRY_CAST(REGEXP_REPLACE(product_price, '[^0-9]', '', 'g') AS INTEGER) > 10000000 THEN 1 ELSE 0 END) as extreme_price,
  ROUND(SUM(CASE WHEN product_title IS NULL OR product_title = '' OR product_price IS NULL OR product_price = '' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as null_pct
FROM 'dump_parquet/all/${TODAY}/**/*.parquet'
GROUP BY crawler
HAVING null_pct > 0 OR zero_price > 0 OR extreme_price > 0
ORDER BY null_pct DESC;

-- 6. Stock coverage by site
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
ORDER BY coverage_pct DESC;

-- 7. Check placeholder prices
SELECT
  crawler,
  SUM(CASE WHEN price IN (99999, 999999, 9999999) THEN 1 ELSE 0 END) as placeholder_count,
  ROUND(SUM(CASE WHEN price IN (99999, 999999, 9999999) THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as placeholder_pct
FROM (
  SELECT crawler, TRY_CAST(REGEXP_REPLACE(product_price, '[^0-9]', '', 'g') AS BIGINT) as price
  FROM 'dump_parquet/all/${TODAY}/**/*.parquet'
)
GROUP BY crawler
HAVING placeholder_count > 0
ORDER BY placeholder_count DESC;
