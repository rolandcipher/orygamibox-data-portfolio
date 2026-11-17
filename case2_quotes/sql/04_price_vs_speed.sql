-- Case 2 | Step 4: price (markup over estimated cost) vs speed of response
-- NTILE(4) splits the quotes into four equal-sized groups by markup.

WITH base AS (
  SELECT
    IF(status = 'Won', 1, 0)                 AS won,
    markup,
    IF(response_days <= 4, 'Fast (0-4 days)', 'Slow (5+ days)') AS speed
  FROM orygamibox.clean_quotes
  WHERE status IN ('Won', 'Lost')
    AND response_days IS NOT NULL
    AND markup IS NOT NULL
    AND client_id != 'UNKNOWN'
),
tiered AS (
  SELECT *, NTILE(4) OVER (ORDER BY markup) AS markup_quartile
  FROM base
)
SELECT
  markup_quartile,
  speed,
  COUNT(*)              AS quotes,
  ROUND(AVG(markup), 3) AS avg_markup,
  ROUND(AVG(won), 4)    AS win_rate
FROM tiered
GROUP BY markup_quartile, speed
ORDER BY markup_quartile, speed;
