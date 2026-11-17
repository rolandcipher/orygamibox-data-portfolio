# Data dictionary

Synthetic data for a fictional company. Period: January 2024 - December 2025 (data snapshot: 31 January 2026).
Raw files are in `data/raw/` (with errors). Cleaned files are in `data/clean/` (produced by `pipelines/clean_data.py`). Every cleaning decision is listed in `docs/cleaning_log.csv`.

## Relationships

```
clients 1--N quotes 1--0..1 orders 1--N production_stages
                                 |           \-- N:1 machines
                                 +--1:1 order_costs
                                 +--N:1 purchases N:1 suppliers
machines 1--N machine_downtime
fact_orders = orders + order_costs + quotes + clients + scrap (built in Case 4)
```

## Tables

| Table | One row per | Key | Rows (clean) |
|---|---|---|---|
| clients | client | client_id | 60 |
| quotes | quote request | quote_id | 3,000 |
| orders | won quote | order_id | 1,135 |
| production_stages | order x stage | stage_record_id | 6,210 |
| machines | machine | machine_id | 8 |
| machine_downtime | stoppage | downtime_id | 640 |
| suppliers | supplier | supplier_id | 12 |
| purchases | purchase order | purchase_id | 399 |
| order_costs | order | order_id | 1,135 |
| fact_orders | order | order_id | 1,135 |

## Fields

**clients:** client_id, client_name, sector (Cosmetics, Food & Beverage, E-commerce & Fashion, Technology), client_size (Small, Medium, Large), city, signup_date, late_penalty_clause (true if the contract has a penalty for late delivery).

**quotes:** quote_id, client_id, request_date, response_date, board_type (SBS, Coated, Kraft, Microflute), gsm (board weight), print_type (Offset, Digital), finish (No finish, Matte lamination, Emboss, Foil), length_mm, width_mm, height_mm, quantity, cost_estimate (USD, standard cost used for the quote), quoted_price (USD), status (Won, Lost, Pending), loss_reason, seller. Added in the clean version: response_days, markup (quoted_price / cost_estimate), sector, client_size.

**orders:** order_id, quote_id, client_id, approval_date, committed_date (promised delivery), delivered_date (empty if still open at the snapshot), qty_ordered, qty_delivered, final_price (USD, after discount), purchase_id (set if a purchase of board had to be made for this order).

**production_stages:** stage_record_id, order_id, stage (Printing, Finishing, Die-cutting, Gluing, Quality control, Dispatch), machine_id (empty for quality control and dispatch), shift (Morning 06-14, Afternoon 14-22, Night 22-06, by start time), start_ts, end_ts, qty_in (pieces entering the stage), qty_out, scrap_units, scrap_reason. Added in the clean version: duration_hours.

**machines:** machine_id, machine_name, stage, install_year.

**machine_downtime:** downtime_id, machine_id, start_ts, end_ts, cause (Breakdown, Scheduled maintenance, Changeover, Waiting for material, Other, Unknown). Added: duration_hours.

**suppliers:** supplier_id, supplier_name, main_material.

**purchases:** purchase_id, supplier_id, material, order_date, promised_date, received_date, quantity_m2, unit_price. Added: days_late (received - promised).

**order_costs (USD):** order_id, material_unit_cost (per piece), material_cost (pieces released x unit cost), consumables_cost (ink, varnish, foil), machine_cost (hours x machine rate), labor_cost, logistics_cost, tooling_cost (cutting die), late_penalty.

**fact_orders:** order-level table for Case 4 with the order, client and quote attributes, all cost components, total_cost, margin, margin_pct, discount_pct, scrap_units, scrap_cost, material_cost_estimate and days_vs_promise.

## Data quality rules applied in the cleaning pipeline

| Rule | Check |
|---|---|
| Dates | Parsed from two formats (YYYY-MM-DD and DD/MM/YYYY) into one date type |
| Categories | Only the canonical labels listed above are allowed |
| Dimensions | Lengths are 60-400 mm; smaller values are treated as cm and multiplied by 10 |
| Quantities | qty_in and scrap_units cannot be negative; qty_in - scrap_units = qty_out on every row |
| Time order | end_ts cannot be earlier than start_ts |
| Keys | order_id in production_stages must exist in orders; client_id in quotes must exist in clients |
| Duplicates | Same quote content under different quote_id = one quote; identical stage rows are dropped |
| Missing values | Never guessed for categories ("Not recorded", "Unknown"); numeric costs are estimated with a documented rule |
