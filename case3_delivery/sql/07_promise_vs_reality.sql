-- Case 3 | Step 7: are the delivery dates we promise realistic? Promised days vs actual lead time by order size.
-- P75 / P90 of the real lead time are candidates for a data-based promise.

SELECT
  order_size,
  COUNT(*)                                                    AS orders,
  ROUND(AVG(promised_days), 1)                                AS avg_promised_days,
  APPROX_QUANTILES(lead_time_days, 100)[OFFSET(50)]           AS actual_p50_days,
  APPROX_QUANTILES(lead_time_days, 100)[OFFSET(75)]           AS actual_p75_days,
  APPROX_QUANTILES(lead_time_days, 100)[OFFSET(90)]           AS actual_p90_days,
  ROUND(AVG(on_time), 3)                                      AS on_time_rate
FROM orygamibox.order_delivery
GROUP BY order_size
ORDER BY order_size;
