-- Case 4 | Step 5: split the clients into four groups by margin % (NTILE) and see how much revenue each group brings

WITH client AS (
  SELECT client_id, client_size, SUM(final_price) AS revenue, SUM(margin) AS margin
  FROM orygamibox.fact_orders
  GROUP BY client_id, client_size
),
ranked AS (
  SELECT *, margin / revenue AS margin_pct, NTILE(4) OVER (ORDER BY margin / revenue DESC) AS margin_quartile
  FROM client
)
SELECT
  margin_quartile,
  COUNT(*)                                                    AS clients,
  COUNTIF(client_size = 'Large')                              AS large_clients,
  ROUND(SUM(revenue), 0)                                      AS revenue,
  ROUND(SUM(revenue) / SUM(SUM(revenue)) OVER (), 4)          AS share_of_revenue,
  ROUND(SUM(margin) / SUM(revenue), 4)                        AS margin_pct
FROM ranked
GROUP BY margin_quartile
ORDER BY margin_quartile;
