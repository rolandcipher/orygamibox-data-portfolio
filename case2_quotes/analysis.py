"""
Case 2 - Quote funnel.

Question: why do we lose quotes: price, response time or type of client?
The SQL in sql/ is the main deliverable (BigQuery). This script reproduces the same numbers
with pandas, draws the charts and exports the tables that feed the Looker Studio dashboard.
Run from the project root:  python case2_quotes/analysis.py
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

q = load("quotes", ["request_date", "response_date"])
clients = load("clients")
orders = load("orders")
costs = load("order_costs")
q = q.drop(columns=[c for c in ["sector", "client_size"] if c in q.columns]).merge(
    clients[["client_id", "sector", "client_size"]], on="client_id", how="left")

res = {}
decided_all = q[q["status"].isin(["Won", "Lost"])]
res["quotes"] = int(len(q))
res["decided"] = int(len(decided_all))
res["win_rate_all_decided"] = float((decided_all["status"] == "Won").mean())

d = decided_all[decided_all["response_days"].notna() & (decided_all["client_id"] != "UNKNOWN")].copy()
d["won"] = (d["status"] == "Won").astype(int)
res["analysed"] = int(len(d))
res["win_rate_analysed"] = float(d["won"].mean())
d["bucket"] = pd.cut(d["response_days"], [-1, 2, 4, 7, 1000], labels=["0-2 days", "3-4 days", "5-7 days", "8+ days"])

# --- response time ---------------------------------------------------------
b = d.groupby("bucket", observed=True)["won"].agg(quotes="size", won="sum", win_rate="mean").reset_index()
res["by_bucket"] = b.round(4).astype({"bucket": str}).to_dict("records")
sb = d.pivot_table(index="sector", columns="bucket", values="won", aggfunc="mean", observed=True)
sn = d.pivot_table(index="sector", columns="bucket", values="won", aggfunc="size", observed=True)
res["sector_bucket_win_rate"] = sb.round(4).reset_index().to_dict("records")
res["sector_bucket_n"] = sn.reset_index().to_dict("records")
res["corr_overall"] = float(d[["response_days", "won"]].corr().iloc[0, 1])
res["corr_by_sector"] = {s: float(g[["response_days", "won"]].corr().iloc[0, 1]) for s, g in d.groupby("sector")}

# --- price -------------------------------------------------------------------
p = d[d["markup"].notna()].copy()
p["markup_quartile"] = pd.qcut(p["markup"], 4, labels=[1, 2, 3, 4])
p["speed"] = np.where(p["response_days"] <= 4, "Fast (0-4 days)", "Slow (5+ days)")
pq = p.groupby(["markup_quartile", "speed"], observed=True).agg(quotes=("won", "size"), avg_markup=("markup", "mean"), win_rate=("won", "mean")).reset_index()
res["price_speed"] = pq.round(4).astype({"markup_quartile": int}).to_dict("records")
res["markup_won_vs_lost"] = p.groupby("status")["markup"].mean().round(4).to_dict()
res["price_by_size"] = p.groupby("client_size")["markup"].mean().round(4).to_dict()
res["win_rate_by_size"] = d.groupby("client_size")["won"].mean().round(4).to_dict()

# --- loss reasons ------------------------------------------------------------
lost = q[q["status"] == "Lost"]
res["loss_reason_share"] = lost["loss_reason"].value_counts(normalize=True).round(4).to_dict()
rec = lost[lost["loss_reason"] != "Not recorded"]["loss_reason"].value_counts(normalize=True).round(4)
res["loss_reason_share_recorded_only"] = rec.to_dict()

# --- sellers -----------------------------------------------------------------
d["speed"] = np.where(d["response_days"] <= 4, "Fast (0-4 days)", "Slow (5+ days)")
sel = d.groupby("seller").agg(quotes=("won", "size"), avg_response_days=("response_days", "mean"), win_rate=("won", "mean")).reset_index()
sel["win_rate_rank"] = sel["win_rate"].rank(ascending=False).astype(int)
res["sellers"] = sel.round(4).to_dict("records")
sel_speed = d.pivot_table(index="seller", columns="speed", values="won", aggfunc="mean").round(4)
res["sellers_within_speed"] = sel_speed.reset_index().to_dict("records")
res["sector_mix_by_seller"] = d.pivot_table(index="seller", columns="sector", values="won", aggfunc="size").pipe(lambda x: x.div(x.sum(axis=1), axis=0)).round(3).reset_index().to_dict("records")

# --- monthly -----------------------------------------------------------------
m = q.assign(month=q["request_date"].dt.to_period("M").dt.to_timestamp()).groupby("month").agg(
    quotes_sent=("quote_id", "size"), decided=("status", lambda s: s.isin(["Won", "Lost"]).sum()), won=("status", lambda s: (s == "Won").sum())).reset_index()
m["win_rate"] = m["won"] / m["decided"]
m["win_rate_3m_avg"] = m["win_rate"].rolling(3, min_periods=1).mean()
m["cumulative_win_rate"] = m["won"].cumsum() / m["decided"].cumsum()

# --- scenario: what if slow answers were faster? ----------------------------
slow = d[d["response_days"] >= 5]
fast_ref = d[(d["response_days"] >= 3) & (d["response_days"] <= 4)]["won"].mean()
gap = fast_ref - slow["won"].mean()
extra_wins_full = gap * len(slow)
avg_order_value = orders["final_price"].mean()
c = costs.merge(orders[["order_id", "final_price"]], on="order_id")
tot_cost = c[["material_cost", "consumables_cost", "machine_cost", "labor_cost", "logistics_cost", "tooling_cost", "late_penalty"]].sum(axis=1)
margin_pct = float((c["final_price"].sum() - tot_cost.sum()) / c["final_price"].sum())
res["scenario"] = {
    "slow_quotes": int(len(slow)), "slow_win_rate": float(slow["won"].mean()), "reference_win_rate_3_4_days": float(fast_ref),
    "extra_wins_if_gap_fully_closed": float(extra_wins_full), "share_assumed_causal": 0.5,
    "extra_wins_assumed": float(extra_wins_full * .5), "avg_order_value": float(avg_order_value),
    "extra_revenue": float(extra_wins_full * .5 * avg_order_value), "overall_margin_pct": margin_pct,
    "extra_margin": float(extra_wins_full * .5 * avg_order_value * margin_pct),
}
json.dump(res, open(HERE / "results.json", "w"), indent=2, default=str)

# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(7, 4))
ax.bar(b["bucket"].astype(str), b["win_rate"] * 100, color=C["main"])
for i, r in b.iterrows():
    ax.text(i, r["win_rate"] * 100 + 1, f"{r['win_rate']:.0%}", ha="center", fontweight="bold")
    ax.text(i, 1.5, f"n={int(r['quotes'])}", ha="center", color="white", fontsize=8)
ax.axhline(res["win_rate_analysed"] * 100, color=C["accent"], ls="--", label=f"Average {res['win_rate_analysed']:.0%}")
ax.set(title="The slower we answer, the less we win", xlabel="Days between request and our answer", ylabel="Win rate (%)")
ax.legend()
save(fig, HERE / "charts/01_win_rate_by_response_time.png")

fig, ax = plt.subplots(figsize=(8, 4.2))
cols = {"Cosmetics": C["grey"], "Food & Beverage": "#6C8EBF", "Technology": C["main"], "E-commerce & Fashion": C["accent"]}
for s in ["Cosmetics", "Food & Beverage", "Technology", "E-commerce & Fashion"]:
    ax.plot(sb.columns.astype(str), sb.loc[s] * 100, marker="o", lw=2.4 if s.startswith("E-com") else 1.6, color=cols[s], label=s)
ax.set(title="Speed matters most for e-commerce and least for cosmetics", ylabel="Win rate (%)", xlabel="Response time")
ax.legend(frameon=False)
save(fig, HERE / "charts/02_response_by_sector.png")

fig, ax = plt.subplots(figsize=(7.5, 4))
pv = pq.pivot(index="markup_quartile", columns="speed", values="win_rate") * 100
x = np.arange(4)
ax.bar(x - .2, pv["Fast (0-4 days)"], .4, label="Fast answer (0-4 days)", color=C["main"])
ax.bar(x + .2, pv["Slow (5+ days)"], .4, label="Slow answer (5+ days)", color=C["grey"])
ax.set_xticks(x)
ax.set_xticklabels(["Q1\n(lowest markup)", "Q2", "Q3", "Q4\n(highest markup)"])
ax.set(title="Higher prices lose more, but a fast answer beats a low price", ylabel="Win rate (%)")
ax.legend(frameon=False)
save(fig, HERE / "charts/03_price_vs_speed.png")

fig, ax = plt.subplots(figsize=(8, 3.8))
ax.plot(m["month"], m["win_rate"] * 100, color=C["grey"], marker=".", label="Monthly win rate")
ax.plot(m["month"], m["win_rate_3m_avg"] * 100, color=C["main"], lw=2.4, label="3-month average")
ax.set(title="Win rate over time: stable, no trend", ylabel="Win rate (%)")
ax.set_ylim(0, 60)
ax.legend(frameon=False)
save(fig, HERE / "charts/04_win_rate_over_time.png")

fig, ax = plt.subplots(figsize=(6.5, 4.2))
ax.scatter(sel["avg_response_days"], sel["win_rate"] * 100, s=sel["quotes"] / 3, color=C["main"], alpha=.8)
for _, r in sel.iterrows():
    ax.annotate(r["seller"], (r["avg_response_days"], r["win_rate"] * 100), textcoords="offset points", xytext=(6, 6))
ax.set(title="Sellers: the slower the answer, the lower the win rate", xlabel="Average response time (days)", ylabel="Win rate (%)")
save(fig, HERE / "charts/05_sellers.png")

fig, ax = plt.subplots(figsize=(7, 3.8))
lr = pd.Series(res["loss_reason_share"]).sort_values()
ax.barh(lr.index, lr.values * 100, color=[C["grey"] if i == "Not recorded" else C["main"] for i in lr.index])
for i, v in enumerate(lr.values):
    ax.text(v * 100 + .5, i, f"{v:.0%}", va="center")
ax.set(title="Why we lost, according to the CRM (45% not recorded)", xlabel="Share of lost quotes (%)")
save(fig, HERE / "charts/06_stated_loss_reasons.png")

# ---------------------------------------------------------------------------
# Exports for Looker Studio
# ---------------------------------------------------------------------------
LS.mkdir(exist_ok=True)
m.to_csv(LS / "monthly_funnel.csv", index=False, float_format="%.4f")
d.groupby(["sector", "bucket"], observed=True)["won"].agg(quotes="size", win_rate="mean").reset_index().assign(bucket=lambda x: x["bucket"].astype(str)).round(4).to_csv(LS / "response_by_sector.csv", index=False)
b.assign(bucket=b["bucket"].astype(str)).round(4).to_csv(LS / "response_buckets.csv", index=False)
pq.round(4).to_csv(LS / "price_vs_speed.csv", index=False)
sel.round(4).to_csv(LS / "sellers.csv", index=False)
q.to_csv(LS / "clean_quotes_for_dashboard.csv", index=False)


def p_bucket(ax):
    ax.bar(b["bucket"].astype(str), b["win_rate"] * 100, color=C["main"])
    for i, r in b.iterrows():
        ax.text(i, r["win_rate"] * 100 + 1, f"{r['win_rate']:.0%}", ha="center", fontweight="bold", fontsize=9)
    ax.set(title="Win rate by response time", ylabel="%")


def p_sector(ax):
    for s_ in ["Cosmetics", "Food & Beverage", "Technology", "E-commerce & Fashion"]:
        ax.plot(sb.columns.astype(str), sb.loc[s_] * 100, marker="o", color=cols[s_], label=s_, lw=2)
    ax.set(title="Win rate by response time and sector", ylabel="%")
    ax.legend(frameon=False, fontsize=7)


def p_price(ax):
    ax.bar(x - .2, pv["Fast (0-4 days)"], .4, label="Fast", color=C["main"])
    ax.bar(x + .2, pv["Slow (5+ days)"], .4, label="Slow", color=C["grey"])
    ax.set_xticks(x)
    ax.set_xticklabels(["Q1 low", "Q2", "Q3", "Q4 high"])
    ax.set(title="Win rate by markup quartile and speed", ylabel="%")
    ax.legend(frameon=False, fontsize=8)


def p_month(ax):
    ax.plot(m["month"], m["win_rate"] * 100, color=C["grey"], marker=".")
    ax.plot(m["month"], m["win_rate_3m_avg"] * 100, color=C["main"], lw=2.4)
    ax.set(title="Monthly win rate (grey) and 3-month average", ylabel="%", ylim=(0, 60))


preview(LS / "dashboard_preview.png", "OrygamiBox S.A. - Quote funnel (preview)",
        "Static preview of the Looker Studio dashboard. Synthetic data, Jan 2024 - Dec 2025.",
        [("Quotes sent", f"{res['quotes']:,}"), ("Win rate (decided)", f"{res['win_rate_all_decided']:.1%}"),
         ("Win rate, answered in 0-2 days", f"{b.iloc[0]['win_rate']:.0%}"), ("Win rate, answered in 8+ days", f"{b.iloc[3]['win_rate']:.0%}"),
         ("Correlation: days vs win", f"{res['corr_overall']:.2f}")],
        [p_bucket, p_sector, p_price, p_month])
print(json.dumps({k: v for k, v in res.items() if not isinstance(v, (list, dict))}, indent=1))
print(json.dumps(res["scenario"], indent=1))
print(res["corr_by_sector"], res["sellers_within_speed"], res["loss_reason_share_recorded_only"], res["markup_won_vs_lost"], res["price_by_size"], res["win_rate_by_size"])
