-- Case 4 | Step 3: where does the margin go?
-- Margin promised in the quote  ->  discounts  ->  costs above the estimate  ->  late penalties  ->  actual margin.
-- ROLLUP adds a total row. Orders without a cost estimate (about 1%) are left out so the bridge adds up exactly.

SELECT
  COALESCE(client_size, 'All clients')                  AS client_size,
  COUNT(*)                                              AS orders,
  ROUND(SUM(quoted_price - cost_estimate), 0)           AS margin_at_quote,
  ROUND(-SUM(quoted_price - final_price), 0)            AS discounts,
  ROUND(-SUM(total_cost - late_penalty - cost_estimate), 0) AS cost_above_estimate,
  ROUND(-SUM(late_penalty), 0)                          AS late_penalties,
  ROUND(SUM(margin), 0)                                 AS actual_margin
FROM orygamibox.fact_orders
WHERE cost_estimate IS NOT NULL
GROUP BY ROLLUP(client_size)
ORDER BY client_size;
