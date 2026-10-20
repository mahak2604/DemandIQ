"""
STEP 4 - Stockout-risk classification.

1. Replay the store manager's rule of thumb ("order the last 4 weeks' average
   + 10%") over the real demand to get stock levels and stockout days.
2. For every store, every evening, describe the situation (stock on hand,
   forecast demand, deliveries due, promotions coming ...) and label it 1 if the
   store runs out of stock in the next 3 days.
3. Train classifiers to predict that label and pick the best one.

Output
  outputs/models/risk_model.joblib
  data/processed/risk_data.parquet
"""
import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.calibration import calibration_curve
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, brier_score_loss, confusion_matrix,
                             f1_score, precision_recall_curve, precision_score, recall_score,
                             roc_auc_score, roc_curve)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from config import (MODEL_DIR, PALETTE, PROC_DIR, RANDOM_STATE, RISK_FORECAST_CUTOFF, TAB_DIR,
                    TEST_END, TRAIN_END, VALID_END)
from inventory import RISK_FEATURES, Panel, add_labels, simulate
from utils import save_fig, save_json, save_table


class ManagerRule:
    """Baseline: worry when stock + deliveries due cover less than the coming trading days at usual sales."""
    def predict_proba(self, X):
        cover = (X["stock_days"] + X["incoming_3d_days"]) / np.maximum(X["open_days_next_3"], 1)
        score = 1 / (1 + np.exp(4 * (cover - 1.2)))
        return np.c_[1 - score, score]


def build_dataset():
    daily = pd.read_parquet(PROC_DIR / "daily.parquet")
    fc = pd.read_parquet(PROC_DIR / "forecasts.parquet")
    seg = pd.read_csv(TAB_DIR / "store_segments.csv")
    panel = Panel(daily, fc, seg, "2013-02-01", TEST_END)
    summary, rec, detail = simulate(panel, "manager", measure_from="2014-07-01",
                                    record_from=pd.Timestamp(RISK_FORECAST_CUTOFF) + pd.Timedelta(days=1))
    data = add_labels(rec, panel, detail)
    data = data[data.Date <= pd.Timestamp(TEST_END) - pd.Timedelta(days=3)]
    data.to_parquet(PROC_DIR / "risk_data.parquet", index=False)

    so = detail["stockout"][:, :panel.n_real]
    op = panel.open[:, :panel.n_real] > 0
    sim_info = {
        "simulated_store_days": int(op.sum()),
        "stockout_day_rate_%": float(100 * so[op].mean()),
        "stockout_rate_promo_days_%": float(100 * so[op & (panel.promo[:, :panel.n_real] > 0)].mean()),
        "stockout_rate_non_promo_%": float(100 * so[op & (panel.promo[:, :panel.n_real] == 0)].mean()),
        "fill_rate_%": float(100 * (1 - detail["lost"][:, :panel.n_real].sum() / panel.demand[:, :panel.n_real].sum())),
        "risk_rows": len(data),
        "positive_rate_%": float(100 * data.stockout_next_3d.mean()),
    }
    save_json(sim_info, "inventory_simulation_summary")
    print("   ", {k: round(v, 2) for k, v in sim_info.items()})
    inventory_figure(panel, detail)
    return data


def inventory_figure(panel, detail):
    c = PALETTE
    s = list(panel.stores).index(262) if 262 in panel.stores else 0
    t0 = panel.dates.get_loc(pd.Timestamp("2015-03-02"))
    t1 = t0 + 56
    dts = panel.dates[t0:t1]
    fig, ax = plt.subplots(figsize=(9, 3.4))
    ax.bar(dts, panel.demand[s, t0:t1], color=c["light"], edgecolor="#B8C4D0", label="Daily demand (actual sales)")
    ax.step(dts, detail["stock"][s, t0:t1], where="post", color=c["navy"], lw=1.6, label="Stock at close of day")
    so = detail["stockout"][s, t0:t1] > 0
    ax.scatter(dts[so], np.zeros(so.sum()) + panel.demand[s, t0:t1].max() * 0.04, color=c["red"],
               marker="v", s=40, zorder=5, label="Stockout day")
    pr = panel.promo[s, t0:t1] > 0
    ax.scatter(dts[pr], np.full(pr.sum(), panel.demand[s, t0:t1].max() * 1.08), marker="s", s=10,
               color=c["amber"], label="Promotion")
    ax.set_title("Inventory replay for store 262 under the manager's rule (Mar-Apr 2015)")
    import matplotlib.dates as mdates
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    ax.set_ylabel("Units (sales value)")
    ax.legend(ncol=4, fontsize=8, loc="upper left", bbox_to_anchor=(0, -0.12))
    save_fig(fig, "fig12_inventory_replay")


def evaluate(name, y, prob, thr):
    pred = (prob >= thr).astype(int)
    return {"Model": name, "ROC-AUC": roc_auc_score(y, prob), "PR-AUC": average_precision_score(y, prob),
            "Precision": precision_score(y, pred, zero_division=0), "Recall": recall_score(y, pred),
            "F1": f1_score(y, pred), "Brier": brier_score_loss(y, np.clip(prob, 0, 1)), "Threshold": thr}


def best_threshold(y, prob):
    p, r, t = precision_recall_curve(y, prob)
    f1 = 2 * p * r / np.maximum(p + r, 1e-9)
    return float(t[np.argmax(f1[:-1])])


def main():
    print("STEP 4  stockout risk")
    data = build_dataset()
    train = data[data.Date <= TRAIN_END]
    valid = data[(data.Date > TRAIN_END) & (data.Date <= VALID_END)]
    test = data[data.Date > VALID_END]
    X = lambda d: d[RISK_FEATURES]
    y = lambda d: d.stockout_next_3d.astype(int)
    print(f"    rows train {len(train)}  valid {len(valid)}  test {len(test)}   positives {y(train).mean():.1%}")

    models = {
        "Manager rule of thumb": ManagerRule(),
        "Logistic Regression": make_pipeline(StandardScaler(), LogisticRegression(
            max_iter=2000, class_weight="balanced")),
        "Random Forest": RandomForestClassifier(n_estimators=200, min_samples_leaf=20, max_features=0.5,
                                                class_weight="balanced_subsample", n_jobs=-1,
                                                random_state=RANDOM_STATE),
        "Gradient Boosting": HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05,
                                                            max_leaf_nodes=31, min_samples_leaf=50,
                                                            l2_regularization=1.0,
                                                            random_state=RANDOM_STATE),
    }
    rows, probs, thresholds = [], {}, {}
    for name, m in models.items():
        if name != "Manager rule of thumb":
            m.fit(X(train), y(train))
        pv = m.predict_proba(X(valid))[:, 1]
        thr = best_threshold(y(valid), pv)              # threshold chosen on validation only
        pt = m.predict_proba(X(test))[:, 1]
        thresholds[name] = thr
        probs[name] = pt
        rows.append({"Split": "Validation", **evaluate(name, y(valid), pv, thr)})
        rows.append({"Split": "Test", **evaluate(name, y(test), pt, thr)})
        print(f"    {name:24s} test ROC-AUC {rows[-1]['ROC-AUC']:.3f}  PR-AUC {rows[-1]['PR-AUC']:.3f}  "
              f"recall {rows[-1]['Recall']:.2f}  precision {rows[-1]['Precision']:.2f}")
    res = pd.DataFrame(rows)
    save_table(res.round(4), "stockout_model_results")

    best = "Gradient Boosting"
    joblib.dump({"model": models[best], "threshold": thresholds[best], "features": RISK_FEATURES},
                MODEL_DIR / "risk_model.joblib")

    cm = confusion_matrix(y(test), (probs[best] >= thresholds[best]).astype(int))
    save_json({"confusion_matrix": cm.tolist(), "threshold": thresholds[best],
               "test_positive_rate": float(y(test).mean())}, "stockout_confusion")
    figures(y(test), probs, thresholds, cm, test)


def figures(yt, probs, thresholds, cm, test):
    c = PALETTE
    cols = {"Manager rule of thumb": c["grey"], "Logistic Regression": c["teal"],
            "Random Forest": c["amber"], "Gradient Boosting": c["navy"]}
    fig, ax = plt.subplots(1, 2, figsize=(9.4, 3.6))
    for name, pr in probs.items():
        fpr, tpr, _ = roc_curve(yt, pr)
        ax[0].plot(fpr, tpr, color=cols[name], lw=1.6, label=f"{name} ({roc_auc_score(yt, pr):.3f})")
        p, r, _ = precision_recall_curve(yt, pr)
        ax[1].plot(r, p, color=cols[name], lw=1.6, label=f"{name} ({average_precision_score(yt, pr):.3f})")
    ax[0].plot([0, 1], [0, 1], color="#BBB", ls="--", lw=1)
    ax[0].set_xlabel("False positive rate"); ax[0].set_ylabel("True positive rate")
    ax[0].set_title("ROC curve (AUC)"); ax[0].legend(fontsize=7.5, loc="lower right")
    ax[1].axhline(yt.mean(), color="#BBB", ls="--", lw=1)
    ax[1].set_xlabel("Recall"); ax[1].set_ylabel("Precision")
    ax[1].set_title("Precision-recall curve (PR-AUC)"); ax[1].legend(fontsize=7.5, loc="upper right")
    save_fig(fig, "fig13_roc_pr_curves")

    fig, ax = plt.subplots(1, 2, figsize=(8.6, 3.5), gridspec_kw={"width_ratios": [1, 1.25]})
    im = ax[0].imshow(cm, cmap="Blues")
    lab = [["True negative", "False alarm"], ["Missed stockout", "Caught stockout"]]
    for i in range(2):
        for j in range(2):
            ax[0].text(j, i, f"{cm[i, j]:,}\n{lab[i][j]}", ha="center", va="center", fontsize=8.5,
                       color="white" if cm[i, j] > cm.max() * .5 else "#222")
    ax[0].set_xticks([0, 1], ["Predicted: safe", "Predicted: at risk"])
    ax[0].set_yticks([0, 1], ["Actual: safe", "Actual: stockout"], rotation=90, va="center")
    ax[0].grid(False)
    ax[0].set_title(f"Confusion matrix (threshold {thresholds['Gradient Boosting']:.2f})")
    for name in ["Logistic Regression", "Gradient Boosting"]:
        fr, mp = calibration_curve(yt, probs[name], n_bins=10, strategy="quantile")
        ax[1].plot(mp, fr, marker="o", ms=3.5, color=cols[name], label=name)
    ax[1].plot([0, 1], [0, 1], color="#BBB", ls="--", lw=1, label="Perfect calibration")
    ax[1].set_xlabel("Predicted probability"); ax[1].set_ylabel("Observed stockout rate")
    ax[1].set_title("Calibration: does 80% mean 80%?")
    ax[1].legend(fontsize=8)
    save_fig(fig, "fig14_confusion_calibration")

    # risk bands
    pr = probs["Gradient Boosting"]
    band = pd.cut(pr, [0, .2, .5, 1.0], labels=["LOW (<20%)", "MEDIUM (20-50%)", "HIGH (>50%)"],
                  include_lowest=True)
    t = pd.DataFrame({"band": band, "y": yt.values}).groupby("band", observed=False).agg(
        share=("y", "size"), rate=("y", "mean"))
    t["share"] = t.share / t.share.sum() * 100
    save_table(t.reset_index().round(4), "risk_bands")
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.bar(range(3), t.rate * 100, color=[c["green"], c["amber"], c["red"]])
    for i, (sh, rt) in enumerate(zip(t.share, t.rate)):
        ax.text(i, rt * 100 + 1.5, f"{rt:.0%} ran out\n({sh:.1f}% of store-days)", ha="center", fontsize=8.5)
    ax.set_xticks(range(3), t.index)
    ax.set_ylabel("Actual stockout rate (%)")
    ax.set_ylim(0, max(t.rate * 100) * 1.35)
    ax.set_title("Risk levels on the test window")
    save_fig(fig, "fig15_risk_bands")


if __name__ == "__main__":
    main()
