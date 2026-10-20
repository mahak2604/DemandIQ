"""
STEP 2 - Group the stores into "personas" with K-Means clustering.

Why: a manager cannot look at 935 stores one by one. Clustering finds a handful
of store types that behave alike (big and steady, promotion-hungry, ...). The
segment is then used as a feature by the demand model and shown in the
dashboard.

Output
  outputs/tables/store_segments.csv
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from config import N_SEGMENTS, PALETTE, PROC_DIR, RANDOM_STATE, TRAIN_END
from utils import save_fig, save_json, save_table

PROFILE_COLS = {
    "avg_sales": "Average daily sales",
    "promo_lift": "Promotion uplift",
    "volatility": "Day-to-day volatility (CV)",
    "saturday_share": "Saturday vs weekday sales",
    "december_lift": "December uplift",
    "log_comp_distance": "Distance to competitor (log)",
}
SEG_COLORS = [PALETTE["navy"], PALETTE["teal"], PALETTE["amber"], PALETTE["red"], PALETTE["grey"]]


def store_profiles(df):
    tr = df[df.Date <= TRAIN_END]
    g = tr.groupby("Store")
    weekday = tr[tr.day_of_week <= 5].groupby("Store").Sales.mean()
    sat = tr[tr.day_of_week == 6].groupby("Store").Sales.mean()
    dec = tr[tr.month == 12].groupby("Store").Sales.mean()
    rest = tr[tr.month != 12].groupby("Store").Sales.mean()
    prof = pd.DataFrame({
        "avg_sales": g.Sales.mean(),
        "promo_lift": g.store_promo_lift.first(),
        "volatility": g.Sales.std() / g.Sales.mean(),
        "saturday_share": (sat / weekday).fillna(1.0),
        "december_lift": dec / rest - 1,
        "log_comp_distance": g.log_competition_distance.first(),
    })
    return prof


def name_segments(centres):
    """Give each cluster a plain-English name from its centre (z-scores)."""
    names = {}
    left = list(centres.index)
    rules = [
        ("High-volume flagships", lambda c: c.avg_sales),
        ("Promotion-driven", lambda c: c.promo_lift - 0.5 * c.avg_sales),
        ("Weekend & seasonal shoppers", lambda c: c.saturday_share + c.december_lift),
    ]
    for label, score in rules:
        best = max(left, key=lambda i: score(centres.loc[i]))
        names[best] = label
        left.remove(best)
    for i in left:
        names[i] = "Steady neighbourhood stores"
    return names


def main():
    print("STEP 2  store segmentation (K-Means)")
    df = pd.read_parquet(PROC_DIR / "model_data.parquet")
    prof = store_profiles(df)
    X = StandardScaler().fit_transform(prof)

    # Choose k with the elbow (inertia) and silhouette score
    ks = range(2, 9)
    inertia, sil = [], []
    for k in ks:
        km = KMeans(k, n_init=20, random_state=RANDOM_STATE).fit(X)
        inertia.append(km.inertia_)
        sil.append(silhouette_score(X, km.labels_))
    fig, ax = plt.subplots(1, 2, figsize=(8, 2.9))
    ax[0].plot(list(ks), inertia, marker="o", color=PALETTE["navy"])
    ax[0].axvline(N_SEGMENTS, color=PALETTE["amber"], ls="--", lw=1)
    ax[0].set_title("Elbow: within-cluster spread")
    ax[0].set_xlabel("Number of clusters k")
    ax[1].plot(list(ks), sil, marker="o", color=PALETTE["teal"])
    ax[1].axvline(N_SEGMENTS, color=PALETTE["amber"], ls="--", lw=1)
    ax[1].set_title("Silhouette score (higher = cleaner)")
    ax[1].set_xlabel("Number of clusters k")
    save_fig(fig, "fig05_kmeans_choice")

    km = KMeans(N_SEGMENTS, n_init=50, random_state=RANDOM_STATE).fit(X)
    prof["cluster"] = km.labels_
    centres = pd.DataFrame(km.cluster_centers_, columns=prof.columns[:-1])
    names = name_segments(centres)
    order = ["High-volume flagships", "Promotion-driven", "Weekend & seasonal shoppers",
             "Steady neighbourhood stores"]
    seg_id = {names[i]: order.index(names[i]) for i in names}
    prof["segment_name"] = prof.cluster.map(names)
    prof["segment"] = prof.segment_name.map(seg_id)

    # Profile heat-map: how each segment differs from the average store
    z = pd.DataFrame(X, index=prof.index, columns=PROFILE_COLS.keys())
    zc = z.groupby(prof.segment).mean().reindex(range(N_SEGMENTS))
    counts = prof.segment.value_counts().reindex(range(N_SEGMENTS))
    fig, ax = plt.subplots(figsize=(8.2, 3.2))
    im = ax.imshow(zc.values, cmap="RdBu_r", vmin=-1.6, vmax=1.6, aspect="auto")
    short = ["Avg. daily\nsales", "Promotion\nuplift", "Volatility\n(CV)", "Saturday vs\nweekday",
             "December\nuplift", "Competitor\ndistance"]
    ax.set_xticks(range(len(PROFILE_COLS)), short, fontsize=8.5)
    ax.set_yticks(range(N_SEGMENTS), [f"{order[i]}  (n={counts[i]})" for i in range(N_SEGMENTS)], fontsize=8.5)
    for i in range(N_SEGMENTS):
        for j in range(len(PROFILE_COLS)):
            ax.text(j, i, f"{zc.values[i, j]:+.1f}", ha="center", va="center", fontsize=8,
                    color="white" if abs(zc.values[i, j]) > .9 else "#222")
    ax.grid(False)
    ax.set_title("Segment profiles (z-score vs. the average store)")
    fig.colorbar(im, ax=ax, fraction=.025, pad=.01)
    save_fig(fig, "fig06_segment_profiles")

    # 2-D picture of the clusters (PCA is only used for drawing)
    p2 = PCA(2, random_state=RANDOM_STATE).fit_transform(X)
    fig, ax = plt.subplots(figsize=(5.6, 3.8))
    for s in range(N_SEGMENTS):
        m = prof.segment.values == s
        ax.scatter(p2[m, 0], p2[m, 1], s=9, alpha=.75, color=SEG_COLORS[s], label=order[s])
    ax.set_xlabel("Principal component 1")
    ax.set_ylabel("Principal component 2")
    ax.set_title("935 stores in four K-Means segments")
    ax.legend(fontsize=8, loc="best", markerscale=1.6)
    save_fig(fig, "fig07_segment_scatter")

    raw_means = prof.groupby("segment_name")[list(PROFILE_COLS)].mean().reindex(order)
    raw_means["stores"] = prof.segment_name.value_counts().reindex(order)
    save_table(raw_means.round(3).reset_index(), "segment_summary")
    save_table(prof.reset_index()[["Store", "segment", "segment_name"] + list(PROFILE_COLS)], "store_segments")
    save_json({"k_values": list(ks), "inertia": inertia, "silhouette": sil,
               "chosen_k": N_SEGMENTS, "silhouette_chosen": sil[N_SEGMENTS - 2]}, "kmeans_selection")
    print(raw_means.round(2).to_string())


if __name__ == "__main__":
    main()
