# Looker Studio dashboard - setup

`dashboard_preview.png` is a **static preview** of the layout. The live report is built in Looker Studio on top of BigQuery.

## 1. Load the data into BigQuery

Create the dataset `orygamibox` and load these files from `data/clean/` (auto-detect schema is fine; timestamps load as TIMESTAMP and dates as DATE):

`orders`, `quotes`, `clients`, `production_stages`, `machine_downtime`, `purchases`, `suppliers`.

Then run, in order: `sql/01_order_delivery.sql` and `sql/02_stage_times.sql` (they create the views `order_delivery` and `stage_times`). The other files are queries to run or to use as custom queries in Looker Studio.

## 2. Data sources

| Source | Where it comes from |
|---|---|
| `order_delivery` | BigQuery view from `01_order_delivery.sql` |
| `stage_times` | BigQuery view from `02_stage_times.sql` |
| Monthly on-time | `06_monthly_on_time.sql` as a custom query (or `monthly_on_time.csv`) |
| Promise vs reality | `07_promise_vs_reality.sql` (or `promise_vs_reality.csv`) |

## 3. Page layout

| Area | Chart | Fields |
|---|---|---|
| Top row | 5 scorecards | Orders, on-time rate (average of `on_time`), average days late, lead time P90, on-time rate in Q4 |
| Left, middle | Column chart | Dimension `order_size`, metric on-time rate |
| Right, middle | Bar chart | Dimension `stage`, metric total `wait_hours` (show as % of total) |
| Left, bottom | Time series | Dimension month of `delivered_date`, metric on-time rate |
| Right, bottom | Histogram-style column chart | Dimension `days_vs_promise` (bucketed), metric record count |
| Second page | Table with heat map | Rows `stage`, columns quarter, metric average `wait_hours` |

Filters: date range, sector, client size, order size.

## 4. No BigQuery? Use the CSV files in this folder

`order_delivery.csv`, `stage_times.csv`, `stage_percentiles.csv`, `monthly_on_time.csv`, `promise_vs_reality.csv` and `supplier_impact.csv` contain the same tables. Upload them as data sources.
