-- Case 4 - Profitability | Step 1: revenue, margin and rankings per client
-- Source: orygamibox.fact_orders (built by case4_profitability/consolidate.py, one row per order)
-- RANK() OVER gives each client's position; a running SUM() OVER gives the cumulative share of revenue.

WITH client AS (
  SELECT
    client_id,
    client_name,
    client_size,
    sector,
    COUNT(*)           AS orders,
    SUM(final_price)   AS revenue,
    SUM(margin)        AS margin,
    SUM(late_penalty)  AS penalties
  FROM orygamibox.fact_orders
  GROUP BY client_id, client_name, client_size, sector
)
SELECT
  client_id,
  client_name,
  client_size,
  sector,
  orders,
  ROUND(revenue, 0)                    AS revenue,
  ROUND(margin, 0)                     AS margin,
  ROUND(margin / revenue, 4)           AS margin_pct,
  RANK() OVER (ORDER BY revenue DESC)  AS revenue_rank,
  RANK() OVER (ORDER BY margin DESC)   AS margin_rank,
  RANK() OVER (ORDER BY margin / revenue DESC) AS margin_pct_rank,
  ROUND(SUM(revenue) OVER (ORDER BY revenue DESC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
        / SUM(revenue) OVER (), 4)     AS cumulative_revenue_share
FROM client
ORDER BY revenue DESC;
