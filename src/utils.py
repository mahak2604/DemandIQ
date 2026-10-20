"""Small helpers shared by every step: metrics, plotting style, saving."""
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from config import FIG_DIR, PALETTE, TAB_DIR


# ---------------------------------------------------------------- metrics
def regression_report(y_true, y_pred):
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    err = y_pred - y_true
    return {
        "MAE": np.mean(np.abs(err)),
        "RMSE": np.sqrt(np.mean(err ** 2)),
        "MAPE (%)": 100 * np.mean(np.abs(err) / y_true),
        "WAPE (%)": 100 * np.sum(np.abs(err)) / np.sum(y_true),
        "RMSPE": np.sqrt(np.mean((err / y_true) ** 2)),
        "Bias (%)": 100 * np.sum(err) / np.sum(y_true),
        "R2": 1 - np.sum(err ** 2) / np.sum((y_true - y_true.mean()) ** 2),
    }


# ---------------------------------------------------------------- plotting
def set_style():
    plt.rcParams.update({
        "figure.dpi": 110,
        "savefig.dpi": 200,
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "axes.titlesize": 11,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.labelsize": 10,
        "axes.edgecolor": "#444444",
        "axes.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": "#DDDDDD",
        "grid.linewidth": 0.6,
        "axes.axisbelow": True,
        "legend.frameon": False,
        "xtick.color": "#333333",
        "ytick.color": "#333333",
        "axes.prop_cycle": matplotlib.cycler(color=[
            PALETTE["navy"], PALETTE["teal"], PALETTE["amber"],
            PALETTE["red"], PALETTE["grey"], PALETTE["green"]]),
    })


def save_fig(fig, name):
    path = FIG_DIR / f"{name}.png"
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  saved figure  {path.name}")


def save_table(df, name, index=False):
    path = TAB_DIR / f"{name}.csv"
    df.to_csv(path, index=index)
    print(f"  saved table   {path.name}")


def save_json(obj, name):
    path = TAB_DIR / f"{name}.json"
    path.write_text(json.dumps(obj, indent=2, default=float))
    print(f"  saved json    {path.name}")


set_style()
