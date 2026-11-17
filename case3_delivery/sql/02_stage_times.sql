-- Case 3 | Step 2: waiting time and processing time of every stage of every order
-- LAG() gives the end of the previous stage of the same order. For the first stage
-- the order is "ready" at approval, so its wait includes design / pre-press and any wait for material.

CREATE OR REPLACE VIEW orygamibox.stage_times AS
WITH sequenced AS (
  SELECT
    s.order_id,
    s.stage,
    s.machine_id,
    s.start_ts,
    s.end_ts,
    LAG(s.end_ts) OVER (PARTITION BY s.order_id ORDER BY s.start_ts) AS previous_end_ts,
    LEAD(s.stage) OVER (PARTITION BY s.order_id ORDER BY s.start_ts) AS next_stage,
    o.approval_date
  FROM orygamibox.production_stages s
  JOIN orygamibox.orders o ON o.order_id = s.order_id
)
SELECT
  order_id,
  stage,
  next_stage,
  machine_id,
  COALESCE(previous_end_ts, TIMESTAMP(approval_date)) AS ready_ts,
  start_ts,
  end_ts,
  TIMESTAMP_DIFF(start_ts, COALESCE(previous_end_ts, TIMESTAMP(approval_date)), MINUTE) / 60.0 AS wait_hours,
  TIMESTAMP_DIFF(end_ts, start_ts, MINUTE) / 60.0                                          AS process_hours
FROM sequenced;
