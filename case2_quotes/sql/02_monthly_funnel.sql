-- Case 2 | Step 2: monthly funnel and win rate
-- Window functions: cumulative win rate (SUM OVER) and a 3-month moving average (ROWS BETWEEN)

WITH monthly AS (
  SELECT
    DATE_TRUNC(request_date, MONTH)  AS month,
    COUNT(*)                         AS quotes_sent,
    COUNTIF(status IN ('Won', 'Lost')) AS decided,
    COUNTIF(status = 'Won')          AS won
  FROM orygamibox.clean_quotes
  GROUP BY month
)
SELECT
  month,
  quotes_sent,
  decided,
  won,
  ROUND(SAFE_DIVIDE(won, decided), 4) AS win_rate,
  ROUND(SAFE_DIVIDE(SUM(won) OVER (ORDER BY month),
                    SUM(decided) OVER (ORDER BY month)), 4) AS cumulative_win_rate,
  ROUND(AVG(SAFE_DIVIDE(won, decided)) OVER (
          ORDER BY month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 4) AS win_rate_3m_avg
FROM monthly
ORDER BY month;
