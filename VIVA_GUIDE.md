# DemandIQ: presentation split and viva prep

## Who presents what (about 18-20 minutes)

| Slides | Presenter | Topic |
|---|---|---|
| 1-5 | Yash Shah (L056) | Problem, objectives, literature (20 books + 15 papers), research gaps |
| 6-9 | Yash Patil (L043) | Dataset, EDA, architecture, K-Means segments |
| 10-12 | Mahak Wadhawan (L074) | Demand models, forecast examples, inventory replay |
| 13-19 | Varshita Vaan (L069) | Stockout risk, ordering policies, SHAP, dashboard demo, conclusion |

Every slide has speaker notes (PowerPoint: View → Notes).

Live demo: `streamlit run app/app.py` → What-if simulator → store 262 → switch the promotion on.

## The project in 30 seconds

We predict daily sales for 935 Rossmann stores (Gradient Boosting, 8.0% error).
Rossmann has no stock data, so we replay a realistic ordering process over the
real sales to get stock levels. A classifier then predicts whether a store will
run out in the next 3 days (ROC-AUC 0.87). The forecast and its uncertainty set
the order quantity, and high risk triggers an emergency order. Compared with a
manager's rule of thumb, stockout days fall by 80% and cost by 63%. SHAP explains
every forecast and every risk score.

## Likely questions, short answers

**Why no deep learning?** The course brief was classical ML, and on tabular retail data, gradient-boosted
trees are the state of the art (the M5 competition was won by LightGBM-based methods). They train in seconds on a laptop and SHAP explains them exactly.

**Why split by date instead of randomly?** It's a time series. A random split would let the model see the
future (for example, the week after a test day), which makes the score look better than it is.

**What is leakage and how did you avoid it?** Leakage is using information that would not be known at prediction time.
Every sales feature is at least 7 days old, store averages come only from the training window, and the risk model
uses forecasts from models trained on earlier data.

**Random Forest vs Gradient Boosting?** Random Forest builds many deep trees independently and averages them (bagging).
Gradient Boosting builds small trees one after another, and each new tree fixes the errors of the previous ones.
Boosting scored best on validation, has almost zero bias, trains faster and supports the quantile loss we need.

**Why is Ridge worse than a simple average?** A linear model can't express interactions such as "promotion × Monday ×
promotion-driven store". Trees can.

**What is MAPE / ROC-AUC / PR-AUC?** MAPE is the average percentage error. ROC-AUC is the chance that a random risky day
is ranked above a random safe day (0.5 = guessing). PR-AUC focuses on the rare positive class; ours is 0.61 against a base rate of 0.16.

**How did you handle class imbalance?** Class weights for Logistic Regression and Random Forest, PR-AUC as a metric,
and a decision threshold chosen on validation instead of 0.5.

**The stock data is simulated. Isn't that cheating?** No public retail dataset publishes stock on hand. We replay a
standard textbook ordering policy over the *real* sales, with late deliveries, and calibrate it to the 8.3%
out-of-stock rate measured in real stores (Gruen et al., 2002). All policies face exactly the same demand and the
same delays, so the comparison is fair. We list this as limitation #1.

**Doesn't DemandIQ just hold more stock?** It holds a little more (1.93 → 2.32 days). The trade-off chart (slide 15)
shows that at *every* stock level DemandIQ has fewer stockouts, because it puts the stock on the right days.

**What is SHAP?** It splits one prediction into "how much each input pushed it up or down" compared with an average
day. The pushes add up exactly to the prediction.

**Why K-Means with k = 4 when the silhouette score is low?** Stores form a continuum, so no k gives sharp clusters.
We picked 4 where the elbow flattens and the groups are easy to name and act on, and we say so openly.

**Is the what-if result causal?** No. It shows what the model learned from history. A causal price effect would need
methods such as double/debiased ML (listed as future work).

**Why is the P10-P90 band only 73%, not 80%?** Quantile models are often slightly over-confident on new data. The
safety-stock formula compensates. Conformal prediction is listed as future work.
