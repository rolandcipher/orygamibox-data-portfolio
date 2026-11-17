-- Case 2 | Step 6: how often does each client come back?
-- LAG() looks at the previous quote of the same client.

WITH ordered AS (
  SELECT
    client_id,
    client_size,
    request_date,
    status,
    LAG(request_date) OVER (PARTITION BY client_id ORDER BY request_date, quote_id) AS previous_request_date,
    LAG(status)       OVER (PARTITION BY client_id ORDER BY request_date, quote_id) AS previous_status
  FROM orygamibox.clean_quotes
  WHERE client_id != 'UNKNOWN'
)
SELECT
  client_size,
  COUNT(*)                                                       AS quotes_with_a_previous_one,
  ROUND(AVG(DATE_DIFF(request_date, previous_request_date, DAY)), 1) AS avg_days_between_quotes,
  -- does a lost previous quote make the client less likely to win the next one?
  ROUND(AVG(IF(previous_status = 'Lost' AND status IN ('Won','Lost'), IF(status = 'Won', 1, 0), NULL)), 4) AS win_rate_after_a_loss,
  ROUND(AVG(IF(previous_status = 'Won'  AND status IN ('Won','Lost'), IF(status = 'Won', 1, 0), NULL)), 4) AS win_rate_after_a_win
FROM ordered
WHERE previous_request_date IS NOT NULL
GROUP BY client_size
ORDER BY client_size;
