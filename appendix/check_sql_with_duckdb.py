"""
Optional check: runs the BigQuery SQL of cases 2, 3 and 4 locally on DuckDB and compares key results
with the pandas numbers in each case's results.json.

BigQuery is the target dialect. DuckDB is only used here to make sure the logic is right, so a few
BigQuery-only functions are swapped before running (SAFE.PARSE_DATE -> TRY_STRPTIME,
APPROX_QUANTILES -> exact QUANTILE_CONT, TIMESTAMP() -> CAST). Results from APPROX_QUANTILES in BigQuery
can differ slightly from the exact percentiles used here.

Needs:  pip install duckdb sqlglot
Run from the project root:  python appendix/check_sql_with_duckdb.py
"""
import json
import re
from pathlib import Path

import duckdb
import sqlglot

ROOT = Path(__file__).resolve().parents[1]
con = duckdb.connect()
con.execute("CREATE SCHEMA IF NOT EXISTS orygamibox")


def register(name, path, all_varchar=False):
    extra = ", all_varchar=true" if all_varchar else ""
    con.execute(f"CREATE OR REPLACE TABLE orygamibox.{name} AS "
                f"SELECT * FROM read_csv('{path}', header=true, nullstr=''{extra})")


register("raw_quotes", ROOT / "data/raw/quotes.csv", True)
for t in ["clients", "orders", "quotes", "production_stages", "machine_downtime", "purchases", "suppliers", "fact_orders"]:
    register(t, ROOT / f"data/clean/{t}.csv")


def run(path):
    sql = Path(path).read_text()
    sql = re.sub(r"SAFE\.PARSE_DATE\('([^']*)',\s*(\w+)\)", r"CAST(TRY_STRPTIME(\2, '\1') AS DATE)", sql)
    sql = re.sub(r"APPROX_QUANTILES\(([^,()]+),\s*100\)\[OFFSET\((\d+)\)\]", r"QUANTILE_CONT(\1, \2/100.0)", sql)
    sql = sql.replace("TIMESTAMP(approval_date)", "CAST(approval_date AS TIMESTAMP)")
    out = None
    for stmt in sqlglot.transpile(sql, read="bigquery", write="duckdb"):
        if not re.sub(r"/\*.*?\*/|--[^\n]*", "", stmt, flags=re.S).strip():
            continue
        cur = con.execute(stmt)
        try:
            out = cur.fetchdf()
        except Exception:
            out = None
    return out


def close(a, b, tol=1e-3):
    return abs(float(a) - float(b)) <= tol


checks = []
r2 = json.loads((ROOT / "case2_quotes/results.json").read_text())
r3 = json.loads((ROOT / "case3_delivery/results.json").read_text())
r4 = json.loads((ROOT / "case4_profitability/results.json").read_text())

# ---- Case 2
sql2 = ROOT / "case2_quotes/sql"
run(sql2 / "01_clean_quotes.sql")
n = con.execute("SELECT COUNT(*) FROM orygamibox.clean_quotes").fetchone()[0]
checks.append(("case2 clean quotes = 3,000", n == r2["quotes"]))
out = run(sql2 / "03_response_time_vs_win.sql").sort_values("response_bucket").reset_index(drop=True)
checks.append(("case2 win rate by response bucket", all(close(out.loc[i, "win_rate"], r2["by_bucket"][i]["win_rate"], 5e-4) for i in range(4))))
for f in ["02_monthly_funnel.sql", "04_price_vs_speed.sql", "05_seller_view.sql", "06_days_between_quotes.sql"]:
    checks.append((f"case2 {f} runs", run(sql2 / f) is not None))

# ---- Case 3
sql3 = ROOT / "case3_delivery/sql"
run(sql3 / "01_order_delivery.sql")
run(sql3 / "02_stage_times.sql")
out = run(sql3 / "03_stage_percentiles.sql").set_index("stage")
checks.append(("case3 waiting share of printing", close(out.loc["Printing", "share_of_total_waiting"], 0.521, 2e-3)))
out = run(sql3 / "04_delay_drivers.sql").set_index("delivery")
late = [d for d in r3["delay_drivers"] if d["delivery"] == "Late"][0]
checks.append(("case3 late orders between-stage days", close(out.loc["Late", "avg_between_stage_days"], late["between_stage_days"], 0.01)))
on_time = con.execute("SELECT AVG(on_time) FROM orygamibox.order_delivery").fetchone()[0]
checks.append(("case3 on-time rate", close(on_time, r3["on_time_rate"], 1e-4)))
for f in ["05_supplier_impact.sql", "06_monthly_on_time.sql", "07_promise_vs_reality.sql"]:
    checks.append((f"case3 {f} runs", run(sql3 / f) is not None))

# ---- Case 4
sql4 = ROOT / "case4_profitability/sql"
out = run(sql4 / "03_margin_bridge.sql").set_index("client_size")
checks.append(("case4 margin bridge: actual margin", close(out.loc["All clients", "actual_margin"], r4["bridge"]["actual_margin"], 1)))
checks.append(("case4 margin bridge: costs above estimate", close(out.loc["All clients", "cost_above_estimate"], r4["bridge"]["cost_above_estimate"], 1)))
out = run(sql4 / "02_pareto_abc.sql").set_index("abc_class")
checks.append(("case4 ABC: class A has 17 clients", int(out.loc["A", "clients"]) == r4["clients_for_80pct_revenue"]))
for f in ["01_client_profitability.sql", "04_margin_by_segment.sql", "05_client_margin_quartiles.sql", "06_cost_structure.sql"]:
    checks.append((f"case4 {f} runs", run(sql4 / f) is not None))

ok = True
for name, passed in checks:
    print(("PASS  " if passed else "FAIL  ") + name)
    ok &= bool(passed)
print("\nAll checks passed." if ok else "\nSome checks failed.")
