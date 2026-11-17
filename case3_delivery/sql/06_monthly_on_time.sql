-- Case 3 | Step 6: on-time delivery by month, with a 3-month moving average (window function)

WITH monthly AS (
  SELECT
    DATE_TRUNC(delivered_date, MONTH) AS month,
    COUNT(*)                          AS orders,
    SUM(on_time)                      AS on_time_orders
  FROM orygamibox.order_delivery
  GROUP BY month
)
SELECT
  month,
  orders,
  ROUND(on_time_orders / orders, 3) AS on_time_rate,
  ROUND(SUM(on_time_orders) OVER (ORDER BY month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)
        / SUM(orders) OVER (ORDER BY month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 3) AS on_time_rate_3m
FROM monthly
ORDER BY month;
