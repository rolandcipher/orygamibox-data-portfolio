-- Case 4 | Step 4: margin % by client size, sector, order size and finish

SELECT 'Client size' AS dimension, client_size AS segment,
       COUNT(*) AS orders, ROUND(SUM(final_price), 0) AS revenue, ROUND(SUM(margin), 0) AS margin,
       ROUND(SUM(margin) / SUM(final_price), 4) AS margin_pct
FROM orygamibox.fact_orders GROUP BY client_size
UNION ALL
SELECT 'Sector', sector, COUNT(*), ROUND(SUM(final_price), 0), ROUND(SUM(margin), 0), ROUND(SUM(margin) / SUM(final_price), 4)
FROM orygamibox.fact_orders GROUP BY sector
UNION ALL
SELECT 'Order size', order_size, COUNT(*), ROUND(SUM(final_price), 0), ROUND(SUM(margin), 0), ROUND(SUM(margin) / SUM(final_price), 4)
FROM orygamibox.fact_orders GROUP BY order_size
UNION ALL
SELECT 'Finish', IF(finish = 'No finish', 'No finish', 'With finish'), COUNT(*), ROUND(SUM(final_price), 0), ROUND(SUM(margin), 0), ROUND(SUM(margin) / SUM(final_price), 4)
FROM orygamibox.fact_orders GROUP BY IF(finish = 'No finish', 'No finish', 'With finish')
ORDER BY dimension, segment;
