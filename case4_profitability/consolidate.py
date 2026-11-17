"""
Case 4 - Step 1: consolidate the clean tables into one fact table with one row per order.

Joins orders, order_costs, quotes, clients and production_stages and calculates margin.
Output: data/clean/fact_orders.csv   (this is the table loaded into BigQuery as `orygamibox.fact_orders`)
Run from the project root:  python case4_profitability/consolidate.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipelines"))
from common import CLEAN, load  # noqa: E402

orders = load("orders", ["approval_date", "committed_date", "delivered_date"])
costs = load("order_costs")
quotes = load("quotes")
clients = load("clients")
stages = load("production_stages")

scrap = (stages[stages["stage"] != "Dispatch"].groupby("order_id")["scrap_units"].sum().rename("scrap_units"))

f = (orders.merge(costs, on="order_id", how="left")
     .merge(quotes[["quote_id", "finish", "quantity", "quoted_price", "cost_estimate"]], on="quote_id", how="left")
     .merge(clients[["client_id", "client_name", "sector", "client_size"]], on="client_id", how="left")
     .merge(scrap, on="order_id", how="left"))

cost_cols = ["material_cost", "consumables_cost", "machine_cost", "labor_cost", "logistics_cost", "tooling_cost"]
f["total_cost"] = (f[cost_cols].sum(axis=1) + f["late_penalty"]).round(2)
f["margin"] = (f["final_price"] - f["total_cost"]).round(2)
f["margin_pct"] = (f["margin"] / f["final_price"]).round(4)
f["discount_pct"] = (1 - f["final_price"] / f["quoted_price"]).round(4)
f["scrap_cost"] = (f["scrap_units"] * f["material_unit_cost"]).round(2)
f["material_cost_estimate"] = (1.05 * f["qty_ordered"] * f["material_unit_cost"]).round(2)   # the quote assumes 5% extra board
f["days_vs_promise"] = (f["delivered_date"] - f["committed_date"]).dt.days
f["order_size"] = pd.cut(f["quantity"], [0, 1000, 3000, 10000, np.inf], right=False,
                         labels=["1) Under 1,000", "2) 1,000-2,999", "3) 3,000-9,999", "4) 10,000+"]).astype(str)

cols = ["order_id", "client_id", "client_name", "sector", "client_size", "approval_date", "delivered_date", "finish",
        "quantity", "order_size", "quoted_price", "cost_estimate", "final_price", "discount_pct", "material_cost",
        "material_cost_estimate", "consumables_cost", "machine_cost", "labor_cost", "logistics_cost", "tooling_cost",
        "late_penalty", "total_cost", "margin", "margin_pct", "scrap_units", "scrap_cost", "days_vs_promise"]
f[cols].to_csv(CLEAN / "fact_orders.csv", index=False)
print(f"fact_orders: {len(f)} rows, revenue {f['final_price'].sum():,.0f}, margin {f['margin'].sum():,.0f} "
      f"({f['margin'].sum() / f['final_price'].sum():.1%})")
