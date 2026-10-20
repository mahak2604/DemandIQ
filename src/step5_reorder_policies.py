"""
STEP 5 - From prediction to decision: how much should each store order?

Three ordering policies are replayed over the same real demand and the same
supplier delays, so the comparison is fair:

  A. Manager rule      order up to (last 4 weeks' average + 10%) x days to cover
  B. DemandIQ forecast order up to (sum of ML forecasts) + safety stock from the
                       P10-P90 forecast range (95% service level)
  C. DemandIQ + risk   policy B, plus an emergency next-day order whenever the
                       stockout classifier says risk >= threshold

The emergency threshold for C is tuned on the validation window (Apr-May 2015)
and then applied unchanged to the test window (Jun-Jul 2015).
"""
import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from config import (LEAD_TIME, MODEL_DIR, PALETTE, PROC_DIR, REVIEW_DAYS, SERVICE_LEVEL_Z, TAB_DIR,
                    TEST_END, TRAIN_END, VALID_END)
from inventory import Panel, RISK_FEATURES, days_to_next_review, risk_features, simulate, target_level
from utils import save_fig, save_json, save_table

NAMES = {"manager": "A. Manager rule", "demandiq": "B. DemandIQ forecast",
         "demandiq_risk": "C. DemandIQ + risk alerts"}


def run_window(daily, fc, seg, start, measure, end, risk, thr):
    p = Panel(daily, fc, seg, start, end)
    out = {}
    for pol in NAMES:
        s, _, det = simulate(p, pol, measure_from=measure,
                             risk_model=risk if pol == "demandiq_risk" else None, threshold=thr)
        out[pol] = (s, det)
    return p, out


def main():
    print("STEP 5  reorder policies")
    daily = pd.read_parquet(PROC_DIR / "daily.parquet")
    fc = pd.read_parquet(PROC_DIR / "forecasts.parquet")
    seg = pd.read_csv(TAB_DIR / "store_segments.csv")
    risk = joblib.load(MODEL_DIR / "risk_model.joblib")["model"]

    # ---- tune the emergency threshold on the validation window
    pv = Panel(daily, fc, seg, "2015-03-25", VALID_END)
    tune = []
    for thr in (0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.6):
        s, _, _ = simulate(pv, "demandiq_risk", measure_from="2015-04-01", risk_model=risk, threshold=thr)
        tune.append({"threshold": thr, **s})
    tune = pd.DataFrame(tune)
    save_table(tune.round(3), "emergency_threshold_tuning")
    thr = float(tune.loc[tune.total_cost.idxmin(), "threshold"])
    print(f"    emergency threshold chosen on validation: {thr}")

    # ---- the real comparison on the held-out test window
    p, out = run_window(daily, fc, seg, "2015-05-25", "2015-06-01", TEST_END, risk, thr)
    res = pd.DataFrame([{**o[0], "policy": NAMES[k]} for k, o in out.items()])
    base = res.iloc[0]
    res["stockout_change_%"] = 100 * (res["stockout_day_rate_%"] / base["stockout_day_rate_%"] - 1)
    res["cost_change_%"] = 100 * (res.total_cost / base.total_cost - 1)
    res["stock_change_%"] = 100 * (res.avg_stock_days / base.avg_stock_days - 1)
    save_table(res.round(3), "policy_comparison")
    save_json({"emergency_threshold": thr}, "policy_settings")
    print(res[["policy", "stockout_day_rate_%", "fill_rate_%", "avg_stock_days", "emergency_orders",
               "total_cost", "cost_change_%"]].round(2).to_string(index=False))

    # by segment
    rows = []
    for k, (s, det) in out.items():
        t0 = p.dates.get_loc(pd.Timestamp("2015-06-01"))
        so = det["stockout"][:, t0:p.n_real]
        op = p.open[:, t0:p.n_real] > 0
        for g in range(4):
            m = p.segment == g
            rows.append({"policy": NAMES[k], "segment": g,
                         "stockout_day_rate_%": 100 * so[m][op[m]].mean()})
    bys = pd.DataFrame(rows).merge(seg[["segment", "segment_name"]].drop_duplicates(), on="segment")
    save_table(bys.round(3), "policy_by_segment")

    recommendations(p, out, risk, thr)
    figures(res, out, p, bys)
    frontier(p)


def frontier(p):
    """Fair comparison: stockouts vs. stock held, for many buffer / service-level settings."""
    import inventory
    rows = []
    for b in (1.05, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6):
        inventory.MANAGER_BUFFER = b
        s, _, _ = simulate(p, "manager", measure_from="2015-06-01")
        rows.append({**s, "policy": "A. Manager rule", "setting": f"+{(b - 1) * 100:.0f}%"})
    for z in (0.5, 1.0, 1.28, 1.645, 2.0, 2.33):
        inventory.SERVICE_LEVEL_Z = z
        s, _, _ = simulate(p, "demandiq", measure_from="2015-06-01")
        rows.append({**s, "policy": "B. DemandIQ forecast", "setting": f"z={z}"})
    inventory.MANAGER_BUFFER, inventory.SERVICE_LEVEL_Z = 1.2, SERVICE_LEVEL_Z
    f = pd.DataFrame(rows)
    save_table(f.round(4), "policy_frontier")
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    for pol, colr in (("A. Manager rule", PALETTE["grey"]), ("B. DemandIQ forecast", PALETTE["navy"])):
        d = f[f.policy == pol]
        ax.plot(d.avg_stock_days, d["stockout_day_rate_%"], marker="o", color=colr, lw=1.8, label=pol)
        for _, r in d.iterrows():
            ax.annotate(r.setting, (r.avg_stock_days, r["stockout_day_rate_%"]), xytext=(4, 4),
                        textcoords="offset points", fontsize=7.5, color=colr)
    ax.set_xlabel("Average stock held (days of sales)")
    ax.set_ylabel("Stockout days (%)")
    ax.set_title("Same stock, fewer stockouts: DemandIQ shifts the trade-off curve")
    ax.legend()
    save_fig(fig, "fig24_tradeoff_frontier")


def recommendations(p, out, risk, thr):
    """What DemandIQ would tell each store manager on the last evening of the data, for stores that
    are still ordering with their old rule of thumb (the situation on the day DemandIQ is switched on)."""
    det = out["manager"][1]
    t = p.n_real - 1
    on_hand = det["stock"][:, t]
    arr_sched = det["arr_sched"]                                   # orders already placed and in transit
    in_transit = det["arr_actual"][:, t + 1:].sum(1)
    feats = risk_features(p, t, on_hand, arr_sched, det["overdue"], det["stockout"])
    prob = risk.predict_proba(feats[RISK_FEATURES])[:, 1]
    h = days_to_next_review(p.dow[t]) + LEAD_TIME - 1
    S = target_level(p, t, h, "demandiq")
    sl = slice(t + 1, t + 1 + h)
    rec = pd.DataFrame({
        "Store": p.stores, "segment": p.segment,
        "stock_on_hand": on_hand.round(0),
        "in_transit": in_transit.round(0),
        "forecast_next_days": p.fc[:, sl].sum(1).round(0),
        "safety_stock": (SERVICE_LEVEL_Z * np.sqrt((p.sigma[:, sl] ** 2).sum(1))).round(0),
        "order_up_to": S.round(0),
        "recommended_order": np.maximum(0, S - on_hand - in_transit).round(0),
        "stockout_risk": prob.round(3),
        "risk_level": pd.cut(prob, [0, .2, .5, 1], labels=["LOW", "MEDIUM", "HIGH"], include_lowest=True),
    })
    save_table(rec, "reorder_recommendations")


def figures(res, out, p, bys):
    c = PALETTE
    cols = [c["grey"], c["teal"], c["navy"]]
    fig, ax = plt.subplots(1, 4, figsize=(11, 3.1))
    specs = [("stockout_day_rate_%", "Stockout days (%)", "{:.2f}%"),
             ("fill_rate_%", "Fill rate (%)", "{:.2f}%"),
             ("avg_stock_days", "Average stock (days of sales)", "{:.2f}"),
             ("total_cost", "Total cost (EUR million)", "{:.2f}")]
    for a, (col, title, fmt) in zip(ax, specs):
        v = res[col] / (1e6 if col == "total_cost" else 1)
        a.bar(range(3), v, color=cols)
        for i, x in enumerate(v):
            a.text(i, x, fmt.format(x), ha="center", va="bottom", fontsize=8)
        a.set_xticks(range(3), ["A", "B", "C"])
        a.set_title(title, fontsize=9.5)
        if col == "fill_rate_%":
            a.set_ylim(v.min() - 1.5, 100)
        else:
            a.set_ylim(0, v.max() * 1.18)
    fig.text(0.01, -0.04, "A = manager rule    B = DemandIQ forecast + safety stock    "
             "C = B + risk-triggered emergency orders", fontsize=8.5, color="#444")
    save_fig(fig, "fig16_policy_comparison")

    fig, ax = plt.subplots(figsize=(6.6, 3.2))
    parts = [("cost_lost_sales", "Lost sales (margin)", c["red"]), ("cost_holding", "Holding stock", c["teal"]),
             ("cost_ordering", "Ordering / delivery", c["amber"])]
    left = np.zeros(3)
    for col, lab, colr in parts:
        v = res[col].values / 1e6
        ax.barh(range(3), v, left=left, color=colr, label=lab)
        left += v
    for i, v in enumerate(left):
        ax.text(v, i, f"  {v:.2f}M", va="center", fontsize=8.5)
    ax.set_yticks(range(3), res.policy)
    ax.invert_yaxis()
    ax.set_xlim(0, left.max() * 1.18)
    ax.set_xlabel("Cost over Jun-Jul 2015, all 935 stores (EUR million)")
    ax.set_title("Where the money goes")
    ax.legend(fontsize=8, ncol=3, loc="upper left", bbox_to_anchor=(0, -0.22))
    save_fig(fig, "fig17_cost_breakdown")

    # one store, policy A vs C
    s = list(p.stores).index(262) if 262 in p.stores else 0
    t0 = p.dates.get_loc(pd.Timestamp("2015-06-01"))
    dts = p.dates[t0:p.n_real]
    fig, ax = plt.subplots(figsize=(9, 3.3))
    ax.bar(dts, p.demand[s, t0:p.n_real], color=c["light"], edgecolor="#C5CFDA", label="Demand")
    for pol, colr, lab in (("manager", c["grey"], "Stock - A. manager rule"),
                           ("demandiq_risk", c["navy"], "Stock - C. DemandIQ + risk")):
        det = out[pol][1]
        ax.step(dts, det["stock"][s, t0:p.n_real], where="post", color=colr, lw=1.5, label=lab)
        so = det["stockout"][s, t0:p.n_real] > 0
        ax.scatter(dts[so], np.full(so.sum(), -p.demand[s].max() * 0.04), marker="^", s=30, color=colr, zorder=5)
    em = out["demandiq_risk"][1]["emergency"][s, t0:p.n_real] > 0
    ax.scatter(dts[em], np.full(em.sum(), p.demand[s, t0:p.n_real].max() * 1.05), marker="*", s=60,
               color=c["amber"], zorder=5, label="Emergency order placed")
    ax.set_title("Store 262, June-July 2015: triangles mark stockout days")
    import matplotlib.dates as mdates
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    ax.legend(fontsize=8, ncol=4, loc="upper left", bbox_to_anchor=(0, -0.1))
    save_fig(fig, "fig18_policy_store_example")


if __name__ == "__main__":
    main()
