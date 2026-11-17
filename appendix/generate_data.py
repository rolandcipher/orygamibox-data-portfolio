"""
Synthetic data generator for the OrygamiBox S.A. case studies.

All data is fictional. The generator uses a fixed seed so every run produces
the same files. It first builds a "true" set of tables (a small simulation of a
folding-carton plant) and then injects realistic data-quality problems
(missing values, duplicates, inconsistent labels, mixed date formats, etc.).

Usage:  python appendix/generate_data.py
Output: data/raw/*.csv  (the messy files the case studies start from)
"""
import math
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 2024
rng = np.random.default_rng(SEED)

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

START, END = pd.Timestamp("2024-01-01"), pd.Timestamp("2025-12-31")
SNAPSHOT = pd.Timestamp("2026-01-31")  # orders not delivered by then stay open

# ----------------------------------------------------------------------------
# 1. Clients
# ----------------------------------------------------------------------------
SECTORS = ["Cosmetics", "Food & Beverage", "E-commerce & Fashion", "Technology"]
N_CLIENTS = 60
name_pool = {
    "Cosmetics": (["Aurora", "Lumen", "Velvet", "Opal", "Silk", "Bloom", "Nectar", "Pearl"],
                  ["Beauty", "Cosmetics", "Skincare", "Labs", "Botanics"]),
    "Food & Beverage": (["Golden", "Harvest", "Alpine", "Cacao", "Maple", "Olive", "Sunrise", "Terra"],
                        ["Foods", "Gourmet", "Tea Co.", "Chocolates", "Pantry"]),
    "E-commerce & Fashion": (["Nova", "Urban", "Kite", "Loop", "Mosaic", "Atlas", "Ember", "Drift"],
                             ["Wear", "Studio", "Apparel", "Market", "Collective"]),
    "Technology": (["Volt", "Pixel", "Nexa", "Quanta", "Orbit", "Cobalt", "Helix", "Zenith"],
                   ["Devices", "Tech", "Systems", "Gadgets", "Electronics"]),
}
CITIES = ["Buenos Aires", "Cordoba", "Rosario", "Mendoza", "La Plata", "Santa Fe"]

clients = pd.DataFrame({
    "client_id": [f"C{i:03d}" for i in range(1, N_CLIENTS + 1)],
    "sector": rng.choice(SECTORS, N_CLIENTS, p=[.25, .20, .35, .20]),
    "client_size": rng.choice(["Small", "Medium", "Large"], N_CLIENTS, p=[.50, .35, .15]),
    "city": rng.choice(CITIES, N_CLIENTS, p=[.40, .15, .12, .10, .13, .10]),
})
used, names = set(), []
for s in clients["sector"]:
    a, b = name_pool[s]
    while True:
        nm = f"{rng.choice(a)} {rng.choice(b)}"
        if nm not in used:
            used.add(nm)
            names.append(nm)
            break
clients["client_name"] = names
clients["signup_date"] = [d.date() for d in (pd.Timestamp("2018-01-01") + pd.to_timedelta(rng.integers(0, 2200, N_CLIENTS), unit="D"))]
pen_p = clients["client_size"].map({"Small": .15, "Medium": .35, "Large": .65})
clients["late_penalty_clause"] = rng.random(N_CLIENTS) < pen_p  # large clients more often have penalty clauses
clients = clients[["client_id", "client_name", "sector", "client_size", "city", "signup_date", "late_penalty_clause"]]

# ----------------------------------------------------------------------------
# 2. Quotes
# ----------------------------------------------------------------------------
N_QUOTES = 3000
size_w = clients["client_size"].map({"Small": 1.0, "Medium": 2.5, "Large": 6.0}).to_numpy()
q_client_idx = rng.choice(N_CLIENTS, N_QUOTES, p=size_w / size_w.sum())
q = pd.DataFrame({"client_id": clients["client_id"].to_numpy()[q_client_idx]})
q = q.merge(clients[["client_id", "sector", "client_size"]], on="client_id", how="left")

days = pd.date_range(START, END, freq="D")
month_w = {1: .8, 2: .8, 3: 1.0, 4: 1.0, 5: 1.0, 6: .9, 7: .9, 8: 1.0, 9: 1.2, 10: 1.4, 11: 1.5, 12: .9}
dw = np.array([month_w[d.month] * (1.1 if d.year == 2025 else 1.0) * (0.0 if d.dayofweek >= 5 else 1.0) for d in days])
q["request_date"] = pd.to_datetime(rng.choice(days, N_QUOTES, p=dw / dw.sum()))

BOARDS = ["SBS", "Coated", "Kraft", "Microflute"]
board_p = {"Cosmetics": [.45, .45, .02, .08], "Food & Beverage": [.50, .10, .35, .05],
           "E-commerce & Fashion": [.10, .05, .45, .40], "Technology": [.20, .25, .05, .50]}
q["board_type"] = [rng.choice(BOARDS, p=board_p[s]) for s in q["sector"]]
gsm_opts = {"SBS": ([250, 300, 350], [.3, .45, .25]), "Coated": ([250, 300, 350], [.3, .45, .25]),
            "Kraft": ([250, 300], [.5, .5]), "Microflute": ([300, 400], [.6, .4])}
q["gsm"] = [int(rng.choice(gsm_opts[b][0], p=gsm_opts[b][1])) for b in q["board_type"]]

FINISHES = ["No finish", "Matte lamination", "Emboss", "Foil"]
fin_p = {"Cosmetics": [.20, .35, .15, .30], "Food & Beverage": [.45, .40, .05, .10],
         "E-commerce & Fashion": [.70, .25, .02, .03], "Technology": [.40, .45, .08, .07]}
q["finish"] = [rng.choice(FINISHES, p=fin_p[s]) for s in q["sector"]]

qty_med = q["client_size"].map({"Small": 1800, "Medium": 4500, "Large": 12000}).to_numpy()
qty = np.clip(qty_med * np.exp(rng.normal(0, 0.9, N_QUOTES)), 500, 60000)
q["quantity"] = np.where(qty > 5000, (qty / 100).round() * 100, (qty / 50).round() * 50).astype(int)
q["print_type"] = np.where(
    q["quantity"] < 1500,
    np.where(rng.random(N_QUOTES) < .60, "Digital", "Offset"),
    np.where(rng.random(N_QUOTES) < .08, "Digital", "Offset"),
)
q["length_mm"] = np.clip(np.exp(rng.normal(math.log(160), .45, N_QUOTES)), 60, 400).round().astype(int)
q["width_mm"] = np.clip(np.exp(rng.normal(math.log(100), .40, N_QUOTES)), 40, 300).round().astype(int)
q["height_mm"] = np.clip(np.exp(rng.normal(math.log(60), .60, N_QUOTES)), 20, 250).round().astype(int)

# --- standard cost model (used for the quote estimate and, later, for actual costs) ---
PRICE_M2 = {"SBS": 0.95, "Coated": 1.05, "Kraft": 0.80, "Microflute": 1.20}  # USD per m2 at 300 gsm
q["blank_area_m2"] = ((2 * (q["length_mm"] + q["width_mm"]) + 20) * (q["height_mm"] + q["width_mm"] + 30)) / 1e6
q["unit_material_cost"] = q["blank_area_m2"] * q["board_type"].map(PRICE_M2) * q["gsm"] / 300
UNIT_PRINT = {"Offset": 0.012, "Digital": 0.040}
UNIT_FINISH = {"No finish": 0.0, "Matte lamination": 0.016, "Emboss": 0.026, "Foil": 0.040}
q["unit_consumables_cost"] = q["print_type"].map(UNIT_PRINT) + q["finish"].map(UNIT_FINISH) * (q["blank_area_m2"] / 0.10)

SPEED = {"M01": 4200, "M02": 3800, "M03": 900, "M04": 2800, "M05": 1100, "M06": 620, "M07": 560, "M08": 2200}
M_SETUP = {"M01": 1.5, "M02": 1.5, "M03": 0.4, "M04": 1.0, "M05": 2.0, "M06": 1.3, "M07": 1.4, "M08": 0.8}
RATE = {"M01": 38, "M02": 34, "M03": 26, "M04": 22, "M05": 28, "M06": 26, "M07": 26, "M08": 20}  # USD / machine hour
LABOR_RATE = 18  # USD / hour (two-person crew)
AVG_RATE = 26


def ideal_hours(row):
    """Process hours without scrap, noise or downtime (what the estimator assumes)."""
    h = (0.4 if row.print_type == "Digital" else 1.5) + row.quantity / (900 if row.print_type == "Digital" else 4000)
    if row.finish != "No finish":
        h += (1.0 if row.finish == "Matte lamination" else 2.0) + row.quantity / (2800 if row.finish == "Matte lamination" else 1100)
    h += 1.35 + row.quantity / 590  # die-cutting
    h += 0.8 + row.quantity / 2200  # gluing
    return h


q["est_hours"] = q.apply(ideal_hours, axis=1)
q["cost_estimate"] = (
    q["quantity"] * 1.05 * q["unit_material_cost"]
    + q["quantity"] * q["unit_consumables_cost"]
    + q["est_hours"] * (AVG_RATE + LABOR_RATE)
    + 35 + q["quantity"] * 0.006
    + 90  # cutting die
).round(2)

mk_mu = q["client_size"].map({"Small": 1.38, "Medium": 1.28, "Large": 1.18}).to_numpy()
mk_sd = np.where(q["client_size"] == "Small", .08, .07)
q["markup"] = np.clip(rng.normal(mk_mu, mk_sd), 1.05, 1.65)
q["quoted_price"] = (q["cost_estimate"] * q["markup"]).round(2)

SELLERS = ["A. Ruiz", "M. Costa", "L. Vega", "P. Soto", "D. Ramos"]
seller_p = {"Cosmetics": [.15, .15, .40, .15, .15], "Food & Beverage": [.20, .25, .20, .20, .15],
            "E-commerce & Fashion": [.25, .25, .10, .20, .20], "Technology": [.20, .20, .20, .20, .20]}
q["seller"] = [rng.choice(SELLERS, p=seller_p[s]) for s in q["sector"]]
seller_eff = {"A. Ruiz": 0.0, "M. Costa": -0.6, "L. Vega": 1.9, "P. Soto": 0.3, "D. Ramos": 0.8}
resp = (rng.gamma(2.2, 1.1, N_QUOTES) + (q["finish"] != "No finish") * 1.2 + (q["quantity"] > 10000) * 0.8
        + q["seller"].map(seller_eff).to_numpy())
resp = resp + (rng.random(N_QUOTES) < .02) * rng.uniform(10, 25, N_QUOTES)
q["response_days"] = np.clip(np.round(resp), 0, 40).astype(int)
q["response_date"] = q["request_date"] + pd.to_timedelta(q["response_days"], unit="D")

# --- who wins? response speed matters most (especially for e-commerce); price matters less ---
sens = q["sector"].map({"Cosmetics": .5, "Food & Beverage": .7, "E-commerce & Fashion": 1.4, "Technology": 1.0}).to_numpy()
size_eff = q["client_size"].map({"Small": -.2, "Medium": 0.0, "Large": .3}).to_numpy()
B0 = -0.40
z = B0 - 0.42 * sens * (q["response_days"].to_numpy() - 3) - 3.0 * (q["markup"].to_numpy() - 1.28) + size_eff + rng.normal(0, .9, N_QUOTES)
won = rng.random(N_QUOTES) < 1 / (1 + np.exp(-z))
recent = q["request_date"] > pd.Timestamp("2025-12-08")
pending = recent & (rng.random(N_QUOTES) < .6)
q["status"] = np.where(pending, "Pending", np.where(won, "Won", "Lost"))
reasons = rng.choice(["Price", "Lead time", "Went with competitor", "Project cancelled"], N_QUOTES, p=[.45, .25, .15, .15])
q["loss_reason"] = np.where(q["status"] == "Lost", reasons, None)
q = q.sort_values("request_date").reset_index(drop=True)
q["quote_id"] = [f"Q{i:05d}" for i in range(1, N_QUOTES + 1)]

# ----------------------------------------------------------------------------
# 3. Machines and downtime
# ----------------------------------------------------------------------------
machines = pd.DataFrame({
    "machine_id": list(SPEED),
    "machine_name": ["Offset Press A", "Offset Press B", "Digital Press", "Laminator", "Foil & Emboss Unit",
                     "Die-cutter A", "Die-cutter B", "Folder-gluer"],
    "stage": ["Printing", "Printing", "Printing", "Finishing", "Finishing", "Die-cutting", "Die-cutting", "Gluing"],
    "install_year": [2019, 2014, 2021, 2018, 2017, 2020, 2013, 2016],
})
n_down = {"M01": 80, "M02": 100, "M03": 60, "M04": 60, "M05": 70, "M06": 90, "M07": 110, "M08": 70}
CAUSES = ["Breakdown", "Scheduled maintenance", "Changeover", "Waiting for material", "Other"]
cause_p = {m: [.25, .25, .20, .15, .15] for m in SPEED}
cause_p["M07"] = [.40, .20, .15, .10, .15]
cause_p["M02"] = [.35, .20, .15, .15, .15]
dt_rows = []
for m, n in n_down.items():
    starts = START + pd.to_timedelta(rng.uniform(0, (END - START).total_seconds(), n), unit="s")
    for s in sorted(starts):
        c = rng.choice(CAUSES, p=cause_p[m])
        mean_h = {"Breakdown": 9, "Scheduled maintenance": 6, "Changeover": 2.5, "Waiting for material": 5, "Other": 3}[c]
        dur = float(np.clip(rng.gamma(2.0, mean_h / 2.0), 0.5, 48))
        dt_rows.append((m, s.floor("min"), (s + pd.Timedelta(hours=dur)).floor("min"), c))
downtime = pd.DataFrame(dt_rows, columns=["machine_id", "start_ts", "end_ts", "cause"]).sort_values("start_ts").reset_index(drop=True)
downtime.insert(0, "downtime_id", [f"D{i:04d}" for i in range(1, len(downtime) + 1)])
events = {m: sorted(zip(g["start_ts"], g["end_ts"])) for m, g in downtime.groupby("machine_id")}

# ----------------------------------------------------------------------------
# 4. Suppliers and purchases
# ----------------------------------------------------------------------------
suppliers = pd.DataFrame({
    "supplier_id": [f"S{i:02d}" for i in range(1, 13)],
    "supplier_name": ["Northline Paperboard", "Cartonera Sur", "Pacific Board Co.", "Coat & Cover", "Brillo Papers",
                      "EcoKraft", "Andean Kraft", "Rio Kraft Mills", "FlutePro", "Corrugados del Plata",
                      "InkWorks", "FoilTech"],
    "main_material": ["SBS", "SBS", "SBS", "Coated", "Coated", "Kraft", "Kraft", "Kraft", "Microflute", "Microflute",
                      "Inks & varnish", "Foil"],
})
MAT_SUPPLIERS = {"SBS": (["S01", "S02", "S03"], [.30, .30, .40]), "Coated": (["S04", "S05"], [.5, .5]),
                 "Kraft": (["S06", "S07", "S08"], [.4, .3, .3]), "Microflute": (["S09", "S10"], [.5, .5])}
LATE_MU = {"S03": (4.5, 3.0), "S07": (2.5, 2.5)}  # (mean extra days, sd); others default to (0.8, 1.5)
SUP_PRICE_ADJ = {"S03": 0.94}                      # the late supplier is also the cheapest


def make_po(material, sup, order_dt, qty_m2):
    promised_lead = int(rng.integers(5, 11))
    mu, sd = LATE_MU.get(sup, (0.8, 1.5))
    late = int(round(max(-2, rng.normal(mu, sd))))
    base = {"SBS": 0.95, "Coated": 1.05, "Kraft": 0.80, "Microflute": 1.20, "Inks & varnish": 4.5, "Foil": 6.0}[material]
    price = base * (1 + 0.08 * ((order_dt - START).days / 730)) * SUP_PRICE_ADJ.get(sup, 1.0) * np.exp(rng.normal(0, .04))
    return dict(supplier_id=sup, material=material, order_date=order_dt.normalize(),
                promised_date=(order_dt + pd.Timedelta(days=promised_lead)).normalize(),
                received_date=(order_dt + pd.Timedelta(days=promised_lead + late)).normalize(),
                quantity_m2=round(float(qty_m2), 0), unit_price=round(float(price), 3))


purchases = []  # purchases triggered by stock-outs are added while building orders

# ----------------------------------------------------------------------------
# 5. Orders and production (a simple plant simulation)
# ----------------------------------------------------------------------------
won_q = q[q["status"] == "Won"].copy()
won_q["approval_date"] = won_q["response_date"] + pd.to_timedelta(
    [int(rng.integers(1, 4)) if s == "Large" else int(rng.integers(1, 7)) for s in won_q["client_size"]], unit="D")
won_q = won_q[won_q["approval_date"] <= END + pd.Timedelta(days=20)].sort_values("approval_date").reset_index(drop=True)
won_q["order_id"] = [f"O{i:05d}" for i in range(1, len(won_q) + 1)]
penalty_clause = dict(zip(clients["client_id"], clients["late_penalty_clause"]))

free_at = {m: START for m in SPEED}
stage_rows, order_rows, cost_rows = [], [], []
sid = 0


def shift_of(ts):
    h = ts.hour
    return "Morning" if 6 <= h < 14 else ("Afternoon" if 14 <= h < 22 else "Night")


def schedule(machine, ready, dur_h):
    start = max(ready, free_at[machine])
    end = start + pd.Timedelta(hours=dur_h)
    for ev_s, ev_e in events[machine]:
        if ev_e <= start:
            continue
        if ev_s >= end:
            break
        if ev_s <= start:           # machine is down when the job wants to start: wait
            start = ev_e
            end = start + pd.Timedelta(hours=dur_h)
        else:                       # machine goes down during the job: job pauses
            end = end + (ev_e - ev_s)
    free_at[machine] = end
    return start.floor("min"), end.floor("min")


def hand_off(ts, mean_h):
    f = 1.35 if ts.month in (10, 11, 12) else 1.0
    return pd.Timedelta(hours=float(np.exp(rng.normal(math.log(mean_h), .7)) * f))


FIXED = {"print_offset": 55, "print_digital": 6, "fin_lam": 20, "fin_big": 40, "diecut": 25, "glue": 10}
REASONS = {
    "Printing": ["Makeready / setup", "Colour deviation", "Registration error", "Material defect", "Operator error"],
    "Finishing": ["Makeready / setup", "Lamination defect", "Foil misalignment", "Material defect", "Operator error"],
    "Die-cutting": ["Makeready / setup", "Die-cut misregistration", "Material defect", "Operator error"],
    "Gluing": ["Makeready / setup", "Glue failure", "Material defect", "Operator error"],
    "Quality control": ["Visual defect", "Dimension out of spec", "Colour deviation"],
}

for r in won_q.itertuples(index=False):
    qty_o = int(r.quantity)
    fixed_plan = (FIXED["print_digital"] if r.print_type == "Digital" else FIXED["print_offset"]) + \
                 ({"No finish": 0, "Matte lamination": FIXED["fin_lam"]}.get(r.finish, FIXED["fin_big"])) + FIXED["diecut"] + FIXED["glue"]
    qty_in = int(math.ceil(qty_o * 1.08 + fixed_plan))   # sheets released to the floor
    start_qty = qty_in

    base = 13 if qty_o < 2000 else (17 if qty_o < 10000 else 23)
    base += -2 if r.sector == "E-commerce & Fashion" else 0
    base += 3 if r.finish != "No finish" else 0
    commit_days = int(max(6, base + rng.integers(-2, 3)))
    approval = pd.Timestamp(r.approval_date)
    committed = approval + pd.Timedelta(days=commit_days)

    p_stock = 0.20 + (0.06 if r.board_type == "Kraft" else 0) + (0.08 if approval.month in (10, 11, 12) else 0)
    purchase_idx, material_ready = None, approval
    if rng.random() < p_stock:
        sups, sp = MAT_SUPPLIERS[r.board_type]
        po = make_po(r.board_type, rng.choice(sups, p=sp), approval, qty_o * r.blank_area_m2 * 1.15 + 200)
        purchases.append(po)
        purchase_idx = len(purchases)
        material_ready = po["received_date"]
    ready = max(approval + pd.Timedelta(days=float(rng.uniform(2, 6))),
                pd.Timestamp(material_ready) + pd.Timedelta(hours=float(rng.uniform(2, 12))))

    stages = ["Printing"] + (["Finishing"] if r.finish != "No finish" else []) + ["Die-cutting", "Gluing", "Quality control", "Dispatch"]
    hours_by_machine, t_ready, prev_end = {}, ready, ready
    for st in stages:
        if st == "Printing":
            m = "M03" if r.print_type == "Digital" else min(["M01", "M02"], key=lambda x: free_at[x])
        elif st == "Finishing":
            m = "M04" if r.finish == "Matte lamination" else "M05"
        elif st == "Die-cutting":
            m = min(["M06", "M07"], key=lambda x: free_at[x])
        elif st == "Gluing":
            m = "M08"
        else:
            m = None

        if m:
            dur = (M_SETUP[m] + qty_in / SPEED[m]) * float(np.exp(rng.normal(0, .12)))
            s_ts, e_ts = schedule(m, t_ready, dur)
        elif st == "Quality control":
            s_ts = t_ready.floor("min")
            e_ts = (t_ready + pd.Timedelta(hours=0.4 + qty_in / 9000)).floor("min")
        else:  # dispatch: waiting for loading / pickup
            wait = float(np.exp(rng.normal(math.log(14), .6)) * (1.2 if t_ready.month in (10, 11, 12) else 1.0))
            s_ts, e_ts = t_ready.floor("min"), (t_ready + pd.Timedelta(hours=wait)).floor("min")

        if st == "Dispatch":
            scrap, reason = 0, None
        else:
            if st == "Printing":
                rate = 0.006 if m == "M03" else 0.016
                rate += {"Kraft": .008, "Microflute": .003, "Coated": -.002, "SBS": 0.0}[r.board_type]
                if m == "M02":
                    rate *= 1.7 if shift_of(s_ts) == "Night" else 1.12
                fixed = FIXED["print_digital"] if m == "M03" else FIXED["print_offset"]
            elif st == "Finishing":
                rate = {"Matte lamination": .009, "Emboss": .022, "Foil": .028}[r.finish]
                fixed = FIXED["fin_lam"] if r.finish == "Matte lamination" else FIXED["fin_big"]
            elif st == "Die-cutting":
                rate = .012 + (.008 if r.board_type == "Microflute" else 0)
                rate *= 1.2 if m == "M07" else 1.0
                fixed = FIXED["diecut"]
            elif st == "Gluing":
                rate, fixed = .006, FIXED["glue"]
            else:
                rate, fixed = .005, 0
            prop = rate * qty_in * float(np.exp(rng.normal(0, .6)))
            if rng.random() < .025:
                prop *= 5  # rare bad event
            scrap = min(int(round(fixed * rng.uniform(.7, 1.3) + prop)), qty_in)
            reason = str(rng.choice(REASONS[st])) if scrap > 0 else None
        qty_out = qty_in - scrap

        sid += 1
        stage_rows.append(dict(stage_record_id=f"R{sid:06d}", order_id=r.order_id, stage=st, machine_id=m,
                               shift=shift_of(s_ts) if m else None, start_ts=s_ts, end_ts=e_ts,
                               qty_in=qty_in, qty_out=qty_out, scrap_units=scrap, scrap_reason=reason))
        if m:
            hours_by_machine[m] = hours_by_machine.get(m, 0) + (e_ts - s_ts).total_seconds() / 3600
        qty_in, prev_end = qty_out, e_ts
        t_ready = e_ts + (hand_off(e_ts, 16 if st == "Quality control" else 5) if st != "Dispatch" else pd.Timedelta(0))

    delivered = (prev_end + pd.Timedelta(days=int(rng.integers(1, 5)))).normalize()
    qty_del = min(qty_o, qty_in)
    disc = 0.0 if rng.random() < .65 else float(rng.uniform(.02, .05) * (1.4 if r.client_size == "Large" else 1))
    price = round(r.quoted_price * (1 - disc), 2)
    late_days = max(0, (delivered - committed).days)
    penalty = round(price * min(.05, .005 * late_days), 2) if penalty_clause[r.client_id] and late_days > 3 else 0.0
    cost_rows.append(dict(
        order_id=r.order_id,
        material_unit_cost=round(r.unit_material_cost, 4),
        material_cost=round(start_qty * r.unit_material_cost, 2),
        consumables_cost=round(qty_o * r.unit_consumables_cost * float(np.exp(rng.normal(0, .05))), 2),
        machine_cost=round(sum(h * RATE[m] for m, h in hours_by_machine.items()), 2),
        labor_cost=round(sum(hours_by_machine.values()) * LABOR_RATE, 2),
        logistics_cost=round(35 + qty_o * 0.006 * float(np.exp(rng.normal(0, .1))), 2),
        tooling_cost=90.0,
        late_penalty=penalty,
    ))
    order_rows.append(dict(
        order_id=r.order_id, quote_id=r.quote_id, client_id=r.client_id, approval_date=approval.normalize(),
        committed_date=committed.normalize(), delivered_date=delivered, qty_ordered=qty_o, qty_delivered=qty_del,
        final_price=price, purchase_id=purchase_idx,
    ))

orders = pd.DataFrame(order_rows)
order_costs = pd.DataFrame(cost_rows)
stages_df = pd.DataFrame(stage_rows)

# replenishment purchases (not tied to a specific order)
for mat, (sups, sp) in MAT_SUPPLIERS.items():
    for d in pd.to_datetime(rng.choice(pd.date_range(START, END), 22, replace=False)):
        purchases.append(make_po(mat, rng.choice(sups, p=sp), d, rng.uniform(4000, 20000)))
for mat, sup in (("Inks & varnish", "S11"), ("Foil", "S12")):
    for d in pd.to_datetime(rng.choice(pd.date_range(START, END), 24, replace=False)):
        purchases.append(make_po(mat, sup, d, rng.uniform(200, 1500)))
purchases_df = pd.DataFrame(purchases)
purchases_df["_old_idx"] = np.arange(1, len(purchases_df) + 1)
purchases_df = purchases_df.sort_values(["order_date", "_old_idx"]).reset_index(drop=True)
purchases_df["purchase_id"] = [f"P{i:04d}" for i in range(1, len(purchases_df) + 1)]
old_to_new = dict(zip(purchases_df["_old_idx"], purchases_df["purchase_id"]))
orders["purchase_id"] = orders["purchase_id"].map(lambda v: old_to_new.get(int(v)) if pd.notna(v) else None)
purchases_df = purchases_df[["purchase_id", "supplier_id", "material", "order_date", "promised_date",
                             "received_date", "quantity_m2", "unit_price"]]

# orders still in transit at the snapshot date stay open
open_mask = orders["delivered_date"] > SNAPSHOT
orders.loc[open_mask, "delivered_date"] = pd.NaT
orders.loc[open_mask, "qty_delivered"] = np.nan

quotes = q[["quote_id", "client_id", "request_date", "response_date", "board_type", "gsm", "print_type", "finish",
            "length_mm", "width_mm", "height_mm", "quantity", "cost_estimate", "quoted_price", "status",
            "loss_reason", "seller"]].copy()

# ----------------------------------------------------------------------------
# 6. Inject data-quality problems (this is what makes the raw files "dirty")
# ----------------------------------------------------------------------------
def pick(n, frac):
    return rng.random(n) < frac


def alt_date(s):
    return pd.Timestamp(s).strftime("%d/%m/%Y")


def variant_case(v):
    return [v.lower(), v.upper(), v + " "][int(rng.integers(0, 3))]


# --- clients
c_raw = clients.copy()
c_raw["signup_date"] = c_raw["signup_date"].astype(str)
m = pick(len(c_raw), .10)
c_raw.loc[m, "sector"] = [variant_case(s) for s in c_raw.loc[m, "sector"]]
c_raw.loc[pick(len(c_raw), .03), "city"] = None

# --- quotes
qr = quotes.copy()
for col in ["request_date", "response_date"]:
    qr[col] = qr[col].dt.strftime("%Y-%m-%d")
    m = pick(len(qr), .04)
    qr.loc[m, col] = [alt_date(x) for x in qr.loc[m, col]]
qr.loc[(qr["status"] != "Won") & pick(len(qr), .08), "response_date"] = None
qr.loc[(qr["status"] == "Lost") & pick(len(qr), .45), "loss_reason"] = None
qr.loc[pick(len(qr), .01), "cost_estimate"] = None
for col in ["board_type", "finish", "print_type"]:
    m = pick(len(qr), .06)
    qr.loc[m, col] = [variant_case(v) for v in qr.loc[m, col]]
m = (qr["finish"] == "Matte lamination") & pick(len(qr), .05)
qr.loc[m, "finish"] = "Matte lam."
cm = pick(len(qr), .015)
for col in ["length_mm", "width_mm", "height_mm"]:
    qr[col] = qr[col].astype(float)
    qr.loc[cm, col] = (qr.loc[cm, col] / 10).round(1)
orph = rng.choice(qr.index.to_numpy(), 5, replace=False)
qr.loc[orph, "client_id"] = [f"C{n}" for n in (61, 62, 63, 64, 65)]
dups = qr.sample(frac=.02, random_state=SEED).copy()
dups["quote_id"] = [f"Q{n:05d}" for n in range(N_QUOTES + 1, N_QUOTES + 1 + len(dups))]
qr = pd.concat([qr, dups], ignore_index=True).sort_values("quote_id").reset_index(drop=True)

# --- orders
orr = orders.copy()
for col in ["approval_date", "committed_date", "delivered_date"]:
    orr[col] = pd.to_datetime(orr[col]).dt.strftime("%Y-%m-%d")
m = pick(len(orr), .03) & orr["delivered_date"].notna()
orr.loc[m, "delivered_date"] = [alt_date(x) for x in orr.loc[m, "delivered_date"]]
orr.loc[pick(len(orr), .01), "qty_delivered"] = None

# --- production stages
sr = stages_df.copy()
sr["start_ts"] = sr["start_ts"].dt.strftime("%Y-%m-%d %H:%M:%S")
sr["end_ts"] = sr["end_ts"].dt.strftime("%Y-%m-%d %H:%M:%S")
swap = pick(len(sr), .004)
sr.loc[swap, ["start_ts", "end_ts"]] = sr.loc[swap, ["end_ts", "start_ts"]].to_numpy()
m = pick(len(sr), .02) & ~swap
sr.loc[m, "start_ts"] = [pd.Timestamp(x).strftime("%d/%m/%Y %H:%M") for x in sr.loc[m, "start_ts"]]
m = pick(len(sr), .04)
sr.loc[m, "stage"] = [variant_case(s) for s in sr.loc[m, "stage"]]
m = pick(len(sr), .02) & sr["machine_id"].notna()
sr.loc[m, "machine_id"] = sr.loc[m, "machine_id"].str.lower()
m = pick(len(sr), .03) & sr["shift"].notna()
sr.loc[m, "shift"] = [variant_case(s) for s in sr.loc[m, "shift"]]
sr.loc[(sr["scrap_units"] > 0) & pick(len(sr), .12), "scrap_reason"] = None
neg = pick(len(sr), .003)
sr.loc[neg, "qty_in"] = -sr.loc[neg, "qty_in"]
neg2 = pick(len(sr), .003)
sr.loc[neg2, "scrap_units"] = -sr.loc[neg2, "scrap_units"]
orph_rows = sr.sample(4, random_state=1).copy()
orph_rows["order_id"] = ["O99901", "O99902", "O99903", "O99904"]
orph_rows["stage_record_id"] = ["R990001", "R990002", "R990003", "R990004"]
dup_rows = sr.sample(frac=.008, random_state=2).copy()
sr = pd.concat([sr, orph_rows, dup_rows], ignore_index=True).sort_values("stage_record_id", kind="stable").reset_index(drop=True)

# --- order costs
cr = order_costs.copy()
cr.loc[pick(len(cr), .03), "logistics_cost"] = None
cr.loc[pick(len(cr), .02), "labor_cost"] = None

# --- downtime
dr = downtime.copy()
dr["start_ts"] = dr["start_ts"].dt.strftime("%Y-%m-%d %H:%M:%S")
dr["end_ts"] = dr["end_ts"].dt.strftime("%Y-%m-%d %H:%M:%S")
dr.loc[pick(len(dr), .04), "cause"] = None
m = pick(len(dr), .05) & dr["cause"].notna()
dr.loc[m, "cause"] = [variant_case(s) for s in dr.loc[m, "cause"]]

# --- purchases
pr = purchases_df.copy()
for col in ["order_date", "promised_date", "received_date"]:
    pr[col] = pd.to_datetime(pr[col]).dt.strftime("%Y-%m-%d")
m = pick(len(pr), .03)
pr.loc[m, "received_date"] = [alt_date(x) for x in pr.loc[m, "received_date"]]
pr.loc[pick(len(pr), .02), "quantity_m2"] = None

outs = {"clients": c_raw, "quotes": qr, "orders": orr, "production_stages": sr, "machines": machines,
        "machine_downtime": dr, "suppliers": suppliers, "purchases": pr, "order_costs": cr}
for name, df in outs.items():
    df.to_csv(RAW / f"{name}.csv", index=False)
    print(f"{name:18s} {len(df):6d} rows")
