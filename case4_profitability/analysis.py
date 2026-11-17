"""
Case 4 - Profitability by client.

Question: which clients really leave us margin and which cost us more than they seem?
The SQL in sql/ builds the final model in BigQuery on top of fact_orders (consolidate.py).
This script reproduces the numbers with pandas, draws the charts and exports the dashboard tables.
Run from the project root:  python case4_profitability/consolidate.py && python case4_profitability/analysis.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipelines"))
from common import PALETTE as C, load, preview, save, style  # noqa: E402

HERE = Path(__file__).resolve().parent
LS = HERE / "looker_studio"
style()

f = load("fact_orders", ["approval_date", "delivered_date"])
res = {}
rev, mar = f["final_price"].sum(), f["margin"].sum()
res.update(orders=int(len(f)), revenue=float(rev), margin=float(mar), margin_pct=float(mar / rev),
           clients=int(f["client_id"].nunique()))

# --- client size, sector, order size, finish ------------------------------------------------
def seg(col, data=f):
    g = data.groupby(col).agg(orders=("order_id", "size"), revenue=("final_price", "sum"), margin=("margin", "sum"))
    g["margin_pct"] = g["margin"] / g["revenue"]
    g["share_of_revenue"] = g["revenue"] / g["revenue"].sum()
    g["share_of_margin"] = g["margin"] / g["margin"].sum()
    return g


by_size = seg("client_size").reindex(["Large", "Medium", "Small"])
by_sector = seg("sector")
by_order = seg("order_size")
f["finish_group"] = np.where(f["finish"] == "No finish", "No finish", "With finish")
by_finish = seg("finish_group")
res["by_client_size"] = by_size.round(4).reset_index().to_dict("records")
res["by_sector"] = by_sector.round(4).reset_index().to_dict("records")
res["by_order_size"] = by_order.round(4).reset_index().to_dict("records")
res["by_finish"] = by_finish.round(4).reset_index().to_dict("records")

# --- clients ----------------------------------------------------------------------------------
cl = f.groupby(["client_id", "client_name", "client_size", "sector"]).agg(
    orders=("order_id", "size"), revenue=("final_price", "sum"), margin=("margin", "sum"), penalties=("late_penalty", "sum")).reset_index()
cl["margin_pct"] = cl["margin"] / cl["revenue"]
cl = cl.sort_values("revenue", ascending=False).reset_index(drop=True)
cl["cum_revenue_share"] = cl["revenue"].cumsum() / cl["revenue"].sum()
top5 = cl.head(5)
res["top5_share_of_revenue"] = float(top5["revenue"].sum() / rev)
res["top5_share_of_margin"] = float(top5["margin"].sum() / mar)
res["top5_margin_pct_range"] = [float(top5["margin_pct"].min()), float(top5["margin_pct"].max())]
res["top5_all_large"] = bool((top5["client_size"] == "Large").all())
res["clients_for_80pct_revenue"] = int((cl["cum_revenue_share"].shift(fill_value=0) < 0.8).sum())
cm = cl.sort_values("margin", ascending=False)
res["clients_for_80pct_margin"] = int(((cm["margin"].cumsum() / cm["margin"].sum()).shift(fill_value=0) < 0.8).sum())
res["corr_revenue_vs_margin_pct_clients"] = float(cl[["revenue", "margin_pct"]].corr().iloc[0, 1])
res["spearman_revenue_vs_margin_pct_clients"] = float(cl[["revenue", "margin_pct"]].corr(method="spearman").iloc[0, 1])
res["spearman_quantity_vs_margin_pct_orders"] = float(f[["quantity", "margin_pct"]].corr(method="spearman").iloc[0, 1])
res["clients_below_10pct_margin"] = int((cl["margin_pct"] < .10).sum())
res["revenue_share_clients_below_10pct"] = float(cl.loc[cl["margin_pct"] < .10, "revenue"].sum() / rev)
res["orders_margin_below_5pct"] = float((f["margin_pct"] < .05).mean())
res["orders_negative_margin"] = float((f["margin"] < 0).mean())
res["discounted_orders_share"] = float((f["discount_pct"] > 0.0005).mean())
res["avg_discount_by_size"] = f.groupby("client_size")["discount_pct"].mean().round(4).to_dict()
res["avg_markup_by_size"] = (f.dropna(subset=["cost_estimate"]).assign(m=lambda x: x["quoted_price"] / x["cost_estimate"]).groupby("client_size")["m"].mean().round(3).to_dict())

# --- margin bridge ------------------------------------------------------------------------------
b = f.dropna(subset=["cost_estimate"])
bridge = {
    "margin_at_quote": float((b["quoted_price"] - b["cost_estimate"]).sum()),
    "discounts": float(-(b["quoted_price"] - b["final_price"]).sum()),
    "cost_above_estimate": float(-(b["total_cost"] - b["late_penalty"] - b["cost_estimate"]).sum()),
    "late_penalties": float(-b["late_penalty"].sum()),
    "actual_margin": float(b["margin"].sum()),
}
bridge["material_part_of_overrun"] = float(-(b["material_cost"] - b["material_cost_estimate"]).sum())
bridge["time_and_other_part_of_overrun"] = bridge["cost_above_estimate"] - bridge["material_part_of_overrun"]
bridge["orders_in_bridge"] = int(len(b))
bridge["revenue_in_bridge"] = float(b["final_price"].sum())
res["bridge"] = bridge

# --- late penalties --------------------------------------------------------------------------
res["late_penalties_total"] = float(f["late_penalty"].sum())
res["orders_with_penalty"] = int((f["late_penalty"] > 0).sum())
res["penalty_share_of_cost"] = float(f["late_penalty"].sum() / f["total_cost"].sum())

# --- cost structure ---------------------------------------------------------------------------
comp = ["material_cost", "consumables_cost", "machine_cost", "labor_cost"]
cs = f.groupby("client_size")[comp + ["logistics_cost", "tooling_cost", "total_cost"]].sum()
cs["logistics_and_tooling"] = cs["logistics_cost"] + cs["tooling_cost"]
cs_share = cs[comp + ["logistics_and_tooling"]].div(cs["total_cost"], axis=0).reindex(["Large", "Medium", "Small"])
res["cost_share_by_size"] = cs_share.round(3).reset_index().to_dict("records")
res["cost_share_total"] = (f[comp + ["logistics_cost", "tooling_cost", "late_penalty"]].sum() / f["total_cost"].sum()).round(3).to_dict()

# --- scenario: raise prices for Large clients ------------------------------------------------
L = f[f["client_size"] == "Large"]
R, M = L["final_price"].sum(), L["margin"].sum()
Ccost = R - M
rows = []
for pr in (0.02, 0.03, 0.05):
    for vol in (0.0, 0.05, 0.10, 0.20):
        new_m = (1 - vol) * ((1 + pr) * R - Ccost)
        rows.append({"price_increase": pr, "volume_lost": vol, "margin_change": float(new_m - M)})
res["scenario_large_clients"] = rows
res["scenario_breakeven_volume_loss_at_3pct"] = float(1 - M / (1.03 * R - Ccost))
res["large_revenue"], res["large_margin"] = float(R), float(M)
json.dump(res, open(HERE / "results.json", "w"), indent=2, default=str)

# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(7, 4))
x = np.arange(3)
ax.bar(x - .2, by_size["share_of_revenue"] * 100, .4, label="Share of revenue", color=C["grey"])
ax.bar(x + .2, by_size["share_of_margin"] * 100, .4, label="Share of margin", color=C["main"])
for i, (r_, m_, p_) in enumerate(zip(by_size["share_of_revenue"], by_size["share_of_margin"], by_size["margin_pct"])):
    ax.text(i - .2, r_ * 100 + 1, f"{r_:.0%}", ha="center", fontsize=9)
    ax.text(i + .2, m_ * 100 + 1, f"{m_:.0%}", ha="center", fontsize=9)
    ax.text(i, -7, f"margin {p_:.1%}", ha="center", fontsize=9, color="#333")
ax.set_xticks(x)
ax.set_xticklabels([f"{i} clients" for i in by_size.index])
ax.set(title="Large clients: 55% of revenue, 36% of margin", ylabel="%", ylim=(-10, 65))
ax.legend(frameon=False)
save(fig, HERE / "charts/01_revenue_vs_margin_share.png")

fig, ax = plt.subplots(figsize=(7.5, 4.6))
col = {"Large": C["accent"], "Medium": C["main"], "Small": C["grey"]}
for s_, g in cl.groupby("client_size"):
    ax.scatter(g["revenue"] / 1000, g["margin_pct"] * 100, s=60, color=col[s_], label=s_, alpha=.85)
for _, r_ in top5.iterrows():
    ax.annotate(r_["client_name"], (r_["revenue"] / 1000, r_["margin_pct"] * 100), textcoords="offset points", xytext=(5, 5), fontsize=8)
ax.set(title="The biggest clients have the lowest margin %", xlabel="Revenue in 24 months ($ thousand)", ylabel="Margin %")
ax.legend(title="Client size", frameon=False)
save(fig, HERE / "charts/02_client_revenue_vs_margin_pct.png")

fig, ax = plt.subplots(figsize=(7, 4))
n = np.arange(1, len(cl) + 1)
ax.plot(n, cl["cum_revenue_share"] * 100, color=C["grey"], lw=2.4, label="Cumulative revenue")
ax.plot(n, cm["margin"].cumsum().to_numpy() / cm["margin"].sum() * 100, color=C["main"], lw=2.4, label="Cumulative margin (clients ranked by margin)")
ax.axhline(80, color=C["accent"], ls="--", lw=1)
ax.set(title=f"{res['clients_for_80pct_revenue']} of 60 clients make 80% of revenue", xlabel="Number of clients", ylabel="% of total")
ax.legend(frameon=False)
save(fig, HERE / "charts/03_pareto.png")

fig, ax = plt.subplots(figsize=(8, 4.2))
steps = [("Margin at\nquote", bridge["margin_at_quote"]), ("Discounts", bridge["discounts"]),
         ("Costs above\nestimate", bridge["cost_above_estimate"]), ("Late\npenalties", bridge["late_penalties"]),
         ("Actual\nmargin", bridge["actual_margin"])]
cum = 0
for i, (lab, v) in enumerate(steps):
    if i in (0, 4):
        ax.bar(i, v / 1000, color=C["main"])
        ax.text(i, v / 1000 + 12, f"${v/1000:,.0f}k", ha="center", fontweight="bold")
        cum = v if i == 0 else cum
    else:
        ax.bar(i, v / 1000, bottom=cum / 1000, color=C["bad"])
        ax.text(i, (cum + v) / 1000 - 40, f"-${abs(v)/1000:,.0f}k", ha="center", color="#333", fontweight="bold")
        cum += v
ax.set_xticks(range(5))
ax.set_xticklabels([s[0] for s in steps])
ax.set(title="Where the margin goes (24 months)", ylabel="$ thousand", ylim=(0, 820))
save(fig, HERE / "charts/04_margin_bridge.png")

fig, axes = plt.subplots(1, 2, figsize=(10, 3.8))
for ax, g, ttl in ((axes[0], by_sector.sort_values("margin_pct"), "By sector"), (axes[1], by_order.sort_index(), "By order size")):
    ax.barh(g.index.astype(str), g["margin_pct"] * 100, color=C["main"])
    for i, v in enumerate(g["margin_pct"]):
        ax.text(v * 100 + .3, i, f"{v:.1%}", va="center", fontsize=9)
    ax.axvline(res["margin_pct"] * 100, color=C["accent"], ls="--")
    ax.set(title=f"Margin % {ttl.lower()}", xlim=(0, 26))
save(fig, HERE / "charts/05_margin_by_segment.png")

fig, ax = plt.subplots(figsize=(7.5, 4))
bottom = np.zeros(3)
labs = {"material_cost": "Material", "consumables_cost": "Consumables", "machine_cost": "Machine time", "labor_cost": "Labour", "logistics_and_tooling": "Logistics + tooling"}
cols_ = [C["main"], "#6C8EBF", C["accent"], "#E9B07C", C["grey"]]
for c_, colr in zip(labs, cols_):
    v = cs_share[c_].to_numpy() * 100
    ax.bar(cs_share.index, v, bottom=bottom, color=colr, label=labs[c_], width=.55)
    bottom += v
ax.set(title="Cost structure by client size (% of total cost)", ylabel="%")
ax.legend(frameon=False, fontsize=8, bbox_to_anchor=(1.01, 1), loc="upper left")
save(fig, HERE / "charts/06_cost_structure.png")

sc = pd.DataFrame(rows).pivot(index="price_increase", columns="volume_lost", values="margin_change") / 1000
fig, ax = plt.subplots(figsize=(6.5, 3.4))
im = ax.imshow(sc.values, cmap="Blues", aspect="auto")
ax.set_xticks(range(4))
ax.set_xticklabels([f"{v:.0%}" for v in sc.columns])
ax.set_yticks(range(3))
ax.set_yticklabels([f"+{p:.0%}" for p in sc.index])
for i in range(3):
    for j in range(4):
        ax.text(j, i, f"+${sc.values[i, j]:,.0f}k", ha="center", va="center", color="white" if sc.values[i, j] > sc.values.max() * .55 else "black", fontsize=9)
ax.set(title="Large clients: margin change over 24 months", xlabel="Volume lost", ylabel="Price increase")
ax.grid(False)
save(fig, HERE / "charts/07_price_scenario.png")

# ---------------------------------------------------------------------------
# Exports + preview
# ---------------------------------------------------------------------------
LS.mkdir(exist_ok=True)
cl.round(4).to_csv(LS / "client_profitability.csv", index=False)
pd.concat([by_size.assign(dimension="Client size"), by_sector.assign(dimension="Sector"), by_order.assign(dimension="Order size"), by_finish.assign(dimension="Finish")]).reset_index(names="segment").round(4).to_csv(LS / "margin_by_segment.csv", index=False)
pd.DataFrame([{"step": s[0].replace("\n", " "), "amount": round(s[1])} for s in steps]).to_csv(LS / "margin_bridge.csv", index=False)
f.drop(columns=["finish_group"]).to_csv(LS / "fact_orders.csv", index=False)


def q1(ax):
    xx = np.arange(3)
    ax.bar(xx - .2, by_size["share_of_revenue"] * 100, .4, label="Revenue", color=C["grey"])
    ax.bar(xx + .2, by_size["share_of_margin"] * 100, .4, label="Margin", color=C["main"])
    ax.set_xticks(xx)
    ax.set_xticklabels(by_size.index)
    ax.set(title="Share of revenue vs share of margin", ylabel="%")
    ax.legend(frameon=False, fontsize=8)


def q2(ax):
    for s_, g in cl.groupby("client_size"):
        ax.scatter(g["revenue"] / 1000, g["margin_pct"] * 100, s=35, color=col[s_], label=s_, alpha=.85)
    ax.set(title="Client revenue vs margin %", xlabel="Revenue ($ thousand)", ylabel="%")
    ax.legend(frameon=False, fontsize=8)


def q3(ax):
    for i, (lab, v) in enumerate(steps):
        if i in (0, 4):
            ax.bar(i, v / 1000, color=C["main"])
        else:
            ax.bar(i, v / 1000, bottom=sum(s_[1] for s_ in steps[:i]) / 1000, color=C["bad"])
    ax.set_xticks(range(5))
    ax.set_xticklabels([s_[0] for s_ in steps], fontsize=7)
    ax.set(title="Margin bridge ($ thousand)", ylim=(0, 820))


def q4(ax):
    ax.plot(n, cl["cum_revenue_share"] * 100, color=C["grey"], lw=2.4)
    ax.axhline(80, color=C["accent"], ls="--", lw=1)
    ax.set(title="Pareto: cumulative revenue by client", xlabel="Clients", ylabel="%")


preview(LS / "dashboard_preview.png", "OrygamiBox S.A. - Profitability by client (preview)",
        "Static preview of the Looker Studio dashboard. Synthetic data, Jan 2024 - Dec 2025.",
        [("Revenue", f"${rev/1e6:.2f}M"), ("Margin", f"${mar/1e3:,.0f}k"), ("Margin %", f"{mar/rev:.1%}"),
         ("Large clients: share of revenue", f"{by_size.loc['Large','share_of_revenue']:.0%}"),
         ("Large clients: share of margin", f"{by_size.loc['Large','share_of_margin']:.0%}")],
        [q1, q2, q3, q4])
print(json.dumps({k: v for k, v in res.items() if not isinstance(v, (list, dict))}, indent=1))
print(json.dumps(res["bridge"], indent=1))
print(res["avg_discount_by_size"], res["avg_markup_by_size"], res["scenario_breakeven_volume_loss_at_3pct"])
print(sc.round(1))
