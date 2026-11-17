-- Case 3 - Delivery performance | Step 1: one row per delivered order with the delivery KPIs
-- Source tables (BigQuery dataset `orygamibox`, loaded from data/clean/): orders, quotes, clients,
--   production_stages, machine_downtime, purchases, suppliers

CREATE OR REPLACE VIEW orygamibox.order_delivery AS
SELECT
  o.order_id,
  o.client_id,
  c.sector,
  c.client_size,
  q.finish,
  q.quantity,
  CASE
    WHEN q.quantity < 1000  THEN '1) Under 1,000'
    WHEN q.quantity < 3000  THEN '2) 1,000-2,999'
    WHEN q.quantity < 10000 THEN '3) 3,000-9,999'
    ELSE '4) 10,000+'
  END AS order_size,
  o.approval_date,
  o.committed_date,
  o.delivered_date,
  o.purchase_id,
  DATE_DIFF(o.committed_date, o.approval_date, DAY) AS promised_days,
  DATE_DIFF(o.delivered_date, o.approval_date, DAY) AS lead_time_days,
  DATE_DIFF(o.delivered_date, o.committed_date, DAY) AS days_vs_promise,   -- positive = late
  IF(o.delivered_date <= o.committed_date, 1, 0)     AS on_time
FROM orygamibox.orders  o
JOIN orygamibox.quotes  q ON q.quote_id  = o.quote_id
JOIN orygamibox.clients c ON c.client_id = o.client_id
WHERE o.delivered_date IS NOT NULL;   -- open orders are excluded from delivery KPIs
