"""
Inventory simulator ("digital twin") shared by steps 4 and 5.

Rossmann tells us how much each store sold every day, but not how much stock
it held. We therefore replay a realistic ordering process over the REAL daily
demand and record what would have happened:

  morning   deliveries arrive (some are late)
  day       customers buy; if the shelf is empty the sale is lost (= stockout)
  evening   on Monday and Thursday the store orders up to a target level S
            (DemandIQ policy C may also place an emergency order on other days)

All stores are simulated together, one day at a time, with NumPy arrays.
"""
import numpy as np
import pandas as pd

from config import (COST_EMERGENCY, COST_HOLDING, COST_LOST_SALE, COST_ORDER, EMERGENCY_LEAD,
                    LEAD_TIME, MANAGER_BUFFER, P_LATE_1, P_LATE_2, RANDOM_STATE, REVIEW_DAYS,
                    RISK_WINDOW, SERVICE_LEVEL_Z, SHELF_CAPACITY_DAYS, TRAIN_END)

PAD = 14
DELAY_MEAN = P_LATE_1 * 1 + P_LATE_2 * 2                       # expected days late (0.25)
DELAY_VAR = P_LATE_1 * 1 + P_LATE_2 * 4 - DELAY_MEAN ** 2      # variance of days late   # extra days after the last date so look-ahead sums never run off the end

RISK_FEATURES = ["stock_days", "cover_ratio", "incoming_3d_days", "forecast_3d_days",
                 "days_to_next_delivery", "delivery_overdue", "promo_days_next_3",
                 "open_days_next_3", "stockouts_last_7", "demand_cv", "forecast_uncertainty",
                 "day_of_week", "segment"]


class Panel:
    """Store x day matrices for one simulation window."""

    def __init__(self, daily, forecasts, segments, start, end):
        dates = pd.date_range(start, pd.Timestamp(end) + pd.Timedelta(days=PAD))
        self.dates = dates
        self.n_real = len(pd.date_range(start, end))
        d = daily[(daily.Date >= start) & (daily.Date <= end)]
        self.stores = np.sort(d.Store.unique())

        def mat(frame, col, fill):
            m = frame.pivot(index="Store", columns="Date", values=col)
            return m.reindex(index=self.stores, columns=dates).fillna(fill).values.astype(float)

        self.open = mat(d, "Open", np.nan)
        # beyond the data: assume Mon-Sat open (only used for look-ahead, never scored)
        future = np.isnan(self.open)
        dow = np.array([x.dayofweek for x in dates])
        self.open[future] = np.broadcast_to(dow < 6, self.open.shape)[future]
        self.demand = mat(d, "Sales", 0.0) * (self.open > 0)
        self.promo = mat(d, "Promo", 0.0)
        self.dow = dow

        # trailing 28-day average of open-day sales, including today (manager's view)
        s = daily[["Store", "Date", "Sales", "Open"]].copy()
        s["v"] = s.Sales.where(s.Open == 1)
        s["avg28"] = s.groupby("Store").v.transform(lambda x: x.rolling(28, min_periods=5).mean())
        s["std28"] = s.groupby("Store").v.transform(lambda x: x.rolling(28, min_periods=5).std())
        s = s[(s.Date >= start) & (s.Date <= end)]
        self.avg28 = mat(s, "avg28", np.nan)
        self.cv28 = mat(s, "std28", np.nan) / self.avg28

        tr = daily[(daily.Open == 1) & (daily.Date <= TRAIN_END)]
        self.store_avg = tr.groupby("Store").Sales.mean().reindex(self.stores).values
        self.avg28 = np.where(np.isnan(self.avg28), self.store_avg[:, None], self.avg28)
        self.cv28 = np.nan_to_num(self.cv28, nan=0.3)
        self.capacity = SHELF_CAPACITY_DAYS * self.store_avg
        seg = segments.set_index("Store").segment.reindex(self.stores).values
        self.segment = seg

        # demand forecasts (P50) and their uncertainty from the P10-P90 range
        f = forecasts[(forecasts.Date >= start) & (forecasts.Date <= end)]
        fallback = self.avg28 * self.open
        self.has_forecast = ~np.isnan(mat(f, "forecast", np.nan))
        self.fc = np.where(self.has_forecast, mat(f, "forecast", 0.0), fallback) * (self.open > 0)
        sig = (mat(f, "p90", np.nan) - mat(f, "p10", np.nan)) / 2.563
        self.sigma = np.where(np.isnan(sig), 0.15 * fallback, sig) * (self.open > 0)

        # supplier delays, drawn once so every policy faces exactly the same luck
        rng = np.random.default_rng(RANDOM_STATE)
        self.delay = rng.choice([0, 1, 2], p=[1 - P_LATE_1 - P_LATE_2, P_LATE_1, P_LATE_2],
                                size=self.open.shape)


def days_to_next_review(dow):
    return min((r - dow) % 7 or 7 for r in REVIEW_DAYS)


def target_level(p, t, horizon, policy):
    """Order-up-to level S for every store, covering days t+1 .. t+horizon."""
    sl = slice(t + 1, t + 1 + horizon)
    if policy == "manager":
        s = MANAGER_BUFFER * p.avg28[:, t] * p.open[:, sl].sum(1)
    else:
        # forecast demand over the horizon, plus cover for a possibly late delivery:
        #   S = sum(F) + E[delay] * F_daily + z * sqrt( sum(sigma^2) + F_daily^2 * Var[delay] )
        f_sum = p.fc[:, sl].sum(1)
        f_day = f_sum / np.maximum(p.open[:, sl].sum(1), 1)
        var = (p.sigma[:, sl] ** 2).sum(1) + f_day ** 2 * DELAY_VAR
        s = f_sum + DELAY_MEAN * f_day + SERVICE_LEVEL_Z * np.sqrt(var)
    return np.minimum(s, p.capacity)


def risk_features(p, t, on_hand, arr_sched, overdue, so_hist):
    w = slice(t + 1, t + 1 + RISK_WINDOW)
    f3 = p.fc[:, w].sum(1)
    inc = arr_sched[:, w].sum(1)
    nxt = np.argmax(arr_sched[:, t + 1:t + 9] > 0, axis=1) + 1
    nxt = np.where(arr_sched[:, t + 1:t + 9].sum(1) > 0, nxt, 9)
    return pd.DataFrame({
        "stock_days": on_hand / p.store_avg,
        "cover_ratio": np.clip((on_hand + inc) / np.maximum(f3, 1), 0, 10),
        "incoming_3d_days": inc / p.store_avg,
        "forecast_3d_days": f3 / p.store_avg,
        "days_to_next_delivery": nxt,
        "delivery_overdue": overdue.astype(int),
        "promo_days_next_3": p.promo[:, w].sum(1),
        "open_days_next_3": p.open[:, w].sum(1),
        "stockouts_last_7": so_hist[:, max(0, t - 6):t + 1].sum(1),
        "demand_cv": p.cv28[:, t],
        "forecast_uncertainty": np.sqrt((p.sigma[:, w] ** 2).sum(1)) / np.maximum(f3, 1),
        "day_of_week": np.full(len(on_hand), p.dow[t] + 1),
        "segment": p.segment,
    })


def simulate(p, policy, measure_from=None, risk_model=None, threshold=0.5,
             record_from=None, initial_days=4.0):
    """
    policy: "manager" | "demandiq" | "demandiq_risk"
    Returns (summary dict, per-day DataFrame of risk features if record_from is set).
    """
    n, T = p.open.shape
    on_hand = initial_days * p.store_avg
    arr_actual = np.zeros((n, T + 8))
    arr_sched = np.zeros((n, T + 8))
    due_cnt = np.zeros(n)
    got_cnt = np.zeros(n)
    sched_cnt = np.zeros((n, T + 8))
    actual_cnt = np.zeros((n, T + 8))
    stockout = np.zeros((n, T))
    lost_m, sold_m, stock_m = (np.zeros((n, T)) for _ in range(3))
    n_orders = np.zeros((n, T))
    n_emerg = np.zeros((n, T))
    rec = []
    t_meas = 0 if measure_from is None else p.dates.get_loc(pd.Timestamp(measure_from))
    t_rec = None if record_from is None else p.dates.get_loc(pd.Timestamp(record_from))

    for t in range(p.n_real):
        # morning: deliveries
        on_hand = on_hand + arr_actual[:, t]
        due_cnt += sched_cnt[:, t]
        got_cnt += actual_cnt[:, t]
        overdue = due_cnt > got_cnt

        # day: sales
        dem = p.demand[:, t]
        sold = np.minimum(on_hand, dem)
        lost = dem - sold
        on_hand = on_hand - sold
        stockout[:, t] = (lost > 0.5) & (p.open[:, t] > 0)
        lost_m[:, t], sold_m[:, t] = lost, sold

        # evening: regular order on review days
        pending = arr_actual[:, t + 1:].sum(1)
        if p.dow[t] in REVIEW_DAYS:
            h = days_to_next_review(p.dow[t]) + LEAD_TIME - 1
            base = "manager" if policy == "manager" else "demandiq"
            S = target_level(p, t, h, base)
            q = np.maximum(0, S - on_hand - pending)
            q[q < 1] = 0
            arrive = t + LEAD_TIME + p.delay[:, t].astype(int)
            idx = np.arange(n)
            np.add.at(arr_actual, (idx, arrive), q)
            arr_sched[:, t + LEAD_TIME] += q
            sched_cnt[:, t + LEAD_TIME] += q > 0
            np.add.at(actual_cnt, (idx, arrive), q > 0)
            n_orders[:, t] = q > 0

        # evening: risk check -> emergency order (policy C, non-review days)
        if (risk_model is not None or t_rec is not None) and t + RISK_WINDOW < p.n_real + PAD:
            feats = risk_features(p, t, on_hand, arr_sched, overdue, stockout)
            if t_rec is not None and t >= t_rec:
                rec.append(feats.assign(Store=p.stores, Date=p.dates[t]))
            if risk_model is not None and p.dow[t] not in REVIEW_DAYS:
                prob = risk_model.predict_proba(feats[RISK_FEATURES])[:, 1]
                w = slice(t + 1, t + 1 + EMERGENCY_LEAD + 1)
                need = p.fc[:, w].sum(1) + SERVICE_LEVEL_Z * np.sqrt((p.sigma[:, w] ** 2).sum(1))
                soon = arr_sched[:, t + 1:t + 1 + EMERGENCY_LEAD + 1].sum(1)
                qe = np.minimum(np.maximum(0, need - on_hand - soon), p.capacity - on_hand)
                qe = np.where((prob >= threshold) & (qe >= 1), qe, 0)
                arr_actual[:, t + EMERGENCY_LEAD] += qe
                arr_sched[:, t + EMERGENCY_LEAD] += qe
                sched_cnt[:, t + EMERGENCY_LEAD] += qe > 0
                actual_cnt[:, t + EMERGENCY_LEAD] += qe > 0
                n_emerg[:, t] = qe > 0

        stock_m[:, t] = on_hand

    m = slice(t_meas, p.n_real)
    open_m = p.open[:, m] > 0
    demand = p.demand[:, m].sum()
    holding = COST_HOLDING * stock_m[:, m].sum()
    lost_cost = COST_LOST_SALE * lost_m[:, m].sum()
    order_cost = COST_ORDER * n_orders[:, m].sum() + COST_EMERGENCY * n_emerg[:, m].sum()
    summary = {
        "policy": policy,
        "stockout_day_rate_%": 100 * stockout[:, m][open_m].mean(),
        "fill_rate_%": 100 * sold_m[:, m].sum() / demand,
        "avg_stock_days": float(np.mean(stock_m[:, m].mean(1) / p.store_avg)),
        "lost_sales_value": lost_m[:, m].sum(),
        "regular_orders": int(n_orders[:, m].sum()),
        "emergency_orders": int(n_emerg[:, m].sum()),
        "cost_lost_sales": lost_cost,
        "cost_holding": holding,
        "cost_ordering": order_cost,
        "total_cost": lost_cost + holding + order_cost,
    }
    detail = {"stockout": stockout, "stock": stock_m, "lost": lost_m, "emergency": n_emerg,
              "arr_sched": arr_sched, "arr_actual": arr_actual, "overdue": overdue}
    records = pd.concat(rec, ignore_index=True) if rec else None
    return summary, records, detail


def add_labels(records, p, detail):
    """Target: will the store run out on any of the next RISK_WINDOW days?"""
    so = detail["stockout"]
    nxt = np.zeros_like(so)
    for k in range(1, RISK_WINDOW + 1):
        nxt[:, :-k] = np.maximum(nxt[:, :-k], so[:, k:])
    lab = pd.DataFrame(nxt[:, :p.n_real], index=p.stores, columns=p.dates[:p.n_real])
    lab = lab.stack().rename("stockout_next_3d").reset_index()
    lab.columns = ["Store", "Date", "stockout_next_3d"]
    return records.merge(lab, on=["Store", "Date"], how="left")
