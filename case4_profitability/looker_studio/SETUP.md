# Looker Studio dashboard - setup

`dashboard_preview.png` is a **static preview** of the layout. The live report is built in Looker Studio on top of BigQuery.

## 1. Build and load the data

```bash
python pipelines/clean_data.py
python case4_profitability/consolidate.py      # creates data/clean/fact_orders.csv
```
In BigQuery, create the dataset `orygamibox` and load `data/clean/fact_orders.csv` as `orygamibox.fact_orders` (auto-detect schema is fine).

## 2. Data sources

| Source | How |
|---|---|
| `fact_orders` | BigQuery table (one row per order, with margin already calculated) |
| Client ranking and Pareto | `sql/01_client_profitability.sql` as a custom query (or `client_profitability.csv`) |
| Margin bridge | `sql/03_margin_bridge.sql` (or `margin_bridge.csv`) |
| Segments | `sql/04_margin_by_segment.sql` (or `margin_by_segment.csv`) |

## 3. Page layout

| Area | Chart | Fields |
|---|---|---|
| Top row | 5 scorecards | Revenue (sum `final_price`), margin (sum `margin`), margin % (calculated field: `SUM(margin) / SUM(final_price)`), large-client share of revenue, large-client share of margin |
| Left, middle | Clustered columns | Dimension `client_size`, metrics share of revenue and share of margin (use "percent of total" comparison) |
| Right, middle | Scatter chart | One point per client from `client_profitability`: X revenue, Y margin %, colour `client_size` |
| Left, bottom | Waterfall chart | Data from `margin_bridge` (steps in order) |
| Right, bottom | Combo / Pareto | Clients ranked by revenue, cumulative revenue share from `01_client_profitability.sql` |
| Second page | Table | Clients with revenue, margin, margin %, rank, with conditional formatting on margin % (red under 10%) |

Filters: date range (`approval_date`), sector, client size, order size.

## 4. No BigQuery? Use the CSV files in this folder

`fact_orders.csv`, `client_profitability.csv`, `margin_by_segment.csv` and `margin_bridge.csv` hold the same tables. Upload them as data sources.
