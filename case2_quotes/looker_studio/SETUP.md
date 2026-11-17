# Looker Studio dashboard - setup

`dashboard_preview.png` is a **static preview** of the dashboard layout. The live report is built in Looker Studio on top of BigQuery.

## 1. Load the data into BigQuery

Create a dataset called `orygamibox` and load:

| Table | File | Notes |
|---|---|---|
| `raw_quotes` | `data/raw/quotes.csv` | Schema: **all columns STRING** (do not auto-detect) |
| `clients` | `data/clean/clients.csv` | Auto-detect is fine |
| `orders` | `data/clean/orders.csv` | Auto-detect is fine |

Then run `sql/01_clean_quotes.sql`. It creates the view `orygamibox.clean_quotes`.

## 2. Connect Looker Studio

Add a BigQuery data source pointing at `orygamibox.clean_quotes`. Create two calculated fields:

```
response_bucket =
  CASE WHEN response_days <= 2 THEN "0-2 days"
       WHEN response_days <= 4 THEN "3-4 days"
       WHEN response_days <= 7 THEN "5-7 days"
       ELSE "8+ days" END

won = CASE WHEN status = "Won" THEN 1 ELSE 0 END
```

Win rate is the average of `won` over decided quotes. Add a filter on the page: `status` in (Won, Lost) and `client_id` is not UNKNOWN.

## 3. Page layout (one page)

| Area | Chart | Fields |
|---|---|---|
| Top row | 5 scorecards | Quotes sent, win rate, avg response days, win rate for 0-2 days, win rate for 8+ days |
| Left, middle | Bar chart | Dimension `response_bucket`, metric win rate |
| Right, middle | Line chart (one line per sector) | Dimension `response_bucket`, breakdown `sector`, metric win rate |
| Left, bottom | Clustered bars | Dimension markup quartile (from `04_price_vs_speed.sql`), breakdown speed, metric win rate |
| Right, bottom | Time series | Dimension month of `request_date`, metric win rate |

Page filters: date range, sector, client size, seller.

## 4. No BigQuery? Use the CSV files in this folder

`monthly_funnel.csv`, `response_buckets.csv`, `response_by_sector.csv`, `price_vs_speed.csv`, `sellers.csv` and `clean_quotes_for_dashboard.csv` contain the same tables. Upload them as data sources (CSV upload or Google Sheets).
