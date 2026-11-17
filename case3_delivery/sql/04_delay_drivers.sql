-- Case 3 | Step 4: what is different about the orders that arrive late?
-- Each order's elapsed time is split into three parts that add up:
--   pre_production_days = approval -> start of printing (design, pre-press, waiting for material)
--   between_stage_days  = waiting between the following stages (queues, hand-offs)
--   process_days        = time on the machines or in inspection
-- Machine downtime that overlaps those windows is reported separately (it is not added to the three parts).

WITH downtime_per_order AS (
  SELECT
    st.order_id,
    SUM(GREATEST(0, TIMESTAMP_DIFF(LEAST(st.end_ts, d.end_ts), GREATEST(st.ready_ts, d.start_ts), MINUTE))) / 60.0 / 24.0
      AS downtime_days
  FROM orygamibox.stage_times st
  JOIN orygamibox.machine_downtime d
    ON d.machine_id = st.machine_id
   AND d.start_ts < st.end_ts
   AND d.end_ts   > st.ready_ts
  GROUP BY st.order_id
),
parts AS (
  SELECT
    order_id,
    SUM(IF(stage = 'Printing', wait_hours, 0)) / 24.0  AS pre_production_days,
    SUM(IF(stage != 'Printing', wait_hours, 0)) / 24.0 AS between_stage_days,
    SUM(process_hours) / 24.0                          AS process_days
  FROM orygamibox.stage_times
  GROUP BY order_id
)
SELECT
  IF(od.on_time = 1, 'On time', 'Late')             AS delivery,
  COUNT(*)                                          AS orders,
  ROUND(AVG(p.pre_production_days), 2)              AS avg_pre_production_days,
  ROUND(AVG(p.between_stage_days), 2)               AS avg_between_stage_days,
  ROUND(AVG(p.process_days), 2)                     AS avg_process_days,
  ROUND(AVG(COALESCE(dt.downtime_days, 0)), 2)      AS avg_downtime_days_overlapping
FROM orygamibox.order_delivery od
JOIN parts p ON p.order_id = od.order_id
LEFT JOIN downtime_per_order dt ON dt.order_id = od.order_id
GROUP BY delivery
ORDER BY delivery DESC;
