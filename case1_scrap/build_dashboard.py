"""
Builds the Case 1 spreadsheet (report + dashboard) from the analysis outputs.

All summary numbers are Excel formulas over the Order_Data and Printing_Data sheets,
so the workbook recalculates if the data changes. The only typed-in values
(blue font) are the 5% quote allowance assumption and the per-group medians,
which are computed in Python (Excel needs array formulas for conditional medians).

Run from the project root (after analysis.py):  python case1_scrap/build_dashboard.py
"""
import json
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = HERE / "dashboard" / "OrygamiBox_Case1_Scrap_Dashboard.xlsx"

res = json.loads((HERE / "results.json").read_text())
od = pd.read_csv(HERE / "dashboard/order_level_scrap.csv")
pr = pd.read_csv(HERE / "dashboard/printing_stage_scrap.csv")
log = pd.read_csv(ROOT / "docs/cleaning_log.csv")

FONT = "Arial"
f_norm = Font(name=FONT, size=10)
f_bold = Font(name=FONT, size=10, bold=True)
f_head = Font(name=FONT, size=10, bold=True, color="FFFFFF")
f_title = Font(name=FONT, size=16, bold=True, color="1F3A5F")
f_sub = Font(name=FONT, size=10, italic=True, color="555555")
f_input = Font(name=FONT, size=10, color="0000FF")          # typed-in values
f_kpi = Font(name=FONT, size=14, bold=True, color="1F3A5F")
fill_head = PatternFill("solid", fgColor="2F5D8A")
fill_kpi = PatternFill("solid", fgColor="EAF1F8")
fill_input = PatternFill("solid", fgColor="FFFF99")
thin = Side(style="thin", color="BBBBBB")
box = Border(left=thin, right=thin, top=thin, bottom=thin)

PCT, INT, USD = "0.0%", "#,##0", "$#,##0"

wb = Workbook()
ws_d = wb.active
ws_d.title = "Dashboard"
ws_rs = wb.create_sheet("By_Run_Size")
ws_f = wb.create_sheet("By_Finish")
ws_p = wb.create_sheet("Press_Shift")
ws_dist = wb.create_sheet("Distribution")
ws_o = wb.create_sheet("Order_Data")
ws_pd = wb.create_sheet("Printing_Data")
ws_cl = wb.create_sheet("Cleaning_Log")
ws_n = wb.create_sheet("Notes_Assumptions")


def header(ws, row, labels, col=1):
    for i, t in enumerate(labels):
        c = ws.cell(row=row, column=col + i, value=t)
        c.font, c.fill, c.border = f_head, fill_head, box
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def style_range(ws, rng, font=f_norm, fmt=None, border=True):
    for row in ws[rng]:
        for c in row:
            c.font = font
            if fmt:
                c.number_format = fmt
            if border:
                c.border = box


def widths(ws, w):
    for i, x in enumerate(w, start=1):
        ws.column_dimensions[get_column_letter(i)].width = x


# ---------------------------------------------------------------------------
# Notes_Assumptions
# ---------------------------------------------------------------------------
ws_n["A1"], ws_n["A1"].font = "Notes and assumptions", f_title
ws_n["A3"], ws_n["A3"].font = "Assumption (edit the yellow cell)", f_bold
ws_n["A4"] = "Scrap allowance built into quotes (% of order quantity)"
ws_n["B4"] = 0.05
ws_n["B4"].font, ws_n["B4"].fill, ws_n["B4"].number_format = f_input, fill_input, PCT
ws_n["C4"] = "The quoting model adds a flat 5% of material for scrap (see docs/data_dictionary.md)."
notes = [
    "Definitions",
    "Units released = pieces sent to the first stage (Printing) of an order.",
    "Scrap units = pieces discarded in Printing, Finishing, Die-cutting, Gluing and Quality control (Dispatch has none).",
    "Scrap % = scrap units / units released.  Weighted rate = total scrap / total released.",
    "Scrap cost = scrap units x material cost per piece. It only values the board, so it is a conservative figure",
    "(printing, finishing and labour already invested in a discarded piece are not counted).",
    "Allowance gap = scrap cost above what the 5% quote allowance covers, per order (never below zero).",
    "",
    "About the numbers",
    "Data is synthetic (AI-generated, with deliberate errors). Cleaning steps are listed in the Cleaning_Log sheet.",
    "Blue font = typed-in values. Per-group medians are computed in Python because Excel needs array formulas for them.",
    "All other figures are formulas over Order_Data and Printing_Data.",
]
for i, t in enumerate(notes, start=6):
    ws_n.cell(row=i, column=1, value=t).font = f_bold if t in ("Definitions", "About the numbers") else f_norm
ws_n["A4"].font = f_norm
ws_n["C4"].font = f_sub
widths(ws_n, [62, 12, 80])

# ---------------------------------------------------------------------------
# Order_Data (one row per order)
# ---------------------------------------------------------------------------
cols = ["order_id", "sector", "qty_ordered", "run_size", "finish", "board_type", "print_machine", "print_shift",
        "input_units", "scrap_units", "scrap_pct", "material_unit_cost", "scrap_cost", "allowance_cost", "gap_cost",
        "final_price"]
header(ws_o, 1, cols)
N = len(od)
LAST = N + 1
for i, r in enumerate(od.itertuples(index=False), start=2):
    ws_o.cell(i, 1, r.order_id)
    ws_o.cell(i, 2, r.sector)
    ws_o.cell(i, 3, int(r.qty_ordered))
    ws_o.cell(i, 4, f'=IF(C{i}<1000,"Under 1,000",IF(C{i}<3000,"1,000-2,999",IF(C{i}<10000,"3,000-9,999","10,000+")))')
    ws_o.cell(i, 5, r.finish)
    ws_o.cell(i, 6, r.board_type)
    ws_o.cell(i, 7, r.print_machine)
    ws_o.cell(i, 8, r.print_shift)
    ws_o.cell(i, 9, int(r.input_units))
    ws_o.cell(i, 10, int(r.scrap_units))
    ws_o.cell(i, 11, f"=J{i}/I{i}")
    ws_o.cell(i, 12, float(r.material_unit_cost))
    ws_o.cell(i, 13, f"=J{i}*L{i}")
    ws_o.cell(i, 14, f"=Notes_Assumptions!$B$4*C{i}*L{i}")
    ws_o.cell(i, 15, f"=MAX(0,M{i}-N{i})")
    ws_o.cell(i, 16, float(r.final_price))
style_range(ws_o, f"A2:P{LAST}", border=False)
for col, fmt in {"C": INT, "I": INT, "J": INT, "K": PCT, "L": "$0.0000", "M": "$#,##0.00", "N": "$#,##0.00", "O": "$#,##0.00", "P": "$#,##0.00"}.items():
    for c in ws_o[f"{col}2:{col}{LAST}"]:
        c[0].number_format = fmt
ws_o.freeze_panes = "B2"
widths(ws_o, [11, 22, 12, 14, 18, 12, 14, 12, 12, 12, 11, 14, 12, 14, 12, 13])
ws_o.row_dimensions[1].height = 30

# Printing_Data
header(ws_pd, 1, ["order_id", "machine_id", "shift", "qty_in", "scrap_units"])
for i, r in enumerate(pr.itertuples(index=False), start=2):
    for j, v in enumerate([r.order_id, r.machine_id, r.shift, int(r.qty_in), int(r.scrap_units)], start=1):
        ws_pd.cell(i, j, v)
PLAST = len(pr) + 1
style_range(ws_pd, f"A2:E{PLAST}", border=False)
ws_pd.freeze_panes = "A2"
widths(ws_pd, [11, 12, 12, 12, 12])


def rng(col):
    return f"Order_Data!${col}$2:${col}${LAST}"


def prng(col):
    return f"Printing_Data!${col}$2:${col}${PLAST}"


# ---------------------------------------------------------------------------
# By_Run_Size and By_Finish
# ---------------------------------------------------------------------------
def group_sheet(ws, title, key_col_letter, labels, med_map):
    ws["A1"], ws["A1"].font = title, f_title
    ws["A2"], ws["A2"].font = "Formulas over Order_Data. Median is typed in (computed in Python).", f_sub
    header(ws, 4, ["Group", "Orders", "Units released", "Scrap units", "Weighted scrap rate", "Scrap cost ($)",
                   "Mean scrap % per order", "Median scrap % per order"])
    ws.row_dimensions[4].height = 32
    for i, lab in enumerate(labels, start=5):
        ws.cell(i, 1, lab)
        ws.cell(i, 2, f"=COUNTIFS({rng(key_col_letter)},$A{i})")
        ws.cell(i, 3, f"=SUMIFS({rng('I')},{rng(key_col_letter)},$A{i})")
        ws.cell(i, 4, f"=SUMIFS({rng('J')},{rng(key_col_letter)},$A{i})")
        ws.cell(i, 5, f"=D{i}/C{i}")
        ws.cell(i, 6, f"=SUMIFS({rng('M')},{rng(key_col_letter)},$A{i})")
        ws.cell(i, 7, f"=AVERAGEIFS({rng('K')},{rng(key_col_letter)},$A{i})")
        ws.cell(i, 8, float(med_map[lab]))
    t = 5 + len(labels)
    ws.cell(t, 1, "Total")
    for c, col in ((2, "B"), (3, "C"), (4, "D"), (6, "F")):
        ws.cell(t, c, f"=SUM({col}5:{col}{t-1})")
    ws.cell(t, 5, f"=D{t}/C{t}")
    ws.cell(t, 7, f"=AVERAGE({rng('K')})")
    ws.cell(t, 8, f"=MEDIAN({rng('K')})")
    style_range(ws, f"A5:H{t}")
    for r in range(5, t + 1):
        for col, fmt in {"B": INT, "C": INT, "D": INT, "E": PCT, "F": USD, "G": PCT, "H": PCT}.items():
            ws[f"{col}{r}"].number_format = fmt
    for r in range(5, t):
        ws[f"H{r}"].font = f_input
    for c in ws[f"A{t}:H{t}"][0]:
        c.font = f_bold
    widths(ws, [20, 10, 15, 13, 17, 14, 18, 18])
    return t - 1


size_labels = ["Under 1,000", "1,000-2,999", "3,000-9,999", "10,000+"]
size_med = {r["run_size"]: r["median_pct"] for r in res["by_run_size"]}
last_size = group_sheet(ws_rs, "Scrap by order size", "D", size_labels, size_med)
fin_labels = ["No finish", "Matte lamination", "Emboss", "Foil"]
fin_med = {r["finish"]: r["median_pct"] for r in res["by_finish"]}
last_fin = group_sheet(ws_f, "Scrap by finish", "E", fin_labels, fin_med)

# ---------------------------------------------------------------------------
# Press_Shift
# ---------------------------------------------------------------------------
ws_p["A1"], ws_p["A1"].font = "Printing scrap rate by machine and shift", f_title
ws_p["A2"], ws_p["A2"].font = "Formulas over Printing_Data. M01/M02 are offset presses, M03 is the digital press.", f_sub
header(ws_p, 4, ["Machine", "Shift", "Runs", "Units printed", "Scrap units", "Scrap rate"])
machines = ["M01", "M02", "M03"]
shifts = ["Morning", "Afternoon", "Night"]
r = 5
for m in machines:
    for s in shifts:
        ws_p.cell(r, 1, m)
        ws_p.cell(r, 2, s)
        ws_p.cell(r, 3, f'=COUNTIFS({prng("B")},A{r},{prng("C")},B{r})')
        ws_p.cell(r, 4, f'=SUMIFS({prng("D")},{prng("B")},A{r},{prng("C")},B{r})')
        ws_p.cell(r, 5, f'=SUMIFS({prng("E")},{prng("B")},A{r},{prng("C")},B{r})')
        ws_p.cell(r, 6, f"=E{r}/D{r}")
        r += 1
style_range(ws_p, "A5:F13")
for rr in range(5, 14):
    for col, fmt in {"C": INT, "D": INT, "E": INT, "F": PCT}.items():
        ws_p[f"{col}{rr}"].number_format = fmt
# matrix used by the chart (shifts in rows, machines in columns)
ws_p["H4"] = "Shift"
header(ws_p, 4, ["Shift", "M01 (Offset A)", "M02 (Offset B)", "M03 (Digital)"], col=8)
for i, s in enumerate(shifts, start=5):
    ws_p.cell(i, 8, s)
    for j, m in enumerate(machines):
        src = 5 + j * 3 + i - 5
        ws_p.cell(i, 9 + j, f"=F{src}")
style_range(ws_p, "H5:K7")
for rr in range(5, 8):
    for col in "IJK":
        ws_p[f"{col}{rr}"].number_format = PCT
widths(ws_p, [10, 12, 9, 14, 12, 12, 3, 12, 16, 16, 16])
ws_p.row_dimensions[4].height = 30

# ---------------------------------------------------------------------------
# Distribution
# ---------------------------------------------------------------------------
ws_dist["A1"], ws_dist["A1"].font = "Distribution of scrap % per order", f_title
ws_dist["A2"], ws_dist["A2"].font = "Number of orders in each 2.5-point band of scrap %.", f_sub
header(ws_dist, 4, ["Band", "From", "To", "Orders"])
edges = [i * 0.025 for i in range(0, 15)]
for i, lo in enumerate(edges, start=5):
    hi = lo + 0.025
    last = i == 5 + len(edges) - 1
    ws_dist.cell(i, 1, f"{lo*100:.1f}%+" if last else f"{lo*100:.1f}-{hi*100:.1f}%")
    ws_dist.cell(i, 2, lo)
    ws_dist.cell(i, 3, 1 if last else hi)
    ws_dist.cell(i, 4, f'=COUNTIFS({rng("K")},">="&B{i},{rng("K")},"<"&C{i})' if not last else f'=COUNTIFS({rng("K")},">="&B{i})')
LD = 5 + len(edges) - 1
style_range(ws_dist, f"A5:D{LD}")
for rr in range(5, LD + 1):
    ws_dist[f"B{rr}"].number_format = PCT
    ws_dist[f"C{rr}"].number_format = PCT
    ws_dist[f"D{rr}"].number_format = INT
widths(ws_dist, [14, 10, 10, 10])

# ---------------------------------------------------------------------------
# Cleaning_Log
# ---------------------------------------------------------------------------
ws_cl["A1"], ws_cl["A1"].font = "Cleaning log (all tables)", f_title
header(ws_cl, 3, ["Table", "Issue found", "Rows affected", "Action taken"])
for i, r in enumerate(log.itertuples(index=False), start=4):
    for j, v in enumerate([r.table, r.issue, int(r.rows_affected), r.action], start=1):
        ws_cl.cell(i, j, v)
style_range(ws_cl, f"A4:D{3+len(log)}")
for rr in range(4, 4 + len(log)):
    ws_cl[f"D{rr}"].alignment = Alignment(wrap_text=True, vertical="top")
    ws_cl[f"B{rr}"].alignment = Alignment(wrap_text=True, vertical="top")
widths(ws_cl, [20, 55, 14, 70])

# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
ws_d.sheet_view.showGridLines = False
ws_d["A1"], ws_d["A1"].font = "OrygamiBox S.A. - Case 1: Scrap in the plant", f_title
ws_d["A2"], ws_d["A2"].font = "Where do we lose the most board, and what does it cost? (Synthetic data, Jan 2024 - Dec 2025)", f_sub

k = lambda r: f"Order_Data!${r}$2:${r}${LAST}"  # noqa: E731
kpis = [
    ("Orders analysed", f"=COUNTA({k('A')})", INT),
    ("Units released to the floor", f"=SUM({k('I')})", INT),
    ("Scrap units", f"=SUM({k('J')})", INT),
    ("Weighted scrap rate", "=E5/C5", PCT),
    ("Mean scrap % per order", f"=AVERAGE({k('K')})", PCT),
    ("Median scrap % per order", f"=MEDIAN({k('K')})", PCT),
    ("Scrap cost, board only ($)", f"=SUM({k('M')})", USD),
    ("Scrap cost as % of revenue", f"=C8/SUM({k('P')})", PCT),
    ("Cost above the 5% quote allowance ($)", f"=SUM({k('O')})", USD),
    ("Top 10% of orders: share of scrap cost", f'=SUMIF({k("M")},">="&LARGE({k("M")},ROUND(COUNT({k("M")})*0.1,0)))/SUM({k("M")})', PCT),
]
# two rows of five KPI tiles: labels on row 4 and 7, values on row 5 and 8
for idx, (lab, formula, fmt) in enumerate(kpis):
    row_lab = 4 if idx < 5 else 7
    col = 1 + (idx % 5) * 2
    lc = ws_d.cell(row_lab, col, lab)
    lc.font, lc.fill, lc.alignment = f_sub, fill_kpi, Alignment(wrap_text=True, vertical="center")
    ws_d.merge_cells(start_row=row_lab, start_column=col, end_row=row_lab, end_column=col + 1)
    vc = ws_d.cell(row_lab + 1, col, formula)
    vc.font, vc.fill, vc.number_format = f_kpi, fill_kpi, fmt
    vc.alignment = Alignment(horizontal="left")
    ws_d.merge_cells(start_row=row_lab + 1, start_column=col, end_row=row_lab + 1, end_column=col + 1)
for rr in (4, 7):
    ws_d.row_dimensions[rr].height = 30
for rr in (5, 8):
    ws_d.row_dimensions[rr].height = 26
for c in range(1, 13):
    ws_d.column_dimensions[get_column_letter(c)].width = 13

def make_bar(title, ytitle, anchor, cats, series, horizontal=False, stacked=False, w=14.5, h=7.5, pct=True):
    ch = BarChart()
    ch.type = "bar" if horizontal else "col"
    ch.title = title
    ch.y_axis.title = ytitle
    ch.width, ch.height = w, h
    for ref in series:
        ch.add_data(ref, titles_from_data=True)
    ch.set_categories(cats)
    ch.x_axis.delete = False
    ch.y_axis.delete = False
    if pct:
        ch.y_axis.number_format = "0%"
    ch.y_axis.majorGridlines = None
    ws_d.add_chart(ch, anchor)
    return ch


make_bar("Mean vs median scrap % by order size", "Scrap % per order", "A11",
         Reference(ws_rs, min_col=1, min_row=5, max_row=last_size),
         [Reference(ws_rs, min_col=7, min_row=4, max_row=last_size), Reference(ws_rs, min_col=8, min_row=4, max_row=last_size)])
make_bar("Mean scrap % by finish", "Scrap % per order", "G11",
         Reference(ws_f, min_col=1, min_row=5, max_row=last_fin),
         [Reference(ws_f, min_col=7, min_row=4, max_row=last_fin)])
make_bar("Printing scrap rate by machine and shift", "Scrap % of units printed", "A27",
         Reference(ws_p, min_col=8, min_row=5, max_row=7),
         [Reference(ws_p, min_col=9, min_row=4, max_row=7), Reference(ws_p, min_col=10, min_row=4, max_row=7),
          Reference(ws_p, min_col=11, min_row=4, max_row=7)])
make_bar("Orders by scrap % band", "Orders", "G27",
         Reference(ws_dist, min_col=1, min_row=5, max_row=LD),
         [Reference(ws_dist, min_col=4, min_row=4, max_row=LD)], pct=False)

ws_d["A43"] = "Source sheets: By_Run_Size, By_Finish, Press_Shift, Distribution, Order_Data, Printing_Data. Notes and assumptions in Notes_Assumptions."
ws_d["A43"].font = f_sub

from openpyxl.worksheet.properties import PageSetupProperties
ws_d.page_setup.orientation = "landscape"
ws_d.page_setup.fitToWidth = 1
ws_d.page_setup.fitToHeight = 1
ws_d.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
for ws in wb.worksheets:
    ws.sheet_properties.tabColor = "2F5D8A" if ws.title == "Dashboard" else "9AA5B1"

OUT.parent.mkdir(exist_ok=True, parents=True)
wb.save(OUT)
print("saved", OUT)
