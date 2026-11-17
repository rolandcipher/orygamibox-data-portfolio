-- Case 3 | Step 3: where does the time go? P50 and P90 per stage, and each stage's share of all waiting time
-- APPROX_QUANTILES is BigQuery's percentile function (approximate, accurate enough for ~6,000 rows).
-- SUM(SUM(x)) OVER () divides each stage's total by the grand total.

SELECT
  stage,
  COUNT(*)                                              AS runs,
  ROUND(APPROX_QUANTILES(wait_hours, 100)[OFFSET(50)], 1)    AS wait_p50_hours,
  ROUND(APPROX_QUANTILES(wait_hours, 100)[OFFSET(90)], 1)    AS wait_p90_hours,
  ROUND(APPROX_QUANTILES(process_hours, 100)[OFFSET(50)], 1) AS process_p50_hours,
  ROUND(APPROX_QUANTILES(process_hours, 100)[OFFSET(90)], 1) AS process_p90_hours,
  ROUND(SUM(wait_hours) / SUM(SUM(wait_hours)) OVER (), 3)   AS share_of_total_waiting
FROM orygamibox.stage_times
GROUP BY stage
ORDER BY share_of_total_waiting DESC;
