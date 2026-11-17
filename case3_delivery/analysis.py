"""
Case 3 - Bottlenecks and delivery performance.

Question: at which stage do orders get delayed and what causes it?
The SQL in sql/ is the main deliverable (BigQuery). This script reproduces the numbers with pandas,
draws the charts and exports the tables for the Looker Studio dashboard.
Run from the project root:  python case3_delivery/analysis.py
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

orders = load("orders", ["approval_date", "committed_date", "delivered_date"])
stages = load("production_stages", ["start_ts", "end_ts"])
downtime = load("machine_downtime", ["start_ts", "end_ts"])
purchases = load("purchases", ["order_date", "promised_date", "received_date"])
suppliers = load("suppliers")
quotes = load("quotes")
clients = load("clients")

# ---------------------------------------------------------------------------
# Order table (same logic as sql/01_order_delivery.sql)
# ---------------------------------------------------------------------------
od = (orders.dropna(subset=["delivered_date"])
      .merge(quotes[["quote_id", "finish", "quantity"]], on="quote_id")
      .merge(clients[["client_id", "sector", "client_size"]], on="client_id"))
od["order_size"] = pd.cut(od["quantity"], [0, 1000, 3000, 10000, np.inf], right=False,
                          labels=["Under 1,000", "1,000-2,999", "3,000-9,999", "10,000+"])
od["promised_days"] = (od["committed_date"] - od["approval_date"]).dt.days
od["lead_time_days"] = (od["delivered_date"] - od["approval_date"]).dt.days
od["days_vs_promise"] = (od["delivered_date"] - od["committed_date"]).dt.days
od["on_time"] = (od["delivered_date"] <= od["committed_date"]).astype(int)

res = {}
res["orders"] = int(len(od))
res["on_time_rate"] = float(od["on_time"].mean())
late = od[od["on_time"] == 0]
res["late_orders"] = int(len(late))
res["avg_days_late_when_late"] = float(late["days_vs_promise"].mean())
res["lead_time_p50"], res["lead_time_p90"] = [float(od["lead_time_days"].quantile(x)) for x in (.5, .9)]

# seasonality
od["quarter"] = od["delivered_date"].dt.to_period("Q").astype(str)
od["month_num"] = od["delivered_date"].dt.month
res["on_time_q4"] = float(od[od["month_num"].isin([10, 11, 12])]["on_time"].mean())
res["on_time_rest"] = float(od[~od["month_num"].isin([10, 11, 12])]["on_time"].mean())
res["on_time_by_quarter"] = od.groupby("quarter")["on_time"].mean().round(3).to_dict()
res["on_time_by_size"] = od.groupby("order_size", observed=True)["on_time"].agg(["size", "mean"]).round(3).reset_index().astype({"order_size": str}).to_dict("records")
res["on_time_by_sector"] = od.groupby("sector")["on_time"].mean().round(3).to_dict()
res["on_time_by_client_size"] = od.groupby("client_size")["on_time"].mean().round(3).to_dict()
res["on_time_by_finish"] = od.assign(f=np.where(od["finish"] == "No finish", "No finish", "With finish")).groupby("f")["on_time"].mean().round(3).to_dict()

# promise vs reality
pv = od.groupby("order_size", observed=True).agg(orders=("order_id", "size"), avg_promised_days=("promised_days", "mean"),
                                                 actual_p50=("lead_time_days", lambda x: x.quantile(.5)),
                                                 actual_p75=("lead_time_days", lambda x: x.quantile(.75)),
                                                 actual_p90=("lead_time_days", lambda x: x.quantile(.9)),
                                                 on_time_rate=("on_time", "mean")).round(2).reset_index()
res["promise_vs_reality"] = pv.astype({"order_size": str}).to_dict("records")

# ---------------------------------------------------------------------------
# Stage times (same logic as sql/02_stage_times.sql)
# ---------------------------------------------------------------------------
st = stages.merge(orders[["order_id", "approval_date"]], on="order_id").sort_values(["order_id", "start_ts"])
st["previous_end"] = st.groupby("order_id")["end_ts"].shift(1)
st["ready_ts"] = st["previous_end"].fillna(st["approval_date"])
st["wait_hours"] = (st["start_ts"] - st["ready_ts"]).dt.total_seconds() / 3600
st["process_hours"] = (st["end_ts"] - st["start_ts"]).dt.total_seconds() / 3600
st = st[st["order_id"].isin(od["order_id"])]

stage_order = ["Printing", "Finishing", "Die-cutting", "Gluing", "Quality control", "Dispatch"]
sp = st.groupby("stage").agg(runs=("order_id", "size"), wait_p50=("wait_hours", lambda x: x.quantile(.5)),
                             wait_p90=("wait_hours", lambda x: x.quantile(.9)),
                             process_p50=("process_hours", lambda x: x.quantile(.5)),
                             process_p90=("process_hours", lambda x: x.quantile(.9)),
                             wait_total=("wait_hours", "sum")).reindex(stage_order)
sp["share_of_waiting"] = sp["wait_total"] / sp["wait_total"].sum()
res["stage_table"] = sp.round(3).reset_index().to_dict("records")

# machine busy time
span_hours = (stages["end_ts"].max() - stages["start_ts"].min()).total_seconds() / 3600
mu = stages.dropna(subset=["machine_id"]).assign(h=lambda x: (x["end_ts"] - x["start_ts"]).dt.total_seconds() / 3600).groupby("machine_id")["h"].sum() / span_hours
res["machine_busy_share"] = mu.round(3).to_dict()
dh = downtime.groupby("machine_id")["duration_hours"].sum().round(0).to_dict()
res["downtime_hours_by_machine"] = dh
res["downtime_cause_hours"] = downtime.groupby("cause")["duration_hours"].sum().round(0).to_dict()

# ---------------------------------------------------------------------------
# Delay drivers (same logic as sql/04_delay_drivers.sql)
# ---------------------------------------------------------------------------
dtb = {m: g for m, g in downtime.groupby("machine_id")}


def overlap_hours(row):
    if pd.isna(row["machine_id"]):
        return 0.0
    g = dtb[row["machine_id"]]
    lo = g["start_ts"].clip(lower=row["ready_ts"])
    hi = g["end_ts"].clip(upper=row["end_ts"])
    return float((hi - lo).dt.total_seconds().clip(lower=0).sum() / 3600)


st["downtime_hours"] = st.apply(overlap_hours, axis=1)
parts = st.groupby("order_id").apply(lambda g: pd.Series({
    "pre_production_days": g.loc[g["stage"] == "Printing", "wait_hours"].sum() / 24,
    "between_stage_days": g.loc[g["stage"] != "Printing", "wait_hours"].sum() / 24,
    "process_days": g["process_hours"].sum() / 24,
    "downtime_days": g["downtime_hours"].sum() / 24}), include_groups=False)
od = od.merge(parts, left_on="order_id", right_index=True)
drv = od.groupby("on_time")[["pre_production_days", "between_stage_days", "process_days", "downtime_days"]].mean().round(2)
drv.index = ["Late", "On time"]
res["delay_drivers"] = drv.reset_index().rename(columns={"index": "delivery"}).to_dict("records")

# die-cutting queue and the share of all waiting
dc = st[st["stage"] == "Die-cutting"].set_index("order_id")["wait_hours"].rename("diecut_wait_hours")
od = od.merge(dc, left_on="order_id", right_index=True)

# scenario: halve the die-cutting queue
saved = 0.5 * od["diecut_wait_hours"] / 24
new_vs_promise = od["days_vs_promise"] - saved
res["scenario_halve_diecut_queue"] = {
    "on_time_now": float(od["on_time"].mean()),
    "on_time_after": float((new_vs_promise <= 0).mean()),
    "late_orders_recovered": int(((od["on_time"] == 0) & (new_vs_promise <= 0)).sum()),
}
# scenario: remove the 4-day average pre-production wait caused by purchases (orders that triggered a purchase)
res["purchase_orders"] = {
    "share_of_orders": float(od["purchase_id"].notna().mean()),
    "pre_production_days_with_purchase": float(od.loc[od["purchase_id"].notna(), "pre_production_days"].mean()),
    "pre_production_days_without": float(od.loc[od["purchase_id"].isna(), "pre_production_days"].mean()),
    "on_time_with_purchase": float(od.loc[od["purchase_id"].notna(), "on_time"].mean()),
    "on_time_without": float(od.loc[od["purchase_id"].isna(), "on_time"].mean()),
}

# suppliers
purchases["days_late"] = (purchases["received_date"] - purchases["promised_date"]).dt.days
sup = (purchases.merge(suppliers, on="supplier_id")
       .merge(od[["purchase_id", "on_time"]], on="purchase_id", how="left")
       .groupby(["supplier_id", "supplier_name", "main_material"])
       .agg(purchases=("purchase_id", "nunique"), avg_days_late=("days_late", "mean"),
            orders_waiting=("on_time", "count"), on_time_rate=("on_time", "mean")).round(3).reset_index()
       .sort_values("avg_days_late", ascending=False))
res["suppliers"] = sup.to_dict("records")

# monthly
mo = od.assign(month=od["delivered_date"].dt.to_period("M").dt.to_timestamp()).groupby("month").agg(orders=("on_time", "size"), on_time_orders=("on_time", "sum")).reset_index()
mo["on_time_rate"] = mo["on_time_orders"] / mo["orders"]
mo["on_time_rate_3m"] = mo["on_time_orders"].rolling(3, min_periods=1).sum() / mo["orders"].rolling(3, min_periods=1).sum()
res["diecut_wait_corr_with_late"] = float(np.corrcoef(od["diecut_wait_hours"], od["days_vs_promise"])[0, 1])
json.dump(res, open(HERE / "results.json", "w"), indent=2, default=str)

# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(7, 4))
t = od.groupby("order_size", observed=True)["on_time"].agg(["mean", "size"]).reset_index()
ax.bar(t["order_size"].astype(str), t["mean"] * 100, color=C["main"])
for i, r in t.iterrows():
    ax.text(i, r["mean"] * 100 + 1.5, f"{r['mean']:.0%}", ha="center", fontweight="bold")
    ax.text(i, 2, f"n={int(r['size'])}", ha="center", color="white", fontsize=8)
ax.axhline(res["on_time_rate"] * 100, color=C["accent"], ls="--", label=f"All orders {res['on_time_rate']:.0%}")
ax.set(title="On-time delivery by order size", ylabel="Orders delivered on time (%)", ylim=(0, 105))
ax.legend()
save(fig, HERE / "charts/01_on_time_by_order_size.png")

fig, ax = plt.subplots(figsize=(7.5, 4))
x = np.arange(len(pv))
ax.bar(x - .27, pv["avg_promised_days"], .27, label="Promised (average)", color=C["accent"])
ax.bar(x, pv["actual_p50"], .27, label="Actual P50", color=C["main"])
ax.bar(x + .27, pv["actual_p90"], .27, label="Actual P90", color=C["grey"])
ax.set_xticks(x)
ax.set_xticklabels(pv["order_size"].astype(str))
ax.set(title="Promised vs actual lead time (days from approval)", ylabel="Days")
ax.legend(frameon=False)
save(fig, HERE / "charts/02_promise_vs_reality.png")

fig, ax = plt.subplots(figsize=(7.5, 4))
s2 = sp.sort_values("share_of_waiting")
ax.barh(s2.index, s2["share_of_waiting"] * 100, color=[C["accent"] if i in ("Printing", "Die-cutting") else C["main"] for i in s2.index])
for i, (v, p90) in enumerate(zip(s2["share_of_waiting"], s2["wait_p90"])):
    ax.text(v * 100 + .5, i, f"{v:.0%}   (P90 wait {p90:.0f} h)", va="center", fontsize=9)
ax.set(title="Where orders wait: share of all waiting time", xlabel="% of total waiting hours", xlim=(0, 75))
save(fig, HERE / "charts/03_waiting_by_stage.png")

fig, ax = plt.subplots(figsize=(7, 4))
dd = drv.loc[["On time", "Late"], ["pre_production_days", "between_stage_days", "process_days"]]
bottom = np.zeros(2)
for col, color, lab in [("pre_production_days", C["grey"], "Before printing (design, material)"), ("between_stage_days", C["accent"], "Waiting between stages"), ("process_days", C["main"], "Processing")]:
    ax.bar(dd.index, dd[col], bottom=bottom, color=color, label=lab, width=.5)
    for i, v in enumerate(dd[col]):
        ax.text(i, bottom[i] + v / 2, f"{v:.1f}", ha="center", color="white", fontweight="bold")
    bottom += dd[col].values
ax.set(title="Late orders wait longer between stages", ylabel="Average days")
ax.legend(frameon=False, fontsize=8, loc="upper left")
save(fig, HERE / "charts/04_late_vs_on_time.png")

fig, ax = plt.subplots(figsize=(8.5, 3.8))
ax.plot(mo["month"], mo["on_time_rate"] * 100, color=C["grey"], marker=".", label="Monthly")
ax.plot(mo["month"], mo["on_time_rate_3m"] * 100, color=C["main"], lw=2.4, label="3-month average")
for yr in (2024, 2025):
    ax.axvspan(pd.Timestamp(f"{yr}-10-01"), pd.Timestamp(f"{yr}-12-31"), color=C["accent"], alpha=.12)
ax.set(title="On-time delivery by month (Q4 shaded)", ylabel="%", ylim=(0, 100))
ax.legend(frameon=False)
save(fig, HERE / "charts/05_on_time_by_month.png")

fig, ax = plt.subplots(figsize=(7, 3.8))
sp_s = sup[sup["main_material"].isin(["SBS", "Coated", "Kraft", "Microflute"])].sort_values("avg_days_late")
ax.barh(sp_s["supplier_id"] + " " + sp_s["supplier_name"], sp_s["avg_days_late"], color=[C["accent"] if v > 2 else C["main"] for v in sp_s["avg_days_late"]])
ax.set(title="Board suppliers: average days late vs promise", xlabel="Days")
save(fig, HERE / "charts/06_suppliers.png")

fig, ax = plt.subplots(figsize=(7, 4))
ax.hist(od["days_vs_promise"].clip(-15, 25), bins=range(-15, 27), color=C["main"], edgecolor="white")
ax.axvline(0, color=C["accent"], lw=2, label="Promised date")
ax.set(title="Delivery vs promised date (negative = early)", xlabel="Days", ylabel="Orders")
ax.legend()
save(fig, HERE / "charts/07_delay_histogram.png")

fig, ax = plt.subplots(figsize=(9, 3.6))
hm = st.assign(q=st["start_ts"].dt.to_period("Q").astype(str)).pivot_table(index="stage", columns="q", values="wait_hours", aggfunc="mean").reindex(stage_order)
hm = hm.loc[:, [c for c in hm.columns if c >= "2024Q1" and c <= "2025Q4"]]
im = ax.imshow(hm.values, cmap="Blues", aspect="auto")
ax.set_xticks(range(len(hm.columns)))
ax.set_xticklabels(hm.columns)
ax.set_yticks(range(len(hm.index)))
ax.set_yticklabels(hm.index)
for i in range(hm.shape[0]):
    for j in range(hm.shape[1]):
        ax.text(j, i, f"{hm.values[i, j]:.0f}", ha="center", va="center", fontsize=8, color="white" if hm.values[i, j] > hm.values.max() * .55 else "black")
ax.set(title="Average waiting hours by stage and quarter")
ax.grid(False)
save(fig, HERE / "charts/08_waiting_heatmap.png")

# ---------------------------------------------------------------------------
# Exports + preview for Looker Studio
# ---------------------------------------------------------------------------
LS.mkdir(exist_ok=True)
od.drop(columns=["quarter"]).to_csv(LS / "order_delivery.csv", index=False)
sp.round(3).reset_index().to_csv(LS / "stage_percentiles.csv", index=False)
mo.to_csv(LS / "monthly_on_time.csv", index=False, float_format="%.4f")
pv.to_csv(LS / "promise_vs_reality.csv", index=False)
sup.to_csv(LS / "supplier_impact.csv", index=False)
st[["order_id", "stage", "machine_id", "start_ts", "end_ts", "wait_hours", "process_hours", "downtime_hours"]].round(2).to_csv(LS / "stage_times.csv", index=False)


def p1(ax):
    ax.bar(t["order_size"].astype(str), t["mean"] * 100, color=C["main"])
    for i, r in t.iterrows():
        ax.text(i, r["mean"] * 100 + 1.5, f"{r['mean']:.0%}", ha="center", fontweight="bold", fontsize=9)
    ax.set(title="On-time rate by order size", ylabel="%", ylim=(0, 105))


def p2(ax):
    ax.barh(s2.index, s2["share_of_waiting"] * 100, color=[C["accent"] if i in ("Printing", "Die-cutting") else C["main"] for i in s2.index])
    ax.set(title="Share of total waiting time by stage", xlabel="%")


def p3(ax):
    ax.plot(mo["month"], mo["on_time_rate"] * 100, color=C["grey"], marker=".")
    ax.plot(mo["month"], mo["on_time_rate_3m"] * 100, color=C["main"], lw=2.4)
    ax.set(title="On-time rate by month", ylabel="%", ylim=(0, 100))


def p4(ax):
    ax.hist(od["days_vs_promise"].clip(-15, 25), bins=range(-15, 27), color=C["main"], edgecolor="white")
    ax.axvline(0, color=C["accent"], lw=2)
    ax.set(title="Days vs promised date", xlabel="Days (negative = early)", ylabel="Orders")


preview(LS / "dashboard_preview.png", "OrygamiBox S.A. - Delivery performance (preview)",
        "Static preview of the Looker Studio dashboard. Synthetic data, orders approved Jan 2024 - Dec 2025.",
        [("Orders delivered", f"{res['orders']:,}"), ("On-time delivery", f"{res['on_time_rate']:.1%}"),
         ("Avg days late (late orders)", f"{res['avg_days_late_when_late']:.1f}"), ("Lead time P90 (days)", f"{res['lead_time_p90']:.0f}"),
         ("On time in Q4", f"{res['on_time_q4']:.0%}")],
        [p1, p2, p3, p4])
print(json.dumps({k: v for k, v in res.items() if not isinstance(v, (list, dict))}, indent=1))
for k in ["scenario_halve_diecut_queue", "purchase_orders", "machine_busy_share", "downtime_hours_by_machine", "downtime_cause_hours", "delay_drivers", "on_time_by_sector", "on_time_by_client_size", "on_time_by_finish"]:
    print(k, res[k])
