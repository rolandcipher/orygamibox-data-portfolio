"""
Cleaning pipeline for the OrygamiBox case studies.

Reads the raw CSV files in data/raw, applies documented cleaning rules and writes
data/clean/*.csv plus docs/cleaning_log.csv (one row per issue found).

Run from the project root:   python pipelines/clean_data.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW, CLEAN, DOCS = ROOT / "data" / "raw", ROOT / "data" / "clean", ROOT / "docs"
CLEAN.mkdir(parents=True, exist_ok=True)
DOCS.mkdir(parents=True, exist_ok=True)

LOG = []


def log(table, issue, rows, action):
    LOG.append({"table": table, "issue": issue, "rows_affected": int(rows), "action": action})


def read(name):
    return pd.read_csv(RAW / f"{name}.csv", dtype=str, keep_default_na=False, na_values=[""])


def parse_dates(s, fmts):
    """Try each format in turn; return a datetime Series."""
    out = pd.Series(pd.NaT, index=s.index, dtype="datetime64[ns]")
    for f in fmts:
        out = out.fillna(pd.to_datetime(s, format=f, errors="coerce"))
    return out


def canon(s, mapping):
    """Normalise labels: strip, lower-case, then map to the canonical spelling."""
    key = s.str.strip().str.lower()
    return key.map(mapping).fillna(s.str.strip())


# ---------------------------------------------------------------------------
# clients
# ---------------------------------------------------------------------------
def clean_clients():
    df = read("clients")
    sector_map = {"cosmetics": "Cosmetics", "food & beverage": "Food & Beverage",
                  "e-commerce & fashion": "E-commerce & Fashion", "technology": "Technology"}
    before = df["sector"].copy()
    df["sector"] = canon(df["sector"], sector_map)
    log("clients", "Inconsistent sector spelling (case / trailing spaces)", (before != df["sector"]).sum(),
        "Mapped to the four canonical sector names")
    n = df["city"].isna().sum()
    df["city"] = df["city"].fillna("Unknown")
    log("clients", "Missing city", n, "Filled with 'Unknown'")
    df["signup_date"] = pd.to_datetime(df["signup_date"])
    df["late_penalty_clause"] = df["late_penalty_clause"].str.lower().eq("true")
    return df


# ---------------------------------------------------------------------------
# quotes
# ---------------------------------------------------------------------------
def clean_quotes(clients, orders_raw):
    df = read("quotes")
    n_raw = len(df)

    for col in ["request_date", "response_date"]:
        iso = pd.to_datetime(df[col], format="%Y-%m-%d", errors="coerce")
        alt = pd.to_datetime(df[col], format="%d/%m/%Y", errors="coerce")
        log("quotes", f"{col} stored as DD/MM/YYYY", (iso.isna() & alt.notna()).sum(), "Parsed both formats into one date type")
        df[col] = iso.fillna(alt)

    for col, mapping in {
        "board_type": {"sbs": "SBS", "coated": "Coated", "kraft": "Kraft", "microflute": "Microflute"},
        "print_type": {"offset": "Offset", "digital": "Digital"},
        "finish": {"no finish": "No finish", "matte lamination": "Matte lamination", "matte lam.": "Matte lamination",
                   "emboss": "Emboss", "foil": "Foil"},
    }.items():
        before = df[col].copy()
        df[col] = canon(df[col], mapping)
        log("quotes", f"Inconsistent {col} labels", (before != df[col]).sum(), "Mapped to canonical labels")

    for col in ["length_mm", "width_mm", "height_mm", "quantity", "gsm", "cost_estimate", "quoted_price"]:
        df[col] = pd.to_numeric(df[col])
    cm = df["length_mm"] < 50  # real lengths are 60-400 mm, so smaller values were entered in cm
    for col in ["length_mm", "width_mm", "height_mm"]:
        df.loc[cm, col] = (df.loc[cm, col] * 10).round()
    log("quotes", "Dimensions entered in cm instead of mm", cm.sum(), "Multiplied the three dimensions by 10")

    # duplicates: same business content under a different quote_id
    key = ["client_id", "request_date", "board_type", "gsm", "print_type", "finish", "length_mm", "width_mm",
           "height_mm", "quantity", "quoted_price"]
    df = df.sort_values("quote_id")
    dup = df.duplicated(subset=key, keep="first")
    log("quotes", "Duplicate quotes (same content, different quote_id)", dup.sum(), "Kept the first quote_id, dropped the rest")
    df = df[~dup].copy()

    # recover unknown clients through the order that references the quote
    known = set(clients["client_id"])
    unk = ~df["client_id"].isin(known)
    n_unk = unk.sum()
    recov = df.loc[unk, "quote_id"].map(orders_raw.set_index("quote_id")["client_id"])
    ok = recov.isin(known)
    df.loc[recov[ok].index, "client_id"] = recov[ok]
    df.loc[df["client_id"].isin(known) == False, "client_id"] = "UNKNOWN"  # noqa: E712
    log("quotes", "client_id not found in clients table", n_unk,
        f"Recovered {int(ok.sum())} from the related order; {int(n_unk - ok.sum())} marked UNKNOWN (excluded from client analysis)")

    n = df["loss_reason"].isna() & (df["status"] == "Lost")
    log("quotes", "Missing loss_reason on lost quotes", n.sum(), "Filled with 'Not recorded' (not guessed)")
    df.loc[df["status"] == "Lost", "loss_reason"] = df.loc[df["status"] == "Lost", "loss_reason"].fillna("Not recorded")
    log("quotes", "Missing response_date (not won)", (df["response_date"].isna()).sum(),
        "Left empty; excluded from response-time analysis")
    log("quotes", "Missing cost_estimate", df["cost_estimate"].isna().sum(), "Left empty; markup not calculated")

    df["response_days"] = (df["response_date"] - df["request_date"]).dt.days
    df["markup"] = (df["quoted_price"] / df["cost_estimate"]).round(4)
    df["status"] = df["status"].str.strip().str.title()
    log("quotes", "Rows after cleaning", len(df), f"Started with {n_raw} rows")
    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# orders
# ---------------------------------------------------------------------------
def clean_orders():
    df = read("orders")
    for col in ["approval_date", "committed_date", "delivered_date"]:
        iso = pd.to_datetime(df[col], format="%Y-%m-%d", errors="coerce")
        alt = pd.to_datetime(df[col], format="%d/%m/%Y", errors="coerce")
        n = (iso.isna() & alt.notna()).sum()
        if n:
            log("orders", f"{col} stored as DD/MM/YYYY", n, "Parsed both formats into one date type")
        df[col] = iso.fillna(alt)
    for col in ["qty_ordered", "qty_delivered", "final_price"]:
        df[col] = pd.to_numeric(df[col])
    if df["delivered_date"].isna().sum():
        log("orders", "Orders not yet delivered at the data snapshot", df["delivered_date"].isna().sum(),
            "Kept; flagged is_open and excluded from delivery metrics")
    log("orders", "Missing qty_delivered on delivered orders",
        (df["qty_delivered"].isna() & df["delivered_date"].notna()).sum(), "Left empty")
    df["is_open"] = df["delivered_date"].isna()
    return df


# ---------------------------------------------------------------------------
# production stages
# ---------------------------------------------------------------------------
def clean_stages(valid_orders):
    df = read("production_stages")
    n_raw = len(df)

    dup = df.duplicated(keep="first")
    log("production_stages", "Exact duplicate rows", dup.sum(), "Dropped")
    df = df[~dup].copy()

    orph = ~df["order_id"].isin(valid_orders)
    log("production_stages", "order_id not found in orders", orph.sum(), "Dropped")
    df = df[~orph].copy()

    before = df["stage"].copy()
    df["stage"] = canon(df["stage"], {"printing": "Printing", "finishing": "Finishing", "die-cutting": "Die-cutting",
                                      "gluing": "Gluing", "quality control": "Quality control", "dispatch": "Dispatch"})
    log("production_stages", "Inconsistent stage labels", (before != df["stage"]).sum(), "Mapped to canonical labels")
    before = df["machine_id"].copy()
    df["machine_id"] = df["machine_id"].str.strip().str.upper()
    log("production_stages", "machine_id in lower case", (before.fillna("") != df["machine_id"].fillna("")).sum(), "Upper-cased")
    before = df["shift"].copy()
    df["shift"] = df["shift"].str.strip().str.capitalize()
    log("production_stages", "Inconsistent shift labels", (before.fillna("") != df["shift"].fillna("")).sum(), "Standardised")

    for col in ["start_ts", "end_ts"]:
        iso = pd.to_datetime(df[col], format="%Y-%m-%d %H:%M:%S", errors="coerce")
        alt = pd.to_datetime(df[col], format="%d/%m/%Y %H:%M", errors="coerce")
        n = (iso.isna() & alt.notna()).sum()
        if n:
            log("production_stages", f"{col} stored as DD/MM/YYYY HH:MM", n, "Parsed both formats")
        df[col] = iso.fillna(alt)
    for col in ["qty_in", "qty_out", "scrap_units"]:
        df[col] = pd.to_numeric(df[col])

    sw = df["end_ts"] < df["start_ts"]
    df.loc[sw, ["start_ts", "end_ts"]] = df.loc[sw, ["end_ts", "start_ts"]].to_numpy()
    log("production_stages", "end_ts earlier than start_ts", sw.sum(), "Swapped the two timestamps")
    n = df["qty_in"] < 0
    df["qty_in"] = df["qty_in"].abs()
    log("production_stages", "Negative qty_in", n.sum(), "Treated as a sign error: absolute value")
    n = df["scrap_units"] < 0
    df["scrap_units"] = df["scrap_units"].abs()
    log("production_stages", "Negative scrap_units", n.sum(), "Treated as a sign error: absolute value")

    bad = (df["qty_in"] - df["scrap_units"] != df["qty_out"])
    log("production_stages", "qty_in - scrap_units does not equal qty_out (after fixes)", bad.sum(), "None needed (check passed)" if bad.sum() == 0 else "Review")

    m = (df["scrap_units"] > 0) & df["scrap_reason"].isna()
    log("production_stages", "Missing scrap_reason where scrap > 0", m.sum(), "Filled with 'Not recorded'")
    df.loc[df["scrap_units"] > 0, "scrap_reason"] = df.loc[df["scrap_units"] > 0, "scrap_reason"].fillna("Not recorded")
    df["scrap_reason"] = df["scrap_reason"].fillna("No scrap")
    df["duration_hours"] = ((df["end_ts"] - df["start_ts"]).dt.total_seconds() / 3600).round(2)
    log("production_stages", "Rows after cleaning", len(df), f"Started with {n_raw} rows")
    return df.sort_values("stage_record_id").reset_index(drop=True)


# ---------------------------------------------------------------------------
# costs, downtime, purchases, small tables
# ---------------------------------------------------------------------------
def clean_costs():
    df = read("order_costs")
    for c in df.columns[1:]:
        df[c] = pd.to_numeric(df[c])
    ratio = (df["labor_cost"] / df["machine_cost"]).median()
    n = df["labor_cost"].isna().sum()
    df["labor_cost"] = df["labor_cost"].fillna((df["machine_cost"] * ratio).round(2))
    log("order_costs", "Missing labor_cost", n, f"Estimated as machine_cost x median labor/machine ratio ({ratio:.2f})")
    orders = read("orders")[["order_id", "qty_ordered"]].assign(qty_ordered=lambda x: pd.to_numeric(x["qty_ordered"]))
    df = df.merge(orders, on="order_id", how="left")
    ok = df["logistics_cost"].notna()
    slope, intercept = np.polyfit(df.loc[ok, "qty_ordered"], df.loc[ok, "logistics_cost"], 1)
    n = (~ok).sum()
    df["logistics_cost"] = df["logistics_cost"].fillna((intercept + slope * df["qty_ordered"]).round(2))
    log("order_costs", "Missing logistics_cost", n,
        f"Estimated with a straight-line fit on quantity (fixed {intercept:.0f} + {slope:.4f} per unit)")
    return df.drop(columns="qty_ordered")


def clean_downtime():
    df = read("machine_downtime")
    for col in ["start_ts", "end_ts"]:
        df[col] = pd.to_datetime(df[col], format="%Y-%m-%d %H:%M:%S")
    before = df["cause"].copy()
    df["cause"] = canon(df["cause"], {"breakdown": "Breakdown", "scheduled maintenance": "Scheduled maintenance",
                                      "changeover": "Changeover", "waiting for material": "Waiting for material",
                                      "other": "Other"})
    log("machine_downtime", "Inconsistent cause labels", ((before != df["cause"]) & before.notna()).sum(), "Mapped to canonical labels")
    n = df["cause"].isna().sum()
    df["cause"] = df["cause"].fillna("Unknown")
    log("machine_downtime", "Missing cause", n, "Filled with 'Unknown'")
    df["duration_hours"] = ((df["end_ts"] - df["start_ts"]).dt.total_seconds() / 3600).round(2)
    return df


def clean_purchases():
    df = read("purchases")
    for col in ["order_date", "promised_date", "received_date"]:
        iso = pd.to_datetime(df[col], format="%Y-%m-%d", errors="coerce")
        alt = pd.to_datetime(df[col], format="%d/%m/%Y", errors="coerce")
        n = (iso.isna() & alt.notna()).sum()
        if n:
            log("purchases", f"{col} stored as DD/MM/YYYY", n, "Parsed both formats")
        df[col] = iso.fillna(alt)
    for col in ["quantity_m2", "unit_price"]:
        df[col] = pd.to_numeric(df[col])
    log("purchases", "Missing quantity_m2", df["quantity_m2"].isna().sum(), "Left empty")
    df["days_late"] = (df["received_date"] - df["promised_date"]).dt.days
    return df


def main():
    clients = clean_clients()
    orders_raw = read("orders")
    quotes = clean_quotes(clients, orders_raw)
    orders = clean_orders()
    stages = clean_stages(set(orders["order_id"]))
    costs = clean_costs()
    downtime = clean_downtime()
    purchases = clean_purchases()
    machines = read("machines")
    suppliers = read("suppliers")

    tables = dict(clients=clients, quotes=quotes, orders=orders, production_stages=stages, order_costs=costs,
                  machine_downtime=downtime, purchases=purchases, machines=machines, suppliers=suppliers)
    for name, df in tables.items():
        df.to_csv(CLEAN / f"{name}.csv", index=False)
        print(f"{name:18s} {len(df):6d} rows -> data/clean/{name}.csv")
    pd.DataFrame(LOG).to_csv(DOCS / "cleaning_log.csv", index=False)
    print(f"\ncleaning_log.csv: {len(LOG)} entries")


if __name__ == "__main__":
    main()
