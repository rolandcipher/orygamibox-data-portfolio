-- Case 3 | Step 5: do late material deliveries delay our orders?
-- Orders that triggered a purchase (purchase_id is not null) wait for that supplier.

WITH po AS (
  SELECT
    purchase_id,
    supplier_id,
    DATE_DIFF(received_date, promised_date, DAY) AS days_late
  FROM orygamibox.purchases
  WHERE received_date IS NOT NULL
)
SELECT
  s.supplier_id,
  s.supplier_name,
  s.main_material,
  COUNT(DISTINCT po.purchase_id)         AS purchases,
  ROUND(AVG(po.days_late), 2)            AS avg_days_late_vs_promise,
  COUNT(od.order_id)                     AS orders_waiting_for_it,
  ROUND(AVG(od.on_time), 3)              AS on_time_rate_of_those_orders
FROM orygamibox.suppliers s
JOIN po ON po.supplier_id = s.supplier_id
LEFT JOIN orygamibox.order_delivery od ON od.purchase_id = po.purchase_id
GROUP BY s.supplier_id, s.supplier_name, s.main_material
ORDER BY avg_days_late_vs_promise DESC;
