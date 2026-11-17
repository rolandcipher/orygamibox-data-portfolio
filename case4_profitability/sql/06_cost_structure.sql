-- Case 4 | Step 6: cost structure by client size (share of total cost per component)

SELECT
  client_size,
  ROUND(SUM(material_cost)     / SUM(total_cost), 3) AS material,
  ROUND(SUM(consumables_cost)  / SUM(total_cost), 3) AS consumables,
  ROUND(SUM(machine_cost)      / SUM(total_cost), 3) AS machine_time,
  ROUND(SUM(labor_cost)        / SUM(total_cost), 3) AS labor,
  ROUND(SUM(logistics_cost + tooling_cost) / SUM(total_cost), 3) AS logistics_and_tooling,
  ROUND(SUM(late_penalty)      / SUM(total_cost), 3) AS late_penalties,
  ROUND(AVG(discount_pct), 4)                        AS avg_discount
FROM orygamibox.fact_orders
GROUP BY client_size
ORDER BY client_size;
