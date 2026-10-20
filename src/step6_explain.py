"""
STEP 6 - Explain the models with SHAP (SHapley Additive exPlanations).

SHAP splits every single prediction into "how much each input pushed it up or
down" compared with an average day. We show it at two levels:
  global - which inputs matter most across all stores and days
  local  - why ONE store on ONE day got the number it got
"""
import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import shap

from config import MODEL_DIR, PALETTE, PROC_DIR, RANDOM_STATE, TAB_DIR, VALID_END
from utils import save_fig, save_table

NICE = {
    "Promo": "Promotion today", "store_dow_avg": "Store's usual sales for this weekday",
    "store_avg_sales": "Store's average sales", "roll_mean_28": "Avg. sales, 4 weeks ago window",
    "roll_mean_7": "Avg. sales, week before last", "lag_7": "Sales same day last week",
    "lag_14": "Sales same day 2 weeks ago", "lag_28": "Sales same day 4 weeks ago",
    "day_of_week": "Day of week", "day_of_month": "Day of month", "month": "Month",
    "week_of_year": "Week of year", "year": "Year", "promo2_active": "Loyalty promo (Promo2) active",

    "SchoolHoliday": "School holiday", "state_holiday_type": "Public holiday type",
    "closed_prev_day": "Store closed yesterday", "closed_next_day": "Store closed tomorrow",
    "store_type": "Store type", "assortment": "Assortment", "segment": "Store segment",
    "Promo2": "Store in Promo2 programme", "log_competition_distance": "Distance to competitor",
    "competition_months": "Months since competitor opened", "store_promo_lift": "Store's promo sensitivity",
    "roll_std_28": "Sales volatility (4 weeks)", "trend_ratio": "Recent trend (1 wk vs 4 wk)",
    # risk model
    "stock_days": "Stock on hand (days)", "cover_ratio": "Cover ratio (stock+due / forecast)",
    "incoming_3d_days": "Deliveries due in 3 days", "forecast_3d_days": "Forecast demand, next 3 days",
    "days_to_next_delivery": "Days to next delivery", "delivery_overdue": "Delivery overdue",
    "promo_days_next_3": "Promotion days ahead", "open_days_next_3": "Trading days ahead",
    "stockouts_last_7": "Stockouts in last 7 days", "demand_cv": "Demand volatility",
    "forecast_uncertainty": "Forecast uncertainty",
}


def bar(values, names, title, fname, color):
    order = np.argsort(values)[::-1][:12][::-1]
    fig, ax = plt.subplots(figsize=(6.6, 3.9))
    ax.barh(range(len(order)), values[order], color=color)
    ax.set_yticks(range(len(order)), [NICE.get(names[i], names[i]) for i in order], fontsize=8.5)
    for i, v in enumerate(values[order]):
        ax.text(v, i, f" {v:.3f}", va="center", fontsize=7.5)
    ax.set_xlim(0, values[order].max() * 1.18)
    ax.set_xlabel("Mean |SHAP value|  (average size of the push)")
    ax.set_title(title)
    save_fig(fig, fname)


def demand_shap():
    meta = joblib.load(MODEL_DIR / "demand_meta.joblib")
    model = joblib.load(MODEL_DIR / "demand_gbm.joblib")
    feats = meta["features"]
    df = pd.read_parquet(PROC_DIR / "model_data.parquet")
    seg = pd.read_csv(TAB_DIR / "store_segments.csv")[["Store", "segment", "segment_name"]]
    test = df.merge(seg, on="Store")
    test = test[test.Date > VALID_END].reset_index(drop=True)
    sample = test.sample(4000, random_state=RANDOM_STATE)
    ex = shap.TreeExplainer(model)
    sv = ex.shap_values(sample[feats])
    imp = np.abs(sv).mean(0)
    save_table(pd.DataFrame({"feature": feats, "label": [NICE.get(f, f) for f in feats],
                             "mean_abs_shap": imp}).sort_values("mean_abs_shap", ascending=False),
               "shap_importance_demand")
    bar(imp, feats, "What drives the demand forecast (global SHAP)", "fig19_shap_demand_global", PALETTE["navy"])

    # group importance (easier to explain in a viva)
    groups = {g: sum(imp[feats.index(f)] for f in fl) for g, fl in meta["groups"].items()}
    save_table(pd.DataFrame(groups.items(), columns=["group", "mean_abs_shap"]), "shap_groups_demand")

    plt.figure()
    shap.summary_plot(sv, sample[feats].rename(columns=NICE), max_display=12, show=False,
                      plot_size=(7.2, 4.6), color_bar_label="Feature value (low -> high)")
    plt.title("Each dot is one store-day: colour = feature value, position = push on forecast",
              fontsize=9.5, loc="left")
    save_fig(plt.gcf(), "fig20_shap_demand_beeswarm")

    # local explanation: a promotion Monday for store 262
    row = test[(test.Store == 262) & (test.Promo == 1) & (test.day_of_week == 1)].iloc[[0]]
    exp = ex(row[feats])
    exp.data = np.round(exp.data.astype(float), 2)
    exp.feature_names = [NICE.get(f, f) for f in feats]
    pred = np.expm1(model.predict(row[feats]))[0]
    with plt.rc_context({"font.size": 12}):
        plt.figure()
        shap.plots.waterfall(exp[0], max_display=10, show=False)
        fig = plt.gcf()
        fig.set_size_inches(8.2, 5.0)
        plt.title(f"Store 262, {row.Date.iloc[0]:%a %d %b %Y}: forecast {pred:,.0f}, actual {row.Sales.iloc[0]:,.0f}",
                  fontsize=12, loc="left")
        save_fig(fig, "fig21_shap_demand_local")

    # promotion effect is not the same everywhere (ICE-style what-if: promo on vs off, per store-day)
    on, off = sample.copy(), sample.copy()
    on["Promo"], off["Promo"] = 1, 0
    lift = np.exp(model.predict(on[feats]) - model.predict(off[feats])) - 1
    d = sample.assign(lift=lift)
    t = d.groupby("segment_name").lift.agg(["mean", lambda x: x.quantile(.1), lambda x: x.quantile(.9)])
    t.columns = ["mean", "p10", "p90"]
    t = t.sort_values("mean")
    fig, ax = plt.subplots(figsize=(6.4, 2.8))
    ax.barh(range(len(t)), t["mean"] * 100, color=PALETTE["teal"])
    ax.errorbar(t["mean"] * 100, range(len(t)), xerr=[(t["mean"] - t.p10) * 100, (t.p90 - t["mean"]) * 100],
                fmt="none", ecolor="#555", capsize=3, lw=1)
    ax.set_yticks(range(len(t)), t.index, fontsize=8.5)
    for i, v in enumerate(t["mean"] * 100):
        ax.text(1, i + 0.28, f"+{v:.0f}%", va="center", fontsize=8.5, color="white", fontweight="bold")
    ax.set_xlabel("Forecast uplift when a promotion is switched on (%, bar = mean, whisker = P10-P90)")
    ax.set_title("The same promotion lifts different store segments differently")
    save_fig(fig, "fig22_promo_effect_by_segment")
    save_table(t.reset_index(), "promo_uplift_by_segment")
    save_table(pd.DataFrame({"additivity_max_error": [float(np.abs(sv.sum(1) + ex.expected_value
                                                               - model.predict(sample[feats])).max())]}),
               "shap_additivity_check")


def risk_shap():
    bundle = joblib.load(MODEL_DIR / "risk_model.joblib")
    model, feats = bundle["model"], bundle["features"]
    data = pd.read_parquet(PROC_DIR / "risk_data.parquet")
    test = data[data.Date > VALID_END]
    sample = test.sample(4000, random_state=RANDOM_STATE)
    ex = shap.TreeExplainer(model)
    sv = ex.shap_values(sample[feats])
    if isinstance(sv, list):
        sv = sv[1]
    imp = np.abs(sv).mean(0)
    save_table(pd.DataFrame({"feature": feats, "label": [NICE.get(f, f) for f in feats],
                             "mean_abs_shap": imp}).sort_values("mean_abs_shap", ascending=False),
               "shap_importance_stockout")
    plt.figure()
    shap.summary_plot(sv, sample[feats].rename(columns=NICE), max_display=10, show=False,
                      plot_size=(7.2, 4.2), color_bar_label="Feature value (low -> high)")
    plt.title("What drives stockout risk (SHAP, log-odds)", fontsize=10, loc="left")
    save_fig(plt.gcf(), "fig23_shap_risk_beeswarm")


def main():
    print("STEP 6  explainability (SHAP)")
    demand_shap()
    risk_shap()


if __name__ == "__main__":
    main()
