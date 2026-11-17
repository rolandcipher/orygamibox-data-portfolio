-- Case 2 | Step 3: does the speed of our answer change the chance of winning?
-- Scope: decided quotes (Won / Lost) with a known response date and a known client.

WITH base AS (
  SELECT
    sector,
    response_days,
    IF(status = 'Won', 1, 0) AS won,
    CASE
      WHEN response_days <= 2 THEN '1) 0-2 days'
      WHEN response_days <= 4 THEN '2) 3-4 days'
      WHEN response_days <= 7 THEN '3) 5-7 days'
      ELSE '4) 8+ days'
    END AS response_bucket
  FROM orygamibox.clean_quotes
  WHERE status IN ('Won', 'Lost')
    AND response_days IS NOT NULL
    AND client_id != 'UNKNOWN'
)

-- 3a) overall
SELECT
  response_bucket,
  COUNT(*)                    AS quotes,
  SUM(won)                    AS won,
  ROUND(AVG(won), 4)          AS win_rate
FROM base
GROUP BY response_bucket
ORDER BY response_bucket;

-- 3b) the same by sector (run this query on its own)
-- SELECT
--   sector,
--   response_bucket,
--   COUNT(*)           AS quotes,
--   ROUND(AVG(won), 4) AS win_rate
-- FROM base
-- GROUP BY sector, response_bucket
-- ORDER BY sector, response_bucket;
