"""Draws the system architecture block diagram used in the report and slides."""
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

from config import PALETTE
from utils import save_fig

C = PALETTE


def box(ax, x, y, w, h, title, lines, color, text_color="white"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.012,rounding_size=0.018",
                                fc=color, ec="none"))
    ax.text(x + w / 2, y + h - 0.035, title, ha="center", va="top", fontsize=9.5,
            fontweight="bold", color=text_color)
    ax.text(x + w / 2, y + h - 0.085, "\n".join(lines), ha="center", va="top", fontsize=7.6,
            color=text_color, linespacing=1.35)


def arrow(ax, x1, y1, x2, y2):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=12,
                                 color="#555", lw=1.2, shrinkA=2, shrinkB=2))


def main():
    fig, ax = plt.subplots(figsize=(10, 5.2))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # row 1 - data
    box(ax, 0.01, 0.70, 0.17, 0.26, "1  Raw data", ["Rossmann sales", "1.02 M store-days", "store master file"], C["grey"])
    box(ax, 0.22, 0.70, 0.20, 0.26, "2  Clean + features", ["935 complete stores", "calendar, promo, holiday", "lags ≥ 7 days old",
                                                           "store profile"], C["navy"])
    box(ax, 0.46, 0.70, 0.17, 0.26, "3  Store segments", ["K-Means (k = 4)", "on 6 store traits", "→ segment feature"], C["teal"])
    box(ax, 0.67, 0.70, 0.32, 0.26, "4  Demand forecast (regression)", ["Naive, Hist. avg, Ridge, Random Forest,",
                                                                       "Gradient Boosting (tuned)", "P10 / P50 / P90 quantile models",
                                                                       "→ units per store per day"], C["navy"])
    # row 2 - decision
    box(ax, 0.67, 0.36, 0.32, 0.26, "5  Stockout risk (classification)", ["inventory replay gives stock & labels",
                                                                          "LogReg, Random Forest, Grad. Boosting",
                                                                          "→ P(stockout in next 3 days)", "→ LOW / MEDIUM / HIGH"], C["red"])
    box(ax, 0.36, 0.36, 0.27, 0.26, "6  Reorder decision", ["order-up-to = forecast", "+ 1.645 x uncertainty",
                                                           "+ emergency order if risk high", "→ how much to order"], C["amber"])
    box(ax, 0.01, 0.36, 0.31, 0.26, "7  Explain (SHAP)", ["global: what drives demand / risk", "local: why this store, this day",
                                                         "promo effect by segment"], C["green"])
    # row 3 - user
    box(ax, 0.12, 0.05, 0.76, 0.16, "8  Streamlit dashboard", ["Overview  |  Store forecast  |  Risk & reorder list  |  Why this forecast?  |  What-if simulator  |  Segments"],
        "#E9EEF3", text_color="#1F3A5F")

    arrow(ax, 0.18, 0.83, 0.22, 0.83)
    arrow(ax, 0.42, 0.83, 0.46, 0.83)
    arrow(ax, 0.63, 0.83, 0.67, 0.83)
    arrow(ax, 0.83, 0.70, 0.83, 0.62)
    arrow(ax, 0.67, 0.49, 0.63, 0.49)
    arrow(ax, 0.36, 0.49, 0.32, 0.49)
    arrow(ax, 0.50, 0.36, 0.50, 0.21)
    arrow(ax, 0.16, 0.36, 0.26, 0.21)
    arrow(ax, 0.83, 0.36, 0.74, 0.21)
    save_fig(fig, "fig00_architecture")


if __name__ == "__main__":
    main()
