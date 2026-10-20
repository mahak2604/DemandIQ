"""
DemandIQ - interactive dashboard.

Run from the project folder:
    streamlit run app/app.py
"""
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import shap
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from config import (LEAD_TIME, MODEL_DIR, PALETTE, PROC_DIR, SERVICE_LEVEL_Z, TAB_DIR,  # noqa: E402
                    VALID_END)
from step6_explain import NICE  # noqa: E402

st.set_page_config(page_title="DemandIQ", page_icon="📦", layout="wide")
C = PALETTE


# ------------------------------------------------------------------ data
@st.cache_resource
def load_models():
    return {
        "gbm": joblib.load(MODEL_DIR / "demand_gbm.joblib"),
        "p10": joblib.load(MODEL_DIR / "demand_p10.joblib"),
        "p90": joblib.load(MODEL_DIR / "demand_p90.joblib"),
        "meta": joblib.load(MODEL_DIR / "demand_meta.joblib"),
        "risk": joblib.load(MODEL_DIR / "risk_model.joblib"),
    }


@st.cache_data
def load_data():
    seg = pd.read_csv(TAB_DIR / "store_segments.csv")
    df = pd.read_parquet(PROC_DIR / "model_data.parquet")
    df = df[df.Date > VALID_END].merge(seg[["Store", "segment", "segment_name"]], on="Store")
    fc = pd.read_parquet(PROC_DIR / "forecasts.parquet")
    fc = fc[fc.Date > VALID_END]
    tabs = {n: pd.read_csv(TAB_DIR / f"{n}.csv") for n in
            ["demand_model_results", "stockout_model_results", "policy_comparison",
             "reorder_recommendations", "segment_summary"]}
    return df, fc, seg, tabs


M = load_models()
FEATS = M["meta"]["features"]
test, fc, seg, T = load_data()


def predict(rows):
    X = rows[FEATS]
    return (np.expm1(M["gbm"].predict(X)), np.expm1(M["p10"].predict(X)), np.expm1(M["p90"].predict(X)))


def order_quantity(p50, p10, p90, stock):
    sigma = (p90 - p10) / 2.563
    target = p50.sum() + SERVICE_LEVEL_Z * np.sqrt((sigma ** 2).sum())
    return target, max(0.0, target - stock)


def kpi(col, label, value, note="", lower_is_better=False):
    col.metric(label, value, note, delta_color="inverse" if lower_is_better else "normal")


# ------------------------------------------------------------------ sidebar
st.sidebar.title("DemandIQ")
st.sidebar.caption("Demand & stockout-risk prediction for 935 Rossmann stores - classical ML only.")
PAGES = ["Overview", "Store forecast", "Stockout risk & reorder", "Why this forecast?", "What-if simulator",
         "Store segments"]
qp = st.query_params                      # e.g. ?page=What-if%20simulator&store=262 (handy for demos)
page = st.sidebar.radio("Go to", PAGES, index=PAGES.index(qp["page"]) if qp.get("page") in PAGES else 0)
STORES = sorted(test.Store.unique())
DEFAULT_STORE = STORES.index(int(qp["store"])) if qp.get("store", "").isdigit() and int(qp["store"]) in STORES else STORES.index(262)
st.sidebar.markdown("---")
st.sidebar.caption("Test window: 1 Jun - 31 Jul 2015 (never seen in training).")

# ------------------------------------------------------------------ pages
if page == "Overview":
    st.title("DemandIQ - from forecast to order")
    st.write("Predicts **what will sell**, warns **what is about to run out**, says **how much to order**, "
             "and explains **why**.")
    dm = T["demand_model_results"]
    dm = dm[dm.Split == "Test"].set_index("Model")
    sm = T["stockout_model_results"]
    sm = sm[sm.Split == "Test"].set_index("Model")
    pc = T["policy_comparison"].set_index("policy")
    a, b, c, d = st.columns(4)
    kpi(a, "Forecast error (MAPE)", f"{dm.loc['Gradient Boosting', 'MAPE (%)']:.1f}%",
        f"{dm.loc['Gradient Boosting', 'MAPE (%)'] - dm.loc['Historical average', 'MAPE (%)']:.1f} pts vs baseline",
        lower_is_better=True)
    kpi(b, "Forecast R²", f"{dm.loc['Gradient Boosting', 'R2']:.3f}")
    kpi(c, "Stockout model ROC-AUC", f"{sm.loc['Gradient Boosting', 'ROC-AUC']:.3f}")
    kpi(d, "Stockout days (policy C vs A)", f"{pc.iloc[2]['stockout_day_rate_%']:.2f}%",
        f"{pc.iloc[2]['stockout_change_%']:.0f}%", lower_is_better=True)
    st.subheader("Demand models on the test window")
    st.dataframe(dm[["MAE", "RMSE", "MAPE (%)", "R2", "Bias (%)"]].style.format("{:,.2f}"), use_container_width=True)
    st.subheader("Ordering policies on the test window")
    show = pc[["stockout_day_rate_%", "fill_rate_%", "avg_stock_days", "emergency_orders", "total_cost", "cost_change_%"]]
    show.columns = ["Stockout days (%)", "Fill rate (%)", "Stock (days)", "Emergency orders", "Total cost (EUR)", "Cost vs A (%)"]
    st.dataframe(show.style.format("{:,.2f}"), use_container_width=True)

elif page == "Store forecast":
    st.title("Store forecast")
    s = st.selectbox("Store", STORES, index=DEFAULT_STORE)
    d = test[test.Store == s].sort_values("Date")
    p50, p10, p90 = predict(d)
    st.caption(f"Segment: **{d.segment_name.iloc[0]}**  -  store type {d.StoreType.iloc[0]}, "
               f"assortment {d.Assortment.iloc[0]}, competitor {d.CompetitionDistance.iloc[0]:,.0f} m away")
    fig, ax = plt.subplots(figsize=(10, 3.6))
    ax.fill_between(d.Date, p10, p90, color=C["teal"], alpha=.2, label="P10-P90 range")
    ax.plot(d.Date, d.Sales, color="#222", marker="o", ms=3, lw=1.2, label="Actual")
    ax.plot(d.Date, p50, color=C["amber"], lw=1.6, label="Forecast")
    ax.legend(ncol=3, frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    import matplotlib.dates as mdates
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    st.pyplot(fig)
    mape = np.mean(np.abs(p50 - d.Sales) / d.Sales) * 100
    inside = np.mean((d.Sales >= p10) & (d.Sales <= p90)) * 100
    a, b = st.columns(2)
    a.metric("MAPE for this store", f"{mape:.1f}%")
    b.metric("Days inside P10-P90 range", f"{inside:.0f}%")

elif page == "Stockout risk & reorder":
    st.title("Stockout risk & reorder list")
    st.write("What DemandIQ recommends on the evening of **31 July 2015** (last day of data) for stores whose "
             "stock so far was managed with the old rule of thumb.")
    rec = T["reorder_recommendations"].merge(seg[["Store", "segment_name"]], on="Store")
    lvl = st.multiselect("Risk level", ["HIGH", "MEDIUM", "LOW"], default=["HIGH", "MEDIUM", "LOW"])
    show = rec[rec.risk_level.isin(lvl)].sort_values("stockout_risk", ascending=False)
    show = show[["Store", "segment_name", "risk_level", "stockout_risk", "stock_on_hand", "in_transit",
                 "forecast_next_days", "safety_stock", "recommended_order"]]
    show.columns = ["Store", "Segment", "Risk", "P(stockout)", "On hand", "In transit", "Forecast to cover",
                    "Safety stock", "Order now"]
    st.dataframe(show.style.format({"P(stockout)": "{:.0%}", "On hand": "{:,.0f}", "In transit": "{:,.0f}",
                                    "Forecast to cover": "{:,.0f}", "Safety stock": "{:,.0f}", "Order now": "{:,.0f}"}),
                 use_container_width=True, height=360, hide_index=True)
    st.subheader("Order calculator")
    c1, c2, c3 = st.columns(3)
    s = c1.selectbox("Store", STORES, index=DEFAULT_STORE, key="calc")
    days = test[test.Store == s].sort_values("Date")
    start = c2.date_input("Order date", days.Date.iloc[10].date(), min_value=days.Date.min().date(),
                          max_value=days.Date.iloc[-6].date())
    stock = c3.number_input("Stock on hand now", 0, 200000, int(days.Sales.mean() * 1.5), step=500)
    nxt = days[days.Date > pd.Timestamp(start)].head(LEAD_TIME + 3)
    p50, p10, p90 = predict(nxt)
    target, q = order_quantity(p50, p10, p90, stock)
    a, b, c = st.columns(3)
    a.metric("Expected demand to cover", f"{p50.sum():,.0f}")
    b.metric("Order-up-to level (incl. safety stock)", f"{target:,.0f}")
    c.metric("Recommended order", f"{q:,.0f}")
    st.caption("Order-up-to = sum of daily forecasts + 1.645 x combined forecast uncertainty (95% service level).")

elif page == "Why this forecast?":
    st.title("Why did the model predict this?")
    c1, c2 = st.columns(2)
    s = c1.selectbox("Store", STORES, index=DEFAULT_STORE)
    d = test[test.Store == s].sort_values("Date")
    day = c2.selectbox("Day", d.Date.dt.strftime("%a %d %b %Y").tolist())
    row = d[d.Date.dt.strftime("%a %d %b %Y") == day]
    p50, _, _ = predict(row)
    st.metric("Forecast", f"{p50[0]:,.0f}", f"actual {row.Sales.iloc[0]:,.0f}")
    ex = shap.TreeExplainer(M["gbm"])
    e = ex(row[FEATS])
    e.data = np.round(e.data.astype(float), 2)
    e.feature_names = [NICE.get(f, f) for f in FEATS]
    plt.figure()
    shap.plots.waterfall(e[0], max_display=10, show=False)
    fig = plt.gcf()
    fig.set_size_inches(8, 4.4)
    st.pyplot(fig)
    vals = pd.Series(e[0].values, index=e.feature_names).sort_values()
    up = vals[vals > 0].tail(2)
    down = vals[vals < 0].head(2)
    st.info("**In words:** pushed up by " + ", ".join(f"*{k}*" for k in up.index[::-1]) +
            "; pulled down by " + ", ".join(f"*{k}*" for k in down.index) +
            ". (SHAP values are in log-sales units: +0.10 is roughly +10%.)")

elif page == "What-if simulator":
    st.title("What-if simulator")
    st.warning("A what-if result shows what the **model has learned** from history. It is not proof "
               "that changing the input would cause the change in the real world.")
    c1, c2 = st.columns(2)
    s = c1.selectbox("Store", STORES, index=DEFAULT_STORE)
    d = test[test.Store == s].sort_values("Date")
    day = c2.selectbox("Day", d.Date.dt.strftime("%a %d %b %Y").tolist(), index=int(qp.get("day", 7)))
    base = d[d.Date.dt.strftime("%a %d %b %Y") == day].copy()
    sc = base.copy()
    st.subheader("Change the situation")
    a, b, c = st.columns(3)
    promo_default = bool(int(qp["promo"])) if qp.get("promo") in ("0", "1") else bool(base.Promo.iloc[0])
    sc["Promo"] = int(a.toggle("Promotion running", promo_default))
    sc["SchoolHoliday"] = int(b.toggle("School holiday", bool(base.SchoolHoliday.iloc[0])))
    sc["closed_next_day"] = int(c.toggle("Store closed tomorrow (holiday)", bool(base.closed_next_day.iloc[0])))
    a, b = st.columns(2)
    dist = a.slider("Distance to nearest competitor (m)", 20, 30000,
                    int(min(30000, base.CompetitionDistance.iloc[0])), step=10)
    sc["log_competition_distance"] = np.log1p(dist)
    price = b.slider("Price change (%)", -20, 20, 0)
    elasticity = st.slider("Assumed price elasticity (not learned - Rossmann has no price data)",
                           -3.0, -0.5, -1.5, 0.1)
    b50, b10, b90 = predict(base)
    s50, s10, s90 = predict(sc)
    factor = (1 + price / 100) ** elasticity
    s50, s10, s90 = s50 * factor, s10 * factor, s90 * factor
    x, y, z = st.columns(3)
    x.metric("Baseline forecast", f"{b50[0]:,.0f}")
    y.metric("Scenario forecast", f"{s50[0]:,.0f}", f"{(s50[0] / b50[0] - 1) * 100:+.1f}%")
    z.metric("Scenario P10-P90", f"{s10[0]:,.0f} - {s90[0]:,.0f}")
    left, _ = st.columns([1, 1])
    fig, ax = plt.subplots(figsize=(5, 2.6))
    ax.bar(["Baseline", "Scenario"], [b50[0], s50[0]], color=[C["grey"], C["navy"]])
    ax.errorbar([0, 1], [b50[0], s50[0]], yerr=[[b50[0] - b10[0], s50[0] - s10[0]], [b90[0] - b50[0], s90[0] - s50[0]]],
                fmt="none", ecolor="#333", capsize=6)
    ax.spines[["top", "right"]].set_visible(False)
    left.pyplot(fig)
    st.caption("Inputs that the model learned: promotion, holidays, closures, competitor distance. "
               "Price is applied on top with the elasticity you choose.")

elif page == "Store segments":
    st.title("Store segments (K-Means)")
    st.dataframe(T["segment_summary"], use_container_width=True)
    s = seg.copy()
    fig, ax = plt.subplots(figsize=(7, 3.6))
    cols = [C["navy"], C["teal"], C["amber"], C["red"]]
    for g in range(4):
        m = s.segment == g
        ax.scatter(s[m].avg_sales, s[m].promo_lift * 100, s=10, color=cols[g], label=s[m].segment_name.iloc[0])
    ax.set_xlabel("Average daily sales")
    ax.set_ylabel("Promotion uplift (%)")
    ax.legend(fontsize=8, frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    st.pyplot(fig)
