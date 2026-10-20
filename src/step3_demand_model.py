"""
STEP 3 - Demand forecasting (regression).

Models compared, from simplest to strongest:
  1. Naive            - "same day last week"
  2. Historical avg.  - the store's average for this weekday, with / without promo
  3. Ridge regression - linear model on one-hot calendar + numeric features
  4. Random Forest    - bagged decision trees
  5. Gradient Boosting (HistGradientBoostingRegressor) - tuned on validation

The best model is also trained with a quantile loss to give a P10-P90 range,
which the reorder step turns into safety stock.

Output
  outputs/models/demand_*.joblib
  data/processed/forecasts.parquet   honest (out-of-sample) forecasts, Jul 2014 - Jul 2015
"""
import time

import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from config import (MODEL_DIR, PALETTE, PROC_DIR, RANDOM_STATE, RISK_FORECAST_CUTOFF,
                    TAB_DIR, TEST_END, TRAIN_END, VALID_END)
from utils import regression_report, save_fig, save_json, save_table

FEATURES = {
    "Calendar": ["day_of_week", "day_of_month", "month", "week_of_year", "year"],
    "Promotion": ["Promo", "promo2_active"],
    "Holidays": ["SchoolHoliday", "state_holiday_type", "closed_prev_day", "closed_next_day"],
    "Store profile": ["store_type", "assortment", "segment", "Promo2", "log_competition_distance",
                      "competition_months", "store_avg_sales", "store_dow_avg", "store_promo_lift"],
    "Sales history": ["lag_7", "lag_14", "lag_28", "roll_mean_7", "roll_mean_28", "roll_std_28",
                      "trend_ratio"],
}
FEATURE_LIST = [f for group in FEATURES.values() for f in group]
CATEGORICAL = ["day_of_week", "month", "store_type", "assortment", "segment", "state_holiday_type"]
START = "2013-02-15"          # first date with a full 28-day history window

GBM_BASE = dict(loss="squared_error", max_iter=600, learning_rate=0.08, random_state=RANDOM_STATE,
                early_stopping=False)
# Categories (store type, segment, ...) are passed as small integers: trees split them
# fine, and it keeps the SHAP explanations exact.
GRID = [dict(max_leaf_nodes=l, min_samples_leaf=m, l2_regularization=r)
        for l in (31, 63, 127) for m in (40,) for r in (0.0, 1.0)]


def load():
    df = pd.read_parquet(PROC_DIR / "model_data.parquet")
    seg = pd.read_csv(TAB_DIR / "store_segments.csv")[["Store", "segment", "segment_name"]]
    df = df.merge(seg, on="Store")
    df = df[df.Date >= START].reset_index(drop=True)
    df["y_log"] = np.log1p(df.Sales)
    return df


# --------------------------------------------------------------- baselines
def naive(df):
    return df.lag_7.fillna(df.store_dow_avg).values


def historical_average(train, df):
    tab = train.groupby(["Store", "day_of_week", "Promo"]).Sales.mean().rename("hist")
    out = df[["Store", "day_of_week", "Promo"]].join(tab, on=["Store", "day_of_week", "Promo"])
    return out["hist"].fillna(df.store_dow_avg).values


# --------------------------------------------------------------- ML models
def ridge_model():
    numeric = [f for f in FEATURE_LIST if f not in CATEGORICAL]
    pre = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
        ("num", make_pipeline(SimpleImputer(strategy="median"), StandardScaler()), numeric),
    ])
    return make_pipeline(pre, Ridge(alpha=1.0))


def forest_model():
    return RandomForestRegressor(n_estimators=120, min_samples_leaf=5, max_features=0.5,
                                 max_samples=0.3, n_jobs=-1, random_state=RANDOM_STATE)


def gbm_model(**params):
    return HistGradientBoostingRegressor(**{**GBM_BASE, **params})


def fit_predict(model, train, test):
    model.fit(train[FEATURE_LIST], train.y_log)
    return model, np.expm1(model.predict(test[FEATURE_LIST]))


def tune_gbm(train, valid):
    """Small grid search on the validation window; number of trees picked from the loss curve."""
    rows, best = [], None
    for p in GRID:
        t = time.time()
        m = gbm_model(**p).fit(train[FEATURE_LIST], train.y_log)
        for it, pred in enumerate(m.staged_predict(valid[FEATURE_LIST]), start=1):
            if it % 50 == 0:
                r = regression_report(valid.Sales, np.expm1(pred))
                rows.append({**p, "max_iter": it, "valid_RMSPE": r["RMSPE"], "valid_MAPE": r["MAPE (%)"]})
                if best is None or r["RMSPE"] < best[1]:
                    best = ({**p, "max_iter": it}, r["RMSPE"])
        print(f"    grid {p}  {time.time() - t:4.0f}s")
    grid = pd.DataFrame(rows)
    save_table(grid, "gbm_tuning_grid")
    return best[0], grid


def loss_curve(train, valid, params):
    m = gbm_model(**{**params, "max_iter": 600}).fit(train[FEATURE_LIST], train.y_log)
    tr_s = train.sample(60000, random_state=RANDOM_STATE)
    rmse_log = lambda d, p: float(np.sqrt(np.mean((d.y_log.values - p) ** 2)))
    tr_curve = [rmse_log(tr_s, p) for p in m.staged_predict(tr_s[FEATURE_LIST])]
    va_curve = [rmse_log(valid, p) for p in m.staged_predict(valid[FEATURE_LIST])]
    fig, ax = plt.subplots(figsize=(6.4, 3.3))
    it = np.arange(1, len(tr_curve) + 1)
    ax.plot(it, tr_curve, color=PALETTE["navy"], label="Training")
    ax.plot(it, va_curve, color=PALETTE["amber"], label="Validation (Apr-May 2015)")
    ax.axvline(params["max_iter"], color=PALETTE["grey"], ls="--", lw=1)
    ax.text(params["max_iter"] + 8, max(va_curve[20:]) * 0.98, f"chosen: {params['max_iter']} trees",
            fontsize=8.5, color="#444")
    ax.set_ylim(0, max(va_curve[15:]) * 1.6)
    ax.set_xlabel("Number of boosting iterations (trees)")
    ax.set_ylabel("Loss: RMSE of log(sales)")
    ax.set_title("Gradient boosting loss curve")
    ax.legend()
    save_fig(fig, "fig09_loss_curve")


def main():
    print("STEP 3  demand forecasting")
    df = load()
    train = df[df.Date <= TRAIN_END]
    valid = df[(df.Date > TRAIN_END) & (df.Date <= VALID_END)]
    trval = df[df.Date <= VALID_END]
    test = df[(df.Date > VALID_END) & (df.Date <= TEST_END)]
    split_info = {k: {"rows": len(v), "from": str(v.Date.min().date()), "to": str(v.Date.max().date())}
                  for k, v in {"train": train, "valid": valid, "test": test}.items()}
    save_json(split_info, "demand_splits")
    print("   ", {k: v["rows"] for k, v in split_info.items()})

    # ---- 1. tune gradient boosting on validation
    best, grid = tune_gbm(train, valid)
    print("    best GBM params:", best)
    loss_curve(train, valid, best)

    # ---- 2. compare every model: fit on train -> score valid; fit on train+valid -> score test
    results, test_preds, timings = [], {}, {}
    candidates = {
        "Naive (same day last week)": None,
        "Historical average": None,
        "Ridge regression": ridge_model,
        "Random Forest": forest_model,
        "Gradient Boosting": lambda: gbm_model(**best),
    }
    fitted = {}
    for name, make in candidates.items():
        t = time.time()
        if name.startswith("Naive"):
            pv, pt = naive(valid), naive(test)
        elif name == "Historical average":
            pv, pt = historical_average(train, valid), historical_average(trval, test)
        else:
            _, pv = fit_predict(make(), train, valid)
            fitted[name], pt = fit_predict(make(), trval, test)
        timings[name] = time.time() - t
        test_preds[name] = pt
        for split, y, p in (("Validation", valid.Sales, pv), ("Test", test.Sales, pt)):
            results.append({"Model": name, "Split": split, **regression_report(y, p)})
        print(f"    {name:28s} test MAPE {regression_report(test.Sales, pt)['MAPE (%)']:5.2f}%  ({timings[name]:.0f}s)")
    res = pd.DataFrame(results)
    res["Train time (s)"] = res.Model.map(timings).round(1)
    save_table(res.round(4), "demand_model_results")

    # ---- 3. quantile models (P10, P90) for uncertainty / safety stock
    q = {}
    for alpha in (0.1, 0.9):
        qm = HistGradientBoostingRegressor(**{**GBM_BASE, **best, "loss": "quantile", "quantile": alpha})
        qm.fit(trval[FEATURE_LIST], trval.y_log)
        q[alpha] = qm
    p10 = np.expm1(q[0.1].predict(test[FEATURE_LIST]))
    p90 = np.expm1(q[0.9].predict(test[FEATURE_LIST]))
    coverage = float(np.mean((test.Sales >= p10) & (test.Sales <= p90)))
    save_json({"p10_p90_coverage_test": coverage, "target": 0.8,
               "mean_interval_width_pct": float(np.mean((p90 - p10) / test_preds["Gradient Boosting"]) * 100)},
              "quantile_coverage")
    print(f"    P10-P90 interval covers {coverage:.1%} of test days (target 80%)")

    joblib.dump(fitted["Gradient Boosting"], MODEL_DIR / "demand_gbm.joblib")
    joblib.dump(q[0.1], MODEL_DIR / "demand_p10.joblib")
    joblib.dump(q[0.9], MODEL_DIR / "demand_p90.joblib")
    joblib.dump({"features": FEATURE_LIST, "groups": FEATURES, "params": best},
                MODEL_DIR / "demand_meta.joblib")

    # ---- 4. honest forecasts for the stockout model and the reorder simulation
    #     window A: Jul 2014 - Mar 2015 from a model trained up to Jun 2014
    #     window B: Apr - May 2015      from a model trained up to Mar 2015
    #     window C: Jun - Jul 2015      from the final model (trained up to May 2015)
    early = df[df.Date <= RISK_FORECAST_CUTOFF]
    win_a = df[(df.Date > RISK_FORECAST_CUTOFF) & (df.Date <= TRAIN_END)]
    m_a, f_a = fit_predict(gbm_model(**best), early, win_a)
    m_b, f_b = fit_predict(gbm_model(**best), train, valid)
    f_c = test_preds["Gradient Boosting"]
    fc = pd.concat([
        win_a[["Store", "Date", "Sales"]].assign(forecast=f_a),
        valid[["Store", "Date", "Sales"]].assign(forecast=f_b),
        test[["Store", "Date", "Sales"]].assign(forecast=f_c, p10=p10, p90=p90),
    ], ignore_index=True)
    # for windows A and B, a P10-P90 band from the test-window ratio keeps the columns complete
    lo, hi = np.median(p10 / f_c), np.median(p90 / f_c)
    fc["p10"] = fc.p10.fillna(fc.forecast * lo)
    fc["p90"] = fc.p90.fillna(fc.forecast * hi)
    fc.to_parquet(PROC_DIR / "forecasts.parquet", index=False)
    save_json({"window_A_MAPE": regression_report(win_a.Sales, f_a)["MAPE (%)"],
               "window_B_MAPE": regression_report(valid.Sales, f_b)["MAPE (%)"],
               "window_C_MAPE": regression_report(test.Sales, f_c)["MAPE (%)"]}, "forecast_windows")

    figures(res, test, test_preds, p10, p90)


def figures(res, test, preds, p10, p90):
    c = PALETTE
    t = res[res.Split == "Test"].set_index("Model")
    order = list(t.index)
    fig, ax = plt.subplots(1, 2, figsize=(9.2, 3.3))
    colors = [c["grey"], c["grey"], c["teal"], c["teal"], c["navy"]]
    for a, metric in zip(ax, ["MAPE (%)", "R2"]):
        vals = t.loc[order, metric]
        a.barh(range(len(order)), vals, color=colors)
        a.set_yticks(range(len(order)), order if a is ax[0] else [""] * len(order), fontsize=8.5)
        a.invert_yaxis()
        for i, v in enumerate(vals):
            a.text(v, i, f" {v:.2f}" if metric == "R2" else f" {v:.1f}%", va="center", fontsize=8.5)
        a.set_title({"MAPE (%)": "Test MAPE (lower is better)", "R2": "Test R² (higher is better)"}[metric])
        a.set_xlim(0, vals.max() * 1.22)
    save_fig(fig, "fig08_model_comparison")

    # forecast vs actual for three example stores
    best = preds["Gradient Boosting"]
    tt = test.assign(pred=best, p10=p10, p90=p90)
    stores = [262, 1, 85] if 262 in set(tt.Store) else list(tt.Store.unique()[:3])
    fig, axes = plt.subplots(3, 1, figsize=(9, 6.6), sharex=True)
    for a, s in zip(axes, stores):
        d = tt[tt.Store == s]
        a.fill_between(d.Date, d.p10, d.p90, color=c["teal"], alpha=.18, label="P10-P90 range")
        a.plot(d.Date, d.Sales, color="#222", lw=1.2, marker="o", ms=2.4, label="Actual")
        a.plot(d.Date, d.pred, color=c["amber"], lw=1.4, label="DemandIQ forecast")
        promo = d[d.Promo == 1]
        a.scatter(promo.Date, np.full(len(promo), d.p10.min() * 0.92), marker="s", s=6,
                  color=c["red"], label="Promotion day")
        mape = np.mean(np.abs(d.pred - d.Sales) / d.Sales) * 100
        a.set_title(f"Store {s}  (segment: {d.segment_name.iloc[0]})  -  MAPE {mape:.1f}%", fontsize=10)
        a.set_ylabel("Sales")
    axes[0].legend(ncol=4, fontsize=8, loc="upper left", bbox_to_anchor=(0, 1.32))
    import matplotlib.dates as mdates
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    save_fig(fig, "fig10_forecast_examples")

    # error analysis
    tt["ape"] = np.abs(tt.pred - tt.Sales) / tt.Sales * 100
    fig, ax = plt.subplots(1, 3, figsize=(10, 3.2))
    ax[0].hexbin(tt.Sales, tt.pred, gridsize=60, bins="log", cmap="Blues", mincnt=1)
    lim = np.percentile(tt.Sales, 99.7)
    ax[0].plot([0, lim], [0, lim], color=c["red"], lw=1)
    ax[0].set_xlim(0, lim); ax[0].set_ylim(0, lim)
    ax[0].set_xlabel("Actual sales"); ax[0].set_ylabel("Forecast")
    ax[0].set_title("Forecast vs actual (test)")
    seg = tt.groupby("segment_name").ape.mean().sort_values()
    ax[1].barh(range(len(seg)), seg.values, color=c["teal"])
    ax[1].set_yticks(range(len(seg)), [s.replace(" ", "\n", 1) for s in seg.index], fontsize=7.5)
    ax[1].set_title("MAPE by store segment")
    for i, v in enumerate(seg.values):
        ax[1].text(v, i, f" {v:.1f}%", va="center", fontsize=8)
    ax[1].set_xlim(0, seg.max() * 1.3)
    dw = tt.groupby("day_of_week").ape.mean()
    ax[2].bar(dw.index, dw.values, color=c["navy"])
    ax[2].set_xticks(dw.index, ["M", "T", "W", "T", "F", "S", "S"][:len(dw)])
    ax[2].set_title("MAPE by weekday")
    save_fig(fig, "fig11_error_analysis")


if __name__ == "__main__":
    main()
