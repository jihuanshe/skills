-- Price Change Analysis (7-day comparison)
-- Variables: ${TODAY}, ${BASELINE}
--
-- Note: Uses url|condition as unique key for dorasuta to avoid JOIN inflation.
-- Excludes placeholder prices (99999, 999999, 9999999).

-- 1. Price changes by game type with median log return
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
ORDER BY median_pct DESC;

-- 2. Price changes by site
WITH baseline AS (
  SELECT
    CASE
      WHEN crawler LIKE 'dorasuta%' THEN 'dorasuta'
      WHEN crawler LIKE 'cardrush%' THEN 'cardrush'
      WHEN crawler LIKE 'yuyu-tei%' THEN 'yuyu-tei'
      WHEN crawler LIKE 'hareruya%' THEN 'hareruya'
      ELSE 'other'
    END as site,
    CASE WHEN crawler LIKE 'dorasuta%' THEN product_url || '|' || REGEXP_REPLACE(COALESCE(product_condition, ''), '\s+', '', 'g') ELSE product_url END as k,
    TRY_CAST(REGEXP_REPLACE(product_price, '[^0-9]', '', 'g') AS INTEGER) as price
  FROM 'dump_parquet/all/${BASELINE}/**/*.parquet'
  WHERE product_price IS NOT NULL AND crawler NOT LIKE 'mercari%'
),
today AS (
  SELECT
    CASE
      WHEN crawler LIKE 'dorasuta%' THEN 'dorasuta'
      WHEN crawler LIKE 'cardrush%' THEN 'cardrush'
      WHEN crawler LIKE 'yuyu-tei%' THEN 'yuyu-tei'
      WHEN crawler LIKE 'hareruya%' THEN 'hareruya'
      ELSE 'other'
    END as site,
    CASE WHEN crawler LIKE 'dorasuta%' THEN product_url || '|' || REGEXP_REPLACE(COALESCE(product_condition, ''), '\s+', '', 'g') ELSE product_url END as k,
    TRY_CAST(REGEXP_REPLACE(product_price, '[^0-9]', '', 'g') AS INTEGER) as price
  FROM 'dump_parquet/all/${TODAY}/**/*.parquet'
  WHERE product_price IS NOT NULL AND crawler NOT LIKE 'mercari%'
)
SELECT
  t.site,
  COUNT(*) AS matched,
  ROUND((EXP(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY LN(t.price * 1.0 / b.price))) - 1) * 100, 2) AS median_pct,
  SUM(CASE WHEN t.price >= b.price * 1.1 THEN 1 ELSE 0 END) AS up_10pct,
  SUM(CASE WHEN t.price <= b.price * 0.9 THEN 1 ELSE 0 END) AS down_10pct,
  ROUND(SUM(CASE WHEN t.price >= b.price * 1.1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS up_rate,
  ROUND(SUM(CASE WHEN t.price <= b.price * 0.9 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS down_rate
FROM today t
JOIN baseline b ON t.k = b.k AND t.site = b.site
WHERE b.price >= 100 AND t.price > 0
  AND b.price NOT IN (99999, 999999, 9999999) AND t.price NOT IN (99999, 999999, 9999999)
GROUP BY t.site
ORDER BY median_pct DESC;

-- 3. Top 20 gainers
WITH baseline AS (
  SELECT crawler, product_url, product_title,
    TRY_CAST(REGEXP_REPLACE(product_price, '[^0-9]', '', 'g') AS INTEGER) as price
  FROM 'dump_parquet/all/${BASELINE}/**/*.parquet'
  WHERE product_price IS NOT NULL AND product_price != ''
),
today AS (
  SELECT crawler, product_url, product_title,
    TRY_CAST(REGEXP_REPLACE(product_price, '[^0-9]', '', 'g') AS INTEGER) as price
  FROM 'dump_parquet/all/${TODAY}/**/*.parquet'
  WHERE product_price IS NOT NULL AND product_price != ''
)
SELECT
  t.crawler,
  LEFT(t.product_title, 50) as title,
  b.price as old_price,
  t.price as new_price,
  t.price - b.price as diff,
  ROUND((t.price - b.price) * 100.0 / b.price, 0) as pct
FROM today t
JOIN baseline b ON t.product_url = b.product_url
WHERE b.price >= 500 AND t.price > b.price
  AND b.price NOT IN (99999, 999999, 9999999) AND t.price NOT IN (99999, 999999, 9999999)
ORDER BY t.price - b.price DESC
LIMIT 20;

-- 4. Top 20 losers
WITH baseline AS (
  SELECT crawler, product_url, product_title,
    TRY_CAST(REGEXP_REPLACE(product_price, '[^0-9]', '', 'g') AS INTEGER) as price
  FROM 'dump_parquet/all/${BASELINE}/**/*.parquet'
  WHERE product_price IS NOT NULL AND product_price != ''
),
today AS (
  SELECT crawler, product_url, product_title,
    TRY_CAST(REGEXP_REPLACE(product_price, '[^0-9]', '', 'g') AS INTEGER) as price
  FROM 'dump_parquet/all/${TODAY}/**/*.parquet'
  WHERE product_price IS NOT NULL AND product_price != ''
)
SELECT
  t.crawler,
  LEFT(t.product_title, 50) as title,
  b.price as old_price,
  t.price as new_price,
  t.price - b.price as diff,
  ROUND((t.price - b.price) * 100.0 / b.price, 0) as pct
FROM today t
JOIN baseline b ON t.product_url = b.product_url
WHERE b.price >= 500 AND t.price < b.price
  AND b.price NOT IN (99999, 999999, 9999999) AND t.price NOT IN (99999, 999999, 9999999)
ORDER BY b.price - t.price DESC
LIMIT 20;
