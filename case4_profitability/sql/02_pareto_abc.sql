-- Case 4 | Step 2: ABC classification of clients by revenue, and what each class contributes to margin
-- A = clients that together make the first 80% of revenue, B = next 15%, C = last 5%.

WITH client AS (
  SELECT client_id, SUM(final_price) AS revenue, SUM(margin) AS margin
  FROM orygamibox.fact_orders
  GROUP BY client_id
),
cumulative AS (
  SELECT
    client_id, revenue, margin,
    SUM(revenue) OVER (ORDER BY revenue DESC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
      / SUM(revenue) OVER () AS cum_share,
    SUM(revenue) OVER (ORDER BY revenue DESC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) - revenue
      AS previous_cum_revenue,
    SUM(revenue) OVER () AS total_revenue
  FROM client
),
classified AS (
  SELECT
    *,
    CASE
      WHEN previous_cum_revenue / total_revenue < 0.80 THEN 'A'
      WHEN previous_cum_revenue / total_revenue < 0.95 THEN 'B'
      ELSE 'C'
    END AS abc_class
  FROM cumulative
)
SELECT
  abc_class,
  COUNT(*)                                          AS clients,
  ROUND(SUM(revenue) / MAX(total_revenue), 4)       AS share_of_revenue,
  ROUND(SUM(margin) / SUM(SUM(margin)) OVER (), 4)  AS share_of_margin,
  ROUND(SUM(margin) / SUM(revenue), 4)              AS margin_pct
FROM classified
GROUP BY abc_class
ORDER BY abc_class;
