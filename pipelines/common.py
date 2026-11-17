"""Small helpers shared by the four case-study scripts."""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "clean"

PALETTE = {"main": "#2F5D8A", "accent": "#E07A2D", "grey": "#9AA5B1", "good": "#3A8F6B", "bad": "#C0392B"}


def load(name, dates=()):
    """Read a cleaned table from data/clean (only empty cells are treated as missing)."""
    return pd.read_csv(CLEAN / f"{name}.csv", keep_default_na=False, na_values=[""], parse_dates=list(dates))


def style():
    plt.rcParams.update({
        "figure.dpi": 150, "savefig.dpi": 150, "font.family": "DejaVu Sans", "font.size": 10,
        "axes.spines.top": False, "axes.spines.right": False, "axes.titleweight": "bold",
        "axes.titlesize": 12, "axes.grid": True, "grid.alpha": 0.25, "axes.axisbelow": True,
    })


def save(fig, path):
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def preview(path, title, subtitle, kpis, panels):
    """Static preview of a dashboard: a row of KPI tiles and up to four chart panels.
    kpis: list of (label, value). panels: list of functions that draw on an Axes."""
    from matplotlib.patches import FancyBboxPatch

    fig = plt.figure(figsize=(13, 8.2))
    fig.text(0.02, 0.965, title, fontsize=16, fontweight="bold", color="#1F3A5F", ha="left")
    fig.text(0.02, 0.935, subtitle, fontsize=9, color="#555555", ha="left")
    n = len(kpis)
    w = 0.96 / n
    for i, (lab, val) in enumerate(kpis):
        ax = fig.add_axes([0.02 + i * w, 0.80, w - 0.012, 0.11])
        ax.axis("off")
        ax.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0,rounding_size=0.06", fc="#EAF1F8", ec="none", transform=ax.transAxes))
        ax.text(0.06, 0.68, lab, fontsize=8.5, color="#555555", transform=ax.transAxes)
        ax.text(0.06, 0.18, val, fontsize=17, fontweight="bold", color="#1F3A5F", transform=ax.transAxes)
    gs = fig.add_gridspec(2, 2, left=0.06, right=0.98, top=0.74, bottom=0.07, hspace=0.55, wspace=0.22)
    for k, fn in enumerate(panels[:4]):
        fn(fig.add_subplot(gs[k // 2, k % 2]))
    fig.savefig(path, dpi=140)
    plt.close(fig)
