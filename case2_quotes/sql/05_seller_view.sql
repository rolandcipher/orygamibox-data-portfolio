-- Case 2 | Step 5: seller performance, and how much of it is just response speed
-- RANK() OVER orders the sellers; the second part compares sellers inside the same response bucket.

WITH base AS (
  SELECT
    seller,
    IF(status = 'Won', 1, 0) AS won,
    response_days,
    CASE WHEN response_days <= 4 THEN 'Fast (0-4 days)' ELSE 'Slow (5+ days)' END AS speed
  FROM orygamibox.clean_quotes
  WHERE status IN ('Won', 'Lost')
    AND response_days IS NOT NULL
    AND client_id != 'UNKNOWN'
),
by_seller AS (
  SELECT
    seller,
    COUNT(*)                  AS quotes,
    ROUND(AVG(response_days), 2) AS avg_response_days,
    ROUND(AVG(won), 4)        AS win_rate
  FROM base
  GROUP BY seller
)
SELECT
  seller,
  quotes,
  avg_response_days,
  win_rate,
  RANK() OVER (ORDER BY win_rate DESC)          AS win_rate_rank,
  RANK() OVER (ORDER BY avg_response_days ASC)  AS speed_rank
FROM by_seller
ORDER BY win_rate_rank;

-- 5b) win rate by seller inside each speed group (run on its own)
-- SELECT seller, speed, COUNT(*) AS quotes, ROUND(AVG(won), 4) AS win_rate
-- FROM base
-- GROUP BY seller, speed
-- ORDER BY speed, seller;
