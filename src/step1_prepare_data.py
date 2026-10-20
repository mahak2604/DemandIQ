"""
STEP 1 - Clean the raw Rossmann data, build features, draw the EDA charts.

Output
  data/processed/daily.parquet     every store x calendar day (incl. closed days)
  data/processed/model_data.parquet  open trading days with all features
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from config import HISTORY_GAP, PALETTE, PROC_DIR, RAW_DIR, TRAIN_END
from utils import save_fig, save_json

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sept", "Oct", "Nov", "Dec"]


def load_raw():
    sales = pd.read_csv(RAW_DIR / "train.csv", parse_dates=["Date"],
                        dtype={"StateHoliday": str})
    stores = pd.read_csv(RAW_DIR / "store.csv")
    return sales, stores


def clean(sales):
    report = {"raw_rows": len(sales), "raw_stores": sales.Store.nunique()}

    # 180 stores were shut for refurbishment for six months in 2014. Their
    # history has a hole, which breaks lag features and the stock simulation,
    # so we keep only stores with a complete 942-day record (one store misses
    # only 1 Jan 2013, which is a closed day anyway).
    days_per_store = sales.groupby("Store").size()
    keep = days_per_store[days_per_store >= 941].index
    sales = sales[sales.Store.isin(keep)].copy()
    report["stores_kept"] = int(len(keep))

    # Re-index to a complete calendar so "7 days ago" really means 7 days ago.
    calendar = pd.MultiIndex.from_product(
        [keep, pd.date_range(sales.Date.min(), sales.Date.max())],
        names=["Store", "Date"])
    sales = sales.set_index(["Store", "Date"]).reindex(calendar).reset_index()
    sales["Open"] = sales["Open"].fillna(0).astype(int)
    sales["Sales"] = sales["Sales"].fillna(0)
    sales["Promo"] = sales["Promo"].fillna(0).astype(int)
    sales["SchoolHoliday"] = sales["SchoolHoliday"].fillna(0).astype(int)
    sales["StateHoliday"] = sales["StateHoliday"].fillna("0").replace({"0.0": "0"})
    sales["DayOfWeek"] = sales["Date"].dt.dayofweek + 1

    # A store that is "open" but sells nothing is a data error, not demand.
    bad = (sales.Open == 1) & (sales.Sales == 0)
    report["open_zero_sales_removed"] = int(bad.sum())
    sales.loc[bad, "Open"] = 0
    report["calendar_rows"] = len(sales)
    report["open_days"] = int(sales.Open.sum())
    return sales.sort_values(["Store", "Date"]).reset_index(drop=True), report


def add_store_info(df, stores):
    st = stores.copy()
    st["CompetitionDistance"] = st["CompetitionDistance"].fillna(st["CompetitionDistance"].median())
    df = df.merge(st, on="Store", how="left")

    # How long has the nearest competitor been open (months, 0 if not yet)?
    since = pd.to_datetime(dict(year=df.CompetitionOpenSinceYear.fillna(1900),
                                month=df.CompetitionOpenSinceMonth.fillna(1), day=1),
                           errors="coerce")
    months = (df.Date - since).dt.days / 30.4
    df["competition_months"] = months.clip(lower=0, upper=120).fillna(120)

    # Is the store's continuing "Promo2" programme running this month?
    started = (df.Promo2 == 1) & (
        (df.Date.dt.isocalendar().year.astype(int) > df.Promo2SinceYear) |
        ((df.Date.dt.isocalendar().year.astype(int) == df.Promo2SinceYear) &
         (df.Date.dt.isocalendar().week.astype(int) >= df.Promo2SinceWeek)))
    month_name = df.Date.dt.month.map(lambda m: MONTHS[m - 1])
    in_interval = [m in str(iv) for m, iv in zip(month_name, df.PromoInterval)]
    df["promo2_active"] = (started & np.array(in_interval)).astype(int)
    return df


def add_features(df):
    g = df.groupby("Store", sort=False)

    # Calendar - known in advance
    df["day_of_week"] = df.Date.dt.dayofweek + 1
    df["day_of_month"] = df.Date.dt.day
    df["month"] = df.Date.dt.month
    df["week_of_year"] = df.Date.dt.isocalendar().week.astype(int)
    df["year"] = df.Date.dt.year
    df["is_state_holiday"] = (df.StateHoliday != "0").astype(int)

    # Closures next to today shift demand (people shop before / after)
    df["closed_prev_day"] = 1 - g.Open.shift(1).fillna(1).astype(int)
    df["closed_next_day"] = 1 - g.Open.shift(-1).fillna(1).astype(int)

    # Sales history - every value is at least HISTORY_GAP (7) days old
    s = df.Sales.where(df.Open == 1)          # closed days are "unknown", not zero
    gs = s.groupby(df.Store, sort=False)
    k = HISTORY_GAP
    df["lag_7"] = gs.shift(k)
    df["lag_14"] = gs.shift(k + 7)
    df["lag_28"] = gs.shift(k + 21)
    shifted = gs.shift(k)
    gsh = shifted.groupby(df.Store, sort=False)
    df["roll_mean_7"] = gsh.transform(lambda x: x.rolling(7, min_periods=3).mean())
    df["roll_mean_28"] = gsh.transform(lambda x: x.rolling(28, min_periods=10).mean())
    df["roll_std_28"] = gsh.transform(lambda x: x.rolling(28, min_periods=10).std())
    df["trend_ratio"] = df.roll_mean_7 / df.roll_mean_28

    # Store profile - computed from the TRAINING window only (no peeking)
    tr = df[(df.Open == 1) & (df.Date <= TRAIN_END)]
    store_avg = tr.groupby("Store").Sales.mean().rename("store_avg_sales")
    dow_avg = tr.groupby(["Store", "day_of_week"]).Sales.mean().rename("store_dow_avg")
    promo_avg = tr.groupby(["Store", "Promo"]).Sales.mean().unstack()
    lift = (promo_avg[1] / promo_avg[0] - 1).rename("store_promo_lift")
    df = df.merge(store_avg, on="Store").merge(lift, on="Store")
    df = df.merge(dow_avg, on=["Store", "day_of_week"], how="left")

    df["log_competition_distance"] = np.log1p(df.CompetitionDistance)
    df["store_type"] = df.StoreType.map({"a": 0, "b": 1, "c": 2, "d": 3})
    df["assortment"] = df.Assortment.map({"a": 0, "b": 1, "c": 2})
    df["state_holiday_type"] = df.StateHoliday.map({"0": 0, "a": 1, "b": 2, "c": 3}).fillna(0)
    return df


def eda_figures(open_days):
    c = PALETTE

    # Fig: chain sales over time
    weekly = open_days.groupby(pd.Grouper(key="Date", freq="W")).Sales.mean()
    fig, ax = plt.subplots(figsize=(9, 3.4))
    ax.plot(weekly.index, weekly.values, color=c["navy"], lw=1.6)
    ax.axvspan(pd.Timestamp("2015-04-01"), pd.Timestamp("2015-05-31"), color=c["amber"], alpha=.12)
    ax.axvspan(pd.Timestamp("2015-06-01"), pd.Timestamp("2015-07-31"), color=c["red"], alpha=.12)
    ax.text(pd.Timestamp("2015-04-05"), weekly.max() * .98, "valid", color=c["amber"], fontsize=9)
    ax.text(pd.Timestamp("2015-06-05"), weekly.max() * .98, "test", color=c["red"], fontsize=9)
    for yr in (2013, 2014):
        x = pd.Timestamp(f"{yr}-12-22")
        ax.annotate("Christmas", (x, weekly.loc[x - pd.Timedelta(days=6):x + pd.Timedelta(days=6)].max()),
                    xytext=(-60, -5), textcoords="offset points", fontsize=8.5, color="#333",
                    arrowprops=dict(arrowstyle="-", color="#999", lw=.8))
    ax.set_ylabel("Avg. sales per store-day")
    ax.set_ylim(weekly.min() * 0.84, weekly.max() * 1.06)
    ax.text(pd.Timestamp("2013-02-01"), weekly.min() * 0.87, "zig-zag = promotions run every second week",
            fontsize=8.5, color="#555", style="italic")
    ax.set_title("Weekly average sales per open store, Jan 2013 - Jul 2015")
    save_fig(fig, "fig01_sales_trend")

    # Fig: weekday x promotion
    t = open_days.groupby(["day_of_week", "Promo"]).Sales.mean().unstack()
    t = t.reindex(range(1, 8))
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    x = np.arange(7)
    ax.bar(x - .2, t[0], .4, label="No promotion", color=c["grey"])
    ax.bar(x + .2, t[1].fillna(0), .4, label="Promotion running", color=c["teal"])
    ax.set_xticks(x, ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
    ax.set_ylabel("Avg. sales per store-day")
    ax.set_title("Promotions lift sales on every weekday they run")
    ax.legend(loc="upper right")
    save_fig(fig, "fig02_weekday_promo")

    # Fig: monthly seasonality + holiday effect
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.2), gridspec_kw={"width_ratios": [2.2, 1]})
    m = open_days[open_days.Date < "2015-01-01"].groupby("month").Sales.mean()
    axes[0].plot(m.index, m.values, marker="o", color=c["navy"])
    axes[0].set_xticks(range(1, 13), [x[:3] for x in MONTHS])
    axes[0].set_title("Monthly seasonality (2013-2014)")
    axes[0].set_ylabel("Avg. sales per store-day")
    wk = open_days[open_days.day_of_week <= 5]      # Mon-Fri only, so the weekday is not a confounder
    sch = wk.groupby("SchoolHoliday").Sales.mean()
    pre = wk.groupby("closed_next_day").Sales.mean()
    vals = [sch[0], sch[1], pre[0], pre[1]]
    axes[1].bar(range(4), vals, color=[c["grey"], c["amber"], c["grey"], c["red"]])
    axes[1].set_xticks(range(4), ["Normal", "School\nholiday", "Normal", "Day before\nholiday"], fontsize=8)
    axes[1].set_ylim(min(vals) * 0.85, max(vals) * 1.04)
    axes[1].set_title("Calendar effects (Mon-Fri)")
    save_fig(fig, "fig03_seasonality_calendar")

    # Fig: how different the stores are
    sa = open_days.groupby(["Store", "StoreType"]).Sales.mean().reset_index()
    fig, ax = plt.subplots(figsize=(6.4, 3.3))
    data = [sa[sa.StoreType == t].Sales.values for t in "abcd"]
    bp = ax.boxplot(data, patch_artist=True, widths=.55, medianprops=dict(color="white", lw=1.6))
    for patch, col in zip(bp["boxes"], [c["navy"], c["amber"], c["teal"], c["grey"]]):
        patch.set_facecolor(col)
    ax.set_xticks(range(1, 5), [f"Type {t}\n(n={len(d)})" for t, d in zip("abcd", data)])
    ax.set_ylabel("Store's average daily sales")
    ax.set_title("Stores differ by a factor of 5+ in size")
    save_fig(fig, "fig04_store_types")


def main():
    print("STEP 1  data preparation")
    sales, stores = load_raw()
    daily, report = clean(sales)
    daily = add_store_info(daily, stores)
    daily = add_features(daily)

    keep_cols = ["Store", "Date", "Open", "Sales", "Customers", "Promo", "SchoolHoliday",
                 "StateHoliday", "StoreType", "Assortment", "CompetitionDistance", "Promo2"]
    feat_cols = [c for c in daily.columns if c not in keep_cols and c[0].islower()]
    daily = daily[keep_cols + feat_cols]
    daily.to_parquet(PROC_DIR / "daily.parquet", index=False)

    open_days = daily[daily.Open == 1].reset_index(drop=True)
    open_days.to_parquet(PROC_DIR / "model_data.parquet", index=False)

    report.update({
        "model_rows": len(open_days),
        "date_min": str(open_days.Date.min().date()),
        "date_max": str(open_days.Date.max().date()),
        "mean_sales": float(open_days.Sales.mean()),
        "median_sales": float(open_days.Sales.median()),
        "promo_share": float(open_days.Promo.mean()),
        "promo_lift_chain": float(open_days.groupby("Promo").Sales.mean().pipe(lambda s: s[1] / s[0] - 1)),
        "n_features_built": len(feat_cols),
    })
    save_json(report, "dataset_summary")
    eda_figures(open_days)
    for k, v in report.items():
        print(f"    {k:28s} {v}")


if __name__ == "__main__":
    main()
