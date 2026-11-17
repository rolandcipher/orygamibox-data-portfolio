"""
Case 1 - Scrap (waste) in the plant.

Question: where do we lose the most board, and how much money is it?
Run from the project root:  python case1_scrap/analysis.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipelines"))
from common import PALETTE, load, save, style  # noqa: E402

HERE = Path(__file__).resolve().parent
style()

stages = load("production_stages", ["start_ts", "end_ts"])
orders = load("orders", ["approval_date"])
quotes = load("quotes")
costs = load("order_costs")
clients = load("clients")

# ---------------------------------------------------------------------------
# 1. Order-level table: one row per order
# ---------------------------------------------------------------------------
work = stages[stages["stage"] != "Dispatch"]
scrap = work.groupby("order_id")["scrap_units"].sum().rename("scrap_units")
first = stages[stages["stage"] == "Printing"].set_index("order_id")
od = (orders.set_index("order_id")
      .join(scrap)
      .join(first[["qty_in", "machine_id", "shift"]].rename(columns={"qty_in": "input_units", "machine_id": "print_machine", "shift": "print_shift"}))
      .join(costs.set_index("order_id")[["material_unit_cost"]])
      .reset_index()
      .merge(quotes[["quote_id", "finish", "board_type", "print_type"]], on="quote_id", how="left")
      .merge(clients[["client_id", "sector"]], on="client_id", how="left"))
od["scrap_pct"] = od["scrap_units"] / od["input_units"]
od["scrap_cost"] = od["scrap_units"] * od["material_unit_cost"]
bins = [0, 1000, 3000, 10000, np.inf]
labels = ["Under 1,000", "1,000-2,999", "3,000-9,999", "10,000+"]
od["run_size"] = pd.cut(od["qty_ordered"], bins=bins, labels=labels, right=False)

res = {}
res["orders"] = int(len(od))
res["scrap_units"] = int(od["scrap_units"].sum())
res["input_units"] = int(od["input_units"].sum())
res["scrap_rate_weighted"] = float(od["scrap_units"].sum() / od["input_units"].sum())
res["scrap_cost_total"] = float(od["scrap_cost"].sum())
res["scrap_cost_share_of_revenue"] = float(od["scrap_cost"].sum() / od["final_price"].sum())
res["mean_order_scrap_pct"] = float(od["scrap_pct"].mean())
res["median_order_scrap_pct"] = float(od["scrap_pct"].median())
res["p90_order_scrap_pct"] = float(od["scrap_pct"].quantile(.9))

# outliers (IQR rule) and concentration
q1, q3 = od["scrap_pct"].quantile([.25, .75])
iqr = q3 - q1
res["outlier_threshold"] = float(q3 + 1.5 * iqr)
res["outlier_orders"] = int((od["scrap_pct"] > q3 + 1.5 * iqr).sum())
top = od.sort_values("scrap_cost", ascending=False)
k = int(round(len(top) * .10))
res["top10pct_orders_share_of_scrap_cost"] = float(top["scrap_cost"].head(k).sum() / top["scrap_cost"].sum())

# ---------------------------------------------------------------------------
# 2. Where does scrap concentrate?
# ---------------------------------------------------------------------------
def group_table(col):
    g = od.groupby(col, observed=True).agg(orders=("order_id", "size"), input_units=("input_units", "sum"),
                                         scrap_units=("scrap_units", "sum"), scrap_cost=("scrap_cost", "sum"),
                                         mean_pct=("scrap_pct", "mean"), median_pct=("scrap_pct", "median"))
    g["weighted_rate"] = g["scrap_units"] / g["input_units"]
    return g


by_size, by_finish, by_board = group_table("run_size"), group_table("finish"), group_table("board_type")
res["by_run_size"] = by_size.round(4).reset_index().astype({"run_size": str}).to_dict("records")
res["by_finish"] = by_finish.round(4).reset_index().to_dict("records")
res["by_board"] = by_board.round(4).reset_index().to_dict("records")

st = work.copy()
by_stage = st.groupby("stage").agg(input_units=("qty_in", "sum"), scrap_units=("scrap_units", "sum"))
by_stage["rate"] = by_stage["scrap_units"] / by_stage["input_units"]
res["by_stage"] = by_stage.round(4).reset_index().to_dict("records")

pr = stages[(stages["stage"] == "Printing") & (stages["machine_id"].isin(["M01", "M02"]))]
ms = pr.groupby(["machine_id", "shift"]).agg(runs=("order_id", "size"), input_units=("qty_in", "sum"), scrap_units=("scrap_units", "sum"))
ms["rate"] = ms["scrap_units"] / ms["input_units"]
res["offset_machine_shift"] = ms.round(4).reset_index().to_dict("records")

# controlling for run size: finish effect inside each run-size band
ctrl = (od.assign(special=np.where(od["finish"].isin(["Foil", "Emboss"]), "Foil/Emboss", "Other"))
        .groupby(["run_size", "special"], observed=True)["scrap_pct"].median().unstack().round(4))
res["finish_within_size_median"] = ctrl.reset_index().astype({"run_size": str}).to_dict("records")

# fixed + variable: scrap_units = a + b * quantity
b, a = np.polyfit(od["qty_ordered"], od["scrap_units"], 1)
res["fit_fixed_units_per_order"] = float(a)
res["fit_variable_rate_per_unit"] = float(b)
res["fit_r"] = float(np.corrcoef(od["qty_ordered"], od["scrap_units"])[0, 1])

# money: M02 night vs M02 other shifts
m2 = pr[pr["machine_id"] == "M02"].copy()
m2["night"] = m2["shift"] == "Night"
rate_night = m2[m2["night"]]["scrap_units"].sum() / m2[m2["night"]]["qty_in"].sum()
rate_other = m2[~m2["night"]]["scrap_units"].sum() / m2[~m2["night"]]["qty_in"].sum()
night_input = m2[m2["night"]]["qty_in"].sum()
avg_cost = od["material_unit_cost"].mean()
res["m2_night_rate"], res["m2_other_rate"] = float(rate_night), float(rate_other)
res["m2_night_excess_units"] = float((rate_night - rate_other) * night_input)
res["m2_night_excess_cost"] = float((rate_night - rate_other) * night_input * avg_cost)

# money: quoted scrap allowance (5% of the order quantity) vs actual scrap
od["allowance_cost"] = 0.05 * od["qty_ordered"] * od["material_unit_cost"]
od["gap_cost"] = (od["scrap_cost"] - od["allowance_cost"]).clip(lower=0)
res["gap_cost_total"] = float(od["gap_cost"].sum())
res["gap_cost_short_runs_share"] = float(od.loc[od["qty_ordered"] < 3000, "gap_cost"].sum() / od["gap_cost"].sum())
res["short_runs_order_share"] = float((od["qty_ordered"] < 3000).mean())
res["short_runs_scrapcost_share"] = float(od.loc[od["qty_ordered"] < 3000, "scrap_cost"].sum() / od["scrap_cost"].sum())

# reasons
rs = work[work["scrap_units"] > 0].groupby("scrap_reason")["scrap_units"].sum().sort_values(ascending=False)
res["reasons_share"] = (rs / rs.sum()).round(4).to_dict()

json.dump(res, open(HERE / "results.json", "w"), indent=2, default=str)

# ---------------------------------------------------------------------------
# 3. Charts
# ---------------------------------------------------------------------------
C = PALETTE
fig, ax = plt.subplots(figsize=(7, 4))
ax.hist(od["scrap_pct"] * 100, bins=30, color=C["main"], edgecolor="white")
ax.axvline(od["scrap_pct"].mean() * 100, color=C["accent"], lw=2, label=f"Mean {od['scrap_pct'].mean():.1%}")
ax.axvline(od["scrap_pct"].median() * 100, color=C["good"], lw=2, ls="--", label=f"Median {od['scrap_pct'].median():.1%}")
ax.set(title="Scrap % per order: a long right tail", xlabel="Scrap as % of units released to the floor", ylabel="Orders")
ax.legend()
save(fig, HERE / "charts/01_distribution.png")

fig, ax = plt.subplots(figsize=(7, 4))
x = np.arange(len(by_size))
ax.bar(x - .2, by_size["mean_pct"] * 100, .4, label="Mean", color=C["main"])
ax.bar(x + .2, by_size["median_pct"] * 100, .4, label="Median", color=C["grey"])
for i, (m, n) in enumerate(zip(by_size["mean_pct"], by_size["orders"])):
    ax.text(i - .2, m * 100 + .2, f"{m:.1%}", ha="center", fontsize=8)
    ax.text(i, -1.6, f"n={n}", ha="center", fontsize=8, color="#555")
ax.set_xticks(x)
ax.set_xticklabels(by_size.index)
ax.set(title="Scrap % by order size: short runs lose the most", ylabel="Scrap %")
ax.legend()
ax.set_ylim(-2.2, None)
save(fig, HERE / "charts/02_by_run_size.png")

fig, ax = plt.subplots(figsize=(7, 4))
bf = by_finish.sort_values("median_pct")
ax.barh(bf.index, bf["median_pct"] * 100, color=C["main"])
for i, v in enumerate(bf["median_pct"]):
    ax.text(v * 100 + .1, i, f"{v:.1%}", va="center", fontsize=9)
ax.set(title="Median scrap % by finish", xlabel="Scrap %")
save(fig, HERE / "charts/03_by_finish.png")

fig, ax = plt.subplots(figsize=(7, 4))
piv = ms["rate"].unstack() * 100
piv = piv[["Morning", "Afternoon", "Night"]]
piv.T.plot(kind="bar", ax=ax, color=[C["grey"], C["accent"]], width=.7)
ax.set(title="Offset presses: scrap rate by shift", ylabel="Scrap % of units printed", xlabel="")
ax.set_xticklabels(["Morning", "Afternoon", "Night"], rotation=0)
ax.legend(title="Machine", labels=["M01 (Press A)", "M02 (Press B)"])
save(fig, HERE / "charts/04_press_by_shift.png")

fig, ax = plt.subplots(figsize=(7, 4))
srt = by_stage.sort_values("rate")
ax.barh(srt.index, srt["rate"] * 100, color=C["main"])
for i, v in enumerate(srt["rate"]):
    ax.text(v * 100 + .05, i, f"{v:.1%}", va="center", fontsize=9)
ax.set(title="Scrap rate by production stage", xlabel="Scrap % of units entering the stage")
save(fig, HERE / "charts/05_by_stage.png")

# data for the spreadsheet
od_out = od[["order_id", "sector", "qty_ordered", "finish", "board_type", "print_machine", "print_shift",
             "input_units", "scrap_units", "material_unit_cost", "final_price"]].sort_values("order_id")
od_out.to_csv(HERE / "dashboard/order_level_scrap.csv", index=False)
pr_out = stages[(stages["stage"] == "Printing")][["order_id", "machine_id", "shift", "qty_in", "scrap_units"]]
pr_out.to_csv(HERE / "dashboard/printing_stage_scrap.csv", index=False)
print(json.dumps({k: v for k, v in res.items() if not isinstance(v, (list, dict))}, indent=1))
