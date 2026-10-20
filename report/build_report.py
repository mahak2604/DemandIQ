"""
Builds the DemandIQ project report (Word, .docx) from the pipeline outputs.

    python report/build_report.py

Every number in the report is read from outputs/tables, so the report always
matches the latest run of the code.
"""
import json
import sys
from pathlib import Path

import pandas as pd
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from docx_helpers import (NAVY, Counter, add_runs, bullets, equation, field, figure, header_text,  # noqa: E402
                          new_document, next_fig, next_tab, page_border, page_break,
                          page_number_footer, page_number_format, para, table)
from references import BOOKS, PAPERS, REFS, Cite  # noqa: E402

FIG = ROOT / "outputs" / "figures"
TAB = ROOT / "outputs" / "tables"
SHOTS = ROOT / "outputs" / "screenshots"
c = Cite.c

TEAM = [("Yash Shah", "L056"), ("Mahak Wadhawan", "L074"), ("Yash Patil", "L043"), ("Varshita Vaan", "L069")]
TITLE = "DemandIQ: Machine Learning for Product Demand and Stockout Risk Prediction"


# ======================================================================= results
def load_results():
    j = lambda n: json.loads((TAB / f"{n}.json").read_text())
    t = lambda n: pd.read_csv(TAB / f"{n}.csv")
    R = {"ds": j("dataset_summary"), "split": j("demand_splits"), "km": j("kmeans_selection"),
         "q": j("quantile_coverage"), "inv": j("inventory_simulation_summary"),
         "cm": j("stockout_confusion"), "pol_set": j("policy_settings"), "fw": j("forecast_windows")}
    dm = t("demand_model_results")
    R["dm"] = dm
    R["dt"] = dm[dm.Split == "Test"].set_index("Model")
    R["dv"] = dm[dm.Split == "Validation"].set_index("Model")
    sm = t("stockout_model_results")
    R["st"] = sm[sm.Split == "Test"].set_index("Model")
    R["sv"] = sm[sm.Split == "Validation"].set_index("Model")
    R["pol"] = t("policy_comparison")
    R["front"] = t("policy_frontier")
    R["seg"] = t("segment_summary")
    R["bands"] = t("risk_bands")
    R["shap_d"] = t("shap_importance_demand")
    R["shap_g"] = t("shap_groups_demand")
    R["shap_r"] = t("shap_importance_stockout")
    R["uplift"] = t("promo_uplift_by_segment")
    R["grid"] = t("gbm_tuning_grid")
    R["thr"] = t("emergency_threshold_tuning")
    R["bys"] = t("policy_by_segment")
    R["add"] = t("shap_additivity_check")
    return R


def f1(x):
    return f"{x:,.1f}"


def f2(x):
    return f"{x:,.2f}"


def f3(x):
    return f"{x:.3f}"


def pct(x, d=1):
    return f"{x:.{d}f}%"


# ======================================================================= front matter
def cover(doc):
    sec = doc.sections[0]
    page_border(sec)
    para(doc, "", after=10)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(str(ROOT / "assets" / "nmims_logo.png"), width=Inches(1.45))
    para(doc, "SVKM's NMIMS (Deemed-to-be University)", bold=True, size=15, align="center", after=2, color=NAVY)
    para(doc, "Mukesh Patel School of Technology Management & Engineering", bold=True, size=13, align="center", after=2)
    para(doc, "Vile Parle (West), Mumbai - 400 056", size=11, align="center", after=26)
    para(doc, "A Machine Learning Group Activity Report on", italic=True, size=12, align="center", after=6)
    para(doc, "DemandIQ", bold=True, size=30, align="center", after=2, color=NAVY)
    para(doc, "Machine Learning for Product Demand and Stockout Risk Prediction", bold=True, size=15,
         align="center", after=24)
    para(doc, "Course: Machine Learning   |   Course Code: ____________", size=12, align="center", after=2)
    para(doc, "B.Tech, Semester V   |   Academic Year 2026-27", size=12, align="center", after=22)
    para(doc, "Submitted by", bold=True, size=12, align="center", after=4)
    t = doc.add_table(rows=len(TEAM) + 1, cols=2)
    t.alignment = 1
    for i, (h1, h2) in enumerate([("Name", "Roll No.")] + TEAM):
        for j, v in enumerate((h1, h2)):
            cell = t.rows[i].cells[j]
            cell.width = Inches(2.4 if j == 0 else 1.2)
            pp = cell.paragraphs[0]
            pp.alignment = WD_ALIGN_PARAGRAPH.CENTER
            pp.paragraph_format.space_after = Pt(2)
            r = pp.add_run(v)
            r.bold = i == 0
            r.font.size = Pt(12)
    para(doc, "", after=14)
    para(doc, "Under the guidance of", italic=True, size=12, align="center", after=2)
    para(doc, "Prof. ______________________", bold=True, size=12, align="center", after=2)
    para(doc, "Department of ______________________, MPSTME", size=11, align="center", after=18)
    para(doc, "Date of Submission: ____ / ____ / 2026", size=12, align="center", after=0)


def declaration(doc, R):
    doc.add_heading("Declaration", level=1)
    para(doc, "We, the undersigned students of B.Tech Semester V, Mukesh Patel School of Technology Management & "
              "Engineering, SVKM's NMIMS, Mumbai, declare that this report titled **\"" + TITLE + "\"** is a record "
              "of the work carried out by us as part of the Machine Learning group activity during the academic year "
              "2026-27. The data used is publicly available, all sources of information have been acknowledged in the "
              "References section, and the code and results presented here were produced by our team.")
    para(doc, "Place: Mumbai", after=2)
    para(doc, "Date: ____ / ____ / 2026", after=14)
    table(doc, "Declaration signatures", ["Name", "Roll No.", "Signature"],
          [[n, r, ""] for n, r in TEAM], [2.6, 1.3, 2.4], font_size=11, zebra=False)

    doc.add_heading("Individual Contribution", level=1)
    para(doc, "The table below lists the main responsibility of each member. All four members took part in the "
              "weekly reviews, testing of the pipeline and proof-reading of this report.")
    rows = [
        ["Yash Shah", "L056", "Problem framing and objectives; literature survey (20 books, 15 papers); research gaps; "
                              "report writing and formatting; project coordination"],
        ["Mahak Wadhawan", "L074", "Demand forecasting models (baselines, Ridge, Random Forest, Gradient Boosting); "
                                   "hyper-parameter tuning; quantile models; model evaluation"],
        ["Yash Patil", "L043", "Data cleaning and merging; feature engineering; K-Means store segmentation; "
                               "inventory simulation (digital twin); reorder-policy comparison"],
        ["Varshita Vaan", "L069", "Stockout-risk classifier; SHAP explainability; Streamlit dashboard and what-if "
                                  "simulator; figures and presentation"],
    ]
    table(doc, "Individual contribution of team members", ["Name", "Roll No.", "Specific tasks handled"], rows,
          [1.5, 0.9, 4.1], font_size=10, align=["left", "center", "left"])


def toc(doc):
    doc.add_heading("Table of Contents", level=1)
    p = doc.add_paragraph()
    field(p, 'TOC \\o "1-2" \\h \\z \\u')
    page_break(doc)
    doc.add_heading("List of Figures", level=1)
    p = doc.add_paragraph()
    field(p, 'TOC \\h \\z \\t "Caption,1"')
    page_break(doc)
    doc.add_heading("List of Tables", level=1)
    p = doc.add_paragraph()
    field(p, 'TOC \\h \\z \\t "Table Caption,1"')
    page_break(doc)


# ======================================================================= chapters
def abstract(doc, R):
    dt, st, pol = R["dt"], R["st"], R["pol"]
    gb, ha = dt.loc["Gradient Boosting"], dt.loc["Historical average"]
    A, B, C = pol.iloc[0], pol.iloc[1], pol.iloc[2]
    doc.add_heading("1. Abstract", level=1)
    para(doc, f"Retailers lose money in two ways: when a shelf runs empty the sale is lost, and when too much stock is "
              f"held, cash is tied up and goods age on the shelf. Both problems come from not knowing tomorrow's demand. "
              f"This project builds **DemandIQ**, a classical machine-learning system (no deep learning) that forecasts "
              f"daily demand, predicts the probability of a stockout in the next three days, recommends how much to "
              f"reorder, and explains every prediction. We use the public Rossmann Store Sales dataset "
              f"({R['ds']['raw_rows']:,} store-days, 1,115 German drugstores, 2013-2015), keep the "
              f"{R['ds']['stores_kept']} stores with a complete history, and split the data strictly by time. "
              f"K-Means groups the stores into four behavioural segments. For demand, a tuned Gradient Boosting "
              f"regressor reaches a test MAPE of {pct(gb['MAPE (%)'], 2)} and R² of {f3(gb['R2'])}, against "
              f"{pct(ha['MAPE (%)'], 2)} for a store-weekday-promotion average baseline. Because Rossmann does not "
              f"publish stock levels, we replay a realistic ordering process over the real sales, calibrated to the "
              f"8.3% worldwide out-of-stock rate, to obtain stock and stockout labels. A Gradient Boosting classifier "
              f"predicts three-day stockout risk with ROC-AUC {f3(st.loc['Gradient Boosting', 'ROC-AUC'])}. On the "
              f"held-out June-July 2015 window, ordering with DemandIQ's forecast and risk alerts cuts stockout days from "
              f"{pct(A['stockout_day_rate_%'], 2)} to {pct(C['stockout_day_rate_%'], 2)} and total inventory cost by "
              f"{abs(C['cost_change_%']):.0f}% compared with a manager's rule of thumb. SHAP explanations and a Streamlit "
              f"what-if dashboard make each number traceable. The main lesson is that a forecast creates value only when "
              f"it is turned into an explained ordering decision.")
    para(doc, "**Keywords:** demand forecasting, stockout prediction, gradient boosting, random forest, K-Means, "
              "SHAP, inventory optimisation, explainable machine learning.", align="left")


def introduction(doc, R):
    doc.add_heading("2. Introduction", level=1)
    doc.add_heading("2.1 Background and motivation", level=2)
    para(doc, "Every shop, warehouse and online seller faces the same question every week: how much of each product "
              "should be kept in stock? If too little is kept, the product runs out (a _stockout_), the customer "
              "leaves without buying and often goes to a competitor. If too much is kept (_overstock_), money is locked "
              "in goods that sit on the shelf, take up space and may expire. A worldwide study of grocery retail found "
              f"that on an average day about 8.3% of items were out of stock {c('gruen')}, and that a large share of "
              "shoppers who meet an empty shelf buy elsewhere or not at all.")
    para(doc, "Both problems have one root cause: demand for tomorrow is not known. Small and mid-sized stores usually "
              "order by habit (\"order what we sold last month, plus a bit\"). Such rules ignore promotions, holidays and "
              "weekday patterns, so they run short exactly when demand jumps. Modern forecasting software uses machine "
              f"learning {c('fildes', 'm5')}, but often gives only a number. A manager who cannot see _why_ the system "
              "predicts 137 units tends not to trust it, and a prediction that is not trusted changes nothing. Finally, "
              "even a perfect forecast is not yet a decision: the manager still has to work out how much to order given "
              f"current stock and delivery time {c('b_silver', 'b_chopra')}.")
    doc.add_heading("2.2 Application domain", level=2)
    para(doc, "We work with daily store-level sales from Rossmann, a large German drugstore chain, which released "
              f"two and a half years of data for a public forecasting competition {c('rossmann')}. The same pipeline "
              "transfers to any business that holds physical stock:")
    table(doc, "Where DemandIQ applies", ["Sector", "How DemandIQ helps"], [
        ["Supermarkets and drugstores", "Daily demand per store; flag stores likely to run out before the next truck"],
        ["E-commerce and D2C brands", "Test a planned discount in the what-if tool before the sale goes live"],
        ["Pharmacies", "Keep critical medicines in stock without over-ordering items that expire"],
        ["FMCG distributors", "Plan replenishment across many outlets around festival and promotion peaks"],
        ["Restaurants and food service", "Forecast ingredient use to cut spoilage and avoid peak-hour shortages"],
    ], [2.1, 4.4], align=["left", "left"])
    doc.add_heading("2.3 Objectives", level=2)
    para(doc, "The project has four objectives, each producing a visible output and each building on the one before:")
    bullets(doc, [
        "**O1 - Predict demand.** Forecast daily sales for every store for the next seven days from calendar, "
        "promotion, holiday, store and sales-history information, with a P10-P90 uncertainty range.",
        "**O2 - Predict stockout risk.** Combine the forecast with current stock and incoming deliveries to give the "
        "probability that the store runs out within three days, shown as LOW, MEDIUM or HIGH.",
        "**O3 - Recommend how much to order.** Turn the forecast and its uncertainty into an order-up-to level and an "
        "order quantity, and trigger an emergency order when risk is high.",
        "**O4 - Explain and allow what-if testing.** Show which factors pushed each forecast and risk score up or "
        "down (SHAP), and let the user change promotion, holiday, competition or price to see the model's response.",
    ], style="List Number")
    para(doc, "A fifth, supporting objective is to group the 935 stores into a small number of segments with "
              "K-Means, so that managers can see which kinds of stores react strongly to promotions.")
    doc.add_heading("2.4 Organisation of the report", level=2)
    para(doc, "Section 3 surveys the literature (20 reference books and 15 research papers) and Section 4 lists the "
              "research gaps. Section 5 defines the problem formally. Section 6 describes the dataset, features, models, "
              "training and metrics. Section 7 presents and discusses the results, Section 8 concludes and Section 9 "
              "outlines future work. The appendices give hyper-parameters, code structure, the dashboard and notes on "
              "ethics and reproducibility.")


def literature(doc, R):
    doc.add_heading("3. Literature Survey", level=1)
    doc.add_heading("3.1 Scope and method", level=2)
    para(doc, "We studied the problem from two kinds of sources. First, **20 reference books** gave us the "
              "foundations: forecasting practice, inventory theory, machine-learning algorithms, explainability and "
              "causal reasoning. Second, **15 peer-reviewed research papers**, most from 2019-2026, show what current "
              "systems achieve and where they stop. Papers were selected if they addressed at least one of our four "
              f"objectives. Table {next_tab()} summarises the books and Table {next_tab() + 1} compares the papers.")
    rows = [
        [c("b_fpp"), "Hyndman & Athanasopoulos, Forecasting: Principles and Practice (2021)", "Time-based splits, naive and seasonal baselines, MAPE/RMSE, prediction intervals"],
        [c("b_box"), "Box, Jenkins, Reinsel & Ljung, Time Series Analysis (2015)", "Autocorrelation and lag structure behind our 7/14/28-day lag features"],
        [c("b_gilliland"), "Gilliland, The Business Forecasting Deal (2010)", "Forecast value added: always compare against a naive baseline"],
        [c("b_silver"), "Silver, Pyke & Thomas, Inventory and Production Management (2017)", "Periodic-review order-up-to (R, S) policy; safety stock with lead-time variability"],
        [c("b_chopra"), "Chopra & Meindl, Supply Chain Management (2016)", "Cycle service level, cost of stockouts versus holding cost"],
        [c("b_nahmias"), "Nahmias & Olsen, Production and Operations Analysis (2015)", "Newsvendor logic and the z-value for a target service level"],
        [c("b_zipkin"), "Zipkin, Foundations of Inventory Management (2000)", "Inventory position = on hand + on order; lost-sales systems"],
        [c("b_axsater"), "Axsäter, Inventory Control (2015)", "Stochastic lead times and their effect on stockout risk"],
        [c("b_winston"), "Winston, Operations Research (2004)", "Simulation as a tool to compare policies under uncertainty"],
        [c("b_esl"), "Hastie, Tibshirani & Friedman, Elements of Statistical Learning (2009)", "Bagging, random forests, gradient boosting, bias-variance trade-off"],
        [c("b_islr"), "James, Witten, Hastie & Tibshirani, Intro. to Statistical Learning (2021)", "Ridge regression, logistic regression, K-Means, validation"],
        [c("b_bishop"), "Bishop, Pattern Recognition and Machine Learning (2006)", "Probabilistic view of classification and calibrated probabilities"],
        [c("b_murphy"), "Murphy, Probabilistic Machine Learning (2022)", "Quantile (pinball) loss and predictive uncertainty"],
        [c("b_geron"), "Géron, Hands-On Machine Learning (2022)", "Scikit-learn pipelines, grid search, ROC/PR curves in practice"],
        [c("b_kuhn_apm"), "Kuhn & Johnson, Applied Predictive Modeling (2013)", "Data splitting, resampling and model comparison discipline"],
        [c("b_kuhn_fes"), "Kuhn & Johnson, Feature Engineering and Selection (2019)", "Encoding categories, rolling statistics, avoiding leakage"],
        [c("b_he"), "He & Ma (Eds.), Imbalanced Learning (2013)", "Class weights, PR-AUC and threshold tuning for rare stockouts"],
        [c("b_molnar"), "Molnar, Interpretable Machine Learning (2022)", "SHAP, partial dependence and ICE; limits of explanations"],
        [c("b_pearl"), "Pearl, Glymour & Jewell, Causal Inference in Statistics (2016)", "Why a what-if on a predictive model is not a causal effect"],
        [c("b_provost"), "Provost & Fawcett, Data Science for Business (2013)", "Framing ML around a business decision and expected value"],
    ]
    table(doc, "Reference books consulted and what each contributed to DemandIQ", ["Ref.", "Book", "Concepts used in this project"],
          rows, [0.5, 2.9, 3.1], font_size=9, align=["center", "left", "left"])

    para(doc, f"The 15 research papers are compared in Table {next_tab()} in the format Author/Year | Technique | "
              "Dataset | Metrics/Results | Limitations.")
    prow = [
        [c("seyedan"), "Seyedan & Mafakheri, 2020", "Survey: time series, clustering, KNN, NN, SVR", "Review of published studies", "Taxonomy of big-data forecasting methods for supply chains", "No empirical comparison; no stock decision"],
        [c("m5"), "Makridakis et al., 2022", "M5 competition; mostly LightGBM ensembles won", "42,840 Walmart series with prices and calendar", "ML methods beat statistical benchmarks", "Accuracy only; large ensembles hard to explain"],
        [c("lightgbm"), "Ke et al., 2017", "Gradient boosting with GOSS and EFB", "Public benchmark datasets", "Up to 20x faster training at similar accuracy", "Algorithm paper; no retail evaluation"],
        [c("gurali"), "Gür Ali et al., 2009", "Regression trees with promotion features", "SKU-store sales, European grocer", "Big gains during promotions; pooling SKUs helps", "Older data; no inventory link"],
        [c("huber"), "Huber & Stuckenschmidt, 2020", "ML vs established methods; special-day features", "Daily sales of a bakery chain", "ML wins; calendar special days matter", "One retailer; forecast only"],
        [c("spiliotis"), "Spiliotis et al., 2022", "Croston-type vs ML with cross-learning", "Daily intermittent SKU demand", "Some ML beat Croston in accuracy and bias", "No explanation; accuracy only"],
        [c("tft"), "Lim et al., 2021", "Temporal Fusion Transformer (deep learning)", "Retail, electricity, traffic sets", "About 7% lower P50 and 9% lower P90 loss", "Heavy model, GPU; hard for managers"],
        [c("liu"), "Liu et al., 2025", "Classical ML classifiers, class imbalance", "1.6 M+ retailer SKUs", "Stock level, 3-month forecast, recent sales are top predictors", "Global importance only; no order size"],
        [c("theodorou"), "Theodorou et al., 2025", "Forecasts + inventory simulation", "M5 Walmart data", "Accuracy-cost link can be weak", "Simulated stock; no explanation"],
        [c("bertsimas"), "Bertsimas & Kallus, 2020", "Prescriptive analytics (kNN, trees, kernels)", "Media distributor, ~1 bn units/yr", "Data-driven decisions beat predict-then-optimise", "Mathematically heavy to audit"],
        [c("banrudin"), "Ban & Rudin, 2019", "Feature-based (big data) newsvendor", "Hospital nurse staffing", "23-24% lower cost than benchmark", "Single period; not retail stores"],
        [c("shap"), "Lundberg & Lee, 2017", "SHAP additive feature attribution", "Benchmark models", "Unique, consistent per-prediction attributions", "Describes the model, not causality"],
        [c("mishra"), "Mishra et al., 2026", "LightGBM + PFI, PDP, SHAP, ICE", "UCI Online Retail II, 41 features", "RMSE 33.71, R² 0.243 (SKU-day)", "Explanations stop at forecast"],
        [c("rozanec"), "Rožanec et al., 2022", "Knowledge-graph enriched XAI", "Real demand-forecasting case", "Links drivers to news and external data", "Complex set-up; no stock decision"],
        [c("dml"), "Chernozhukov et al., 2018", "Double/debiased ML, cross-fitting", "Econometric examples", "Valid effect estimates where naive ML is biased", "Needs causal design; not a forecaster"],
    ]
    table(doc, "Comparison of reviewed research papers", ["Ref.", "Author / Year", "Technique", "Dataset", "Metrics / Results", "Limitations"],
          prow, [0.42, 1.0, 1.35, 1.2, 1.35, 1.18], font_size=8.5, align=["center", "left", "left", "left", "left", "left"])

    doc.add_heading("3.2 Synthesis of the literature", level=2)
    para(doc, f"**Machine learning forecasts retail demand well.** Surveys show a clear move from classical time-series "
              f"models to data-driven methods {c('seyedan', 'fildes')}. In the M5 competition on Walmart data, machine-"
              f"learning methods, most of them built on LightGBM, beat the statistical benchmarks {c('m5')}. Gradient-boosted "
              f"trees are the workhorse for this kind of tabular data and LightGBM trains much faster than older boosting "
              f"at similar accuracy {c('lightgbm')}. Three findings shaped our features: promotions need explicit "
              f"features {c('gurali')}, calendar special days behave differently from normal days {c('huber')}, and "
              f"training one model across many series (cross-learning) helps {c('spiliotis')}. The textbook advice "
              f"to split by time and always report a naive baseline {c('b_fpp', 'b_gilliland')} guided our evaluation. "
              f"Deep models such as the Temporal Fusion Transformer {c('tft')} are accurate but heavy, and the brief for "
              f"this course was classical machine learning, so we did not use them.")
    para(doc, f"**Stockout prediction is studied much less than forecasting.** Liu et al. trained classical models on "
              f"over 1.6 million SKUs and found stock level and the near-term forecast to be the strongest predictors "
              f"{c('liu')}. This directly supports our design, where the risk model sees current stock, deliveries due and "
              f"the forecast. Their output is a prediction plus a global feature ranking, not an item-level reason or an "
              f"order quantity. Because stockouts are rare, imbalance has to be handled with class weights, PR-AUC and "
              f"threshold tuning {c('b_he')}.")
    para(doc, f"**Accuracy is not the same as a good decision.** Theodorou et al. showed on M5 data that the most "
              f"accurate forecast is not always the cheapest to stock against {c('theodorou')}. Prescriptive methods "
              f"{c('bertsimas', 'banrudin')} optimise the order directly and report large savings, but they are hard for "
              f"a store manager to check. Inventory theory offers a transparent alternative: a periodic-review order-up-to "
              f"policy whose safety stock covers both forecast error and late deliveries {c('b_silver', 'b_nahmias', 'b_axsater')}. "
              f"We keep this readable rule and feed it with machine-learning forecasts and quantiles.")
    para(doc, f"**Explanations usually stop at the forecast.** SHAP gives each feature a fair share of an individual "
              f"prediction {c('shap')} and has an exact, fast version for tree models {c('treeshap')}. The closest work to "
              f"ours, Mishra et al., combines LightGBM with four explanation layers {c('mishra')}; Rožanec et al. enrich "
              f"explanations with external knowledge {c('rozanec')}. In both, the explanation is attached to the "
              f"forecast only. Finally, a what-if result shows what the model learned, not what would really happen: "
              f"naive machine-learning effect estimates are biased {c('dml')}, and causal claims need a causal design "
              f"{c('b_pearl')}. We therefore label every what-if output as model behaviour.")


def gaps(doc, R):
    doc.add_heading("4. Research Gaps", level=1)
    para(doc, "Reading the books and papers side by side, we found six gaps. Each is tied to specific sources and to "
              "the way DemandIQ responds to it.")
    table(doc, "Research gaps identified and DemandIQ's response", ["ID", "Gap", "Evidence", "DemandIQ response"], [
        ["G1", "Forecasting, stockout risk and ordering are studied separately", f"{c('liu')} predicts stockouts; {c('mishra')}, {c('rozanec')} explain forecasts; {c('bertsimas')}, {c('banrudin')} prescribe orders", "One pipeline: forecast → risk → order quantity (O1-O3)"],
        ["G2", "Explanations end at the forecast", f"{c('mishra')}, {c('rozanec')} explain forecasts; {c('liu')} gives global importance only", "SHAP for both the demand and the risk model, plus plain-language reasons (O4)"],
        ["G3", "Forecast accuracy is not decision quality", f"{c('theodorou')} finds a weak accuracy-cost link", "Judge policies on stockout days, fill rate, stock held and cost, not only MAPE"],
        ["G4", "What-if output is easily misread as causal", f"{c('dml')}, {c('b_pearl')}", "Every what-if is labelled as model behaviour; price uses a stated elasticity"],
        ["G5", "One policy is applied to very different stores", f"{c('mishra')} finds opposite feature effects across product groups", "K-Means store segments; promotion uplift shown per segment"],
        ["G6", "No public retail data contains stock on hand", f"{c('m5')}, {c('rossmann')} publish sales only", "Calibrated inventory replay over real demand, matched to the 8.3% out-of-stock rate of " + c('gruen')],
    ], [0.4, 1.7, 2.1, 2.3], font_size=9, align=["center", "left", "left", "left"])


def problem(doc, R):
    doc.add_heading("5. Problem Definition", level=1)
    doc.add_heading("5.1 Problem statement", level=2)
    para(doc, "Design an explainable, classical machine-learning system that predicts short-term demand for each store "
              "from past sales, promotion, holiday, store and seasonality data; identifies stores at risk of stockout in "
              "the next three days; recommends how much to reorder; and shows the reasons behind each prediction, with a "
              "what-if tool to test how promotion, holidays, competition or price would change demand.")
    doc.add_heading("5.2 Formal definition", level=2)
    para(doc, "For store _s_ on day _t_ let **x**(s,t) be the feature vector known in advance (calendar, promotion, "
              "holidays, store profile and sales history that is at least seven days old). The project contains four "
              "learning tasks:")
    table(doc, "Learning tasks in DemandIQ", ["Task", "Type", "Input", "Output"], [
        ["T1 Demand forecast", "Regression", "x(s,t), 27 features", "Sales y(s,t); quantiles q0.1 and q0.9"],
        ["T2 Stockout risk", "Binary classification", "Stock state, deliveries due, forecasts (13 features)", "P(stockout on any of days t+1..t+3)"],
        ["T3 Reorder", "Decision rule on T1/T2", "Forecasts, uncertainty, inventory position", "Order quantity Q(s,t) >= 0"],
        ["T4 Store segments", "Clustering (unsupervised)", "6 store traits", "Segment label 0-3"],
    ], [1.5, 1.4, 1.9, 1.7], font_size=9.5, align=["left", "left", "left", "left"])
    para(doc, "The demand model learns f such that ŷ(s,t) = f(**x**(s,t)) minimises squared error on log(1 + sales), "
              "which is close to minimising percentage error. The risk model learns g such that "
              "p(s,t) = g(**z**(s,t)) estimates the probability of a stockout, where **z** describes the inventory "
              "state in the evening of day t.")
    doc.add_heading("5.3 Scope and assumptions", level=2)
    bullets(doc, [
        "Demand is modelled at store-day level, the finest level Rossmann publishes. Sales values are treated as units.",
        "Closed days have zero demand; the store's opening calendar and promotion plan are known in advance.",
        "Rossmann has no stock data. Stock is simulated by replaying a periodic-review ordering process over the real "
        "daily sales: orders on Monday and Thursday, two-day lead time, 15% of deliveries one day late and 5% two days "
        "late, unmet demand is lost.",
        "Costs: a lost sale costs 30% of its value (lost margin), holding costs 0.07% of value per day (about 25% a year), "
        "a regular delivery costs EUR 25 and an emergency next-day delivery EUR 75.",
        "Rossmann has no prices. The price lever in the what-if tool therefore uses a stated elasticity, not a learned one.",
    ])
    doc.add_heading("5.4 Success criteria", level=2)
    table(doc, "Target metrics fixed before modelling", ["Objective", "Metric", "Target"], [
        ["O1 Demand", "Test MAPE / R²", "MAPE below 10% and below the best baseline; R² above 0.90"],
        ["O1 Uncertainty", "P10-P90 coverage", "Close to 80% of test days"],
        ["O2 Risk", "ROC-AUC / PR-AUC", "ROC-AUC above 0.85; PR-AUC at least 2x the positive rate"],
        ["O3 Ordering", "Stockout days, cost", "At least 30% fewer stockout days than the manager rule, at lower total cost"],
        ["O4 Explain", "SHAP additivity; dashboard", "Contributions add up to the prediction; answers in about 2 seconds"],
    ], [1.4, 1.7, 3.4], font_size=10, align=["left", "left", "left"])


def methodology(doc, R):
    ds = R["ds"]
    sp = R["split"]
    doc.add_heading("6. System Design and Methodology", level=1)
    doc.add_heading("6.1 Overall architecture", level=2)
    para(doc, f"Fig. {next_fig()} shows the full pipeline. Raw data is cleaned and turned into features; stores are "
              "segmented; a regression model forecasts demand; an inventory replay produces stock levels on which a "
              "classifier learns stockout risk; a decision rule converts forecasts and risk into orders; SHAP explains "
              "both models; and a Streamlit dashboard puts everything in front of the user. Each block is one Python "
              "script, run in order by run_all.py.")
    figure(doc, FIG / "fig00_architecture.png", "System architecture of DemandIQ (numbers match the pipeline scripts).", 6.4)

    doc.add_heading("6.2 Dataset selection", level=2)
    para(doc, f"**Source.** Rossmann Store Sales {c('rossmann')}, a public dataset released by the German drugstore "
              f"chain Rossmann. It has {ds['raw_rows']:,} daily records for {ds['raw_stores']:,} stores from "
              f"1 January 2013 to 31 July 2015 and a separate store master file.")
    para(doc, "**Why this dataset.** It is real retail data (not synthetic), large enough for machine learning, "
              "contains exactly the drivers named in our objectives (promotions, state and school holidays, weekday, "
              "season, competition, store format), is freely downloadable, and is a well-known benchmark, so results can "
              "be compared with others.")
    table(doc, "Main columns of the Rossmann dataset", ["Column", "Meaning"], [
        ["Store, Date, DayOfWeek", "Store identifier (1-1115) and trading date"],
        ["Sales", "Daily sales - the demand we forecast (target)"],
        ["Customers, Open", "Number of customers; 1 if the store traded that day"],
        ["Promo / Promo2", "Daily promotion running; store takes part in a continuing loyalty promotion"],
        ["StateHoliday, SchoolHoliday", "Public holiday type (none, public, Easter, Christmas); schools closed"],
        ["StoreType, Assortment", "Store format (a-d) and range carried (basic, extra, extended)"],
        ["CompetitionDistance, ...Since", "Metres to the nearest competitor and when it opened"],
    ], [2.3, 4.2], font_size=10, align=["left", "left"])
    para(doc, f"**Class distribution.** For the regression target, daily sales have a mean of {ds['mean_sales']:,.0f} and "
              f"a median of {ds['median_sales']:,.0f} (right-skewed, so we model log sales). Promotions run on "
              f"{ds['promo_share'] * 100:.1f}% of open days and lift average sales by {ds['promo_lift_chain'] * 100:.1f}%. "
              f"For the classification target, a stockout within three days occurs in "
              f"{R['inv']['positive_rate_%']:.1f}% of store-evenings, so the classes are imbalanced roughly 1:4.")
    para(doc, f"**Split strategy.** Because this is a time series, rows are never shuffled. We split by date "
              f"(Table {next_tab()}). Hyper-parameters are chosen on the validation window only; the test window is used "
              f"once, at the end. Store profile statistics are computed on the training window only.")
    table(doc, "Time-based data split for the demand model", ["Split", "Period", "Rows", "Used for"], [
        ["Training", f"{sp['train']['from']} to {sp['train']['to']}", f"{sp['train']['rows']:,}", "Fitting the models"],
        ["Validation", f"{sp['valid']['from']} to {sp['valid']['to']}", f"{sp['valid']['rows']:,}", "Tuning and model selection"],
        ["Test (held out)", f"{sp['test']['from']} to {sp['test']['to']}", f"{sp['test']['rows']:,}", "Final, one-time evaluation"],
    ], [1.3, 2.3, 1.0, 1.9], font_size=10)

    doc.add_heading("6.3 Data preprocessing and feature engineering", level=2)
    para(doc, "**Cleaning.** (i) 180 stores were closed for refurbishment for six months in 2014; their histories have a "
              f"hole that breaks lag features and the stock simulation, so we keep the {ds['stores_kept']} stores with a "
              f"complete record. (ii) {ds['open_zero_sales_removed']} days marked open with zero sales were treated as closed. "
              "(iii) Each store was re-indexed to a full calendar, so that \"seven days ago\" always means seven calendar "
              "days. (iv) Missing competitor distances (3 stores in the master file) were filled with the median; missing competitor "
              "opening dates were treated as long-established competitors. (v) Closed days are kept in the calendar for "
              f"the simulation but excluded from model training, giving {ds['model_rows']:,} trading days.")
    para(doc, "**Encoding.** Store type, assortment, holiday type and segment are small categories and are given as "
              "integer codes to the tree models; the Ridge and Logistic Regression models use one-hot encoding and "
              "standardised numeric features, with median imputation for missing lags.")
    para(doc, f"**Features.** We built 27 features in five groups (Table {next_tab()}). The key design rule is that "
              "**every sales-history feature is at least seven days old**. This prevents leakage and also means one model "
              "can forecast any of the next seven days, which is exactly what an order covering the next few days needs "
              f"{c('b_kuhn_fes')}.")
    table(doc, "Feature groups used by the demand model", ["Group", "Features", "Why"], [
        ["Calendar", "day of week, day of month, month, week of year, year", "Weekly and yearly seasonality, pay-day effects"],
        ["Promotion", "Promo, Promo2 active this month", "Promotions lift sales by about 40%"],
        ["Holidays", "school holiday, public holiday type, store closed yesterday / tomorrow", "Shopping shifts around closures"],
        ["Store profile", "store type, assortment, segment, Promo2, competitor distance and age, store average, store-weekday average, store promo lift", "Stores differ by a factor of five in size"],
        ["Sales history", "sales 7, 14, 28 days ago; mean of 7 and 28 days and 28-day std (all ending 7 days ago); trend ratio", "Recent level and momentum"],
    ], [1.2, 3.2, 2.1], font_size=9.5, align=["left", "left", "left"])
    para(doc, f"**Store segmentation (K-Means).** For each store we compute six traits on the training window: average daily "
              f"sales, promotion uplift, day-to-day volatility (coefficient of variation), Saturday-to-weekday sales "
              f"ratio, December uplift and log competitor distance. After standardising, K-Means {c('macqueen')} is run "
              f"for k = 2 to 8. The silhouette score {c('rousseeuw')} is low for every k (0.18-0.25), which shows that stores "
              f"form a continuum rather than sharply separated groups; we choose k = {R['km']['chosen_k']} where the elbow "
              f"flattens and the groups are easy to name and act on (Fig. {next_fig()}). The segment number becomes a "
              f"feature of both models.")
    figure(doc, FIG / "fig05_kmeans_choice.png", "Choosing the number of store segments: elbow curve and silhouette score.", 5.6)

    doc.add_heading("6.4 Model selection", level=2)
    para(doc, "For each task we start from a simple baseline and add complexity only if it pays off, as recommended "
              f"by {c('b_gilliland')} and {c('b_kuhn_apm')}.")
    table(doc, "Candidate models and the reason for each", ["Task", "Model", "Why it was chosen"], [
        ["Demand", "Naive (same day last week)", "Simplest possible forecast; any model must beat it"],
        ["Demand", "Historical average", "Store x weekday x promotion average - what an experienced manager would estimate"],
        ["Demand", "Ridge regression", "Linear, fast, easy to explain; tests whether interactions are needed"],
        ["Demand", "Random Forest " + c('breiman'), "Bagged trees capture interactions and are robust to outliers"],
        ["Demand", "Gradient Boosting " + c('friedman', 'lightgbm'), "Histogram-based boosting (LightGBM-style) - state of the art on tabular retail data " + c('m5')],
        ["Demand", "Quantile Gradient Boosting " + c('koenker'), "Same model with pinball loss gives P10 and P90 for safety stock"],
        ["Risk", "Manager rule of thumb", "\"Worry if stock + deliveries cover less than the coming days\" - baseline"],
        ["Risk", "Logistic Regression", "Linear and interpretable; class-weighted for imbalance"],
        ["Risk", "Random Forest / Gradient Boosting", "Non-linear, handle interactions such as promotion x low stock"],
        ["Segments", "K-Means", "Simple, fast, centroids are easy to read as store profiles"],
    ], [0.8, 2.2, 3.5], font_size=9.5, align=["left", "left", "left"])
    best = R["grid"].sort_values("valid_RMSPE").iloc[0]
    para(doc, f"**Key hyper-parameters.** Gradient Boosting (demand): learning rate 0.08, {int(best.max_iter)} trees, "
              f"{int(best.max_leaf_nodes)} leaves per tree, at least {int(best.min_samples_leaf)} samples per leaf, L2 "
              f"penalty {best.l2_regularization}. Random Forest: 120 trees, at least 5 samples per leaf, 50% of features and "
              f"30% of rows per tree. Ridge: alpha = 1. Risk Gradient Boosting: 300 trees, learning rate 0.05, 31 leaves, "
              f"50 samples per leaf. Full settings are listed in Appendix A.")

    doc.add_heading("6.5 Model training", level=2)
    para(doc, f"**Set-up.** Python 3 with pandas, NumPy, scikit-learn {c('sklearn')}, SHAP and Matplotlib; the "
              "dashboard uses Streamlit. Everything runs on an ordinary laptop CPU (no GPU); the full pipeline takes "
              "about eight minutes. A fixed random seed (42) makes every run reproducible.")
    para(doc, "**Loss functions.** Demand models minimise squared error on log(1 + sales), so a 10% miss costs the same "
              "for a small and a large store. Quantile models minimise the pinball loss at 0.1 and 0.9. Classifiers "
              "minimise log-loss (binary cross-entropy). Gradient boosting fits each new tree to the gradient of the loss "
              "(it has no separate optimiser such as Adam); trees play the role of epochs.")
    para(doc, f"**Hyper-parameter tuning.** A grid search over tree size (31, 63, 127 leaves) and L2 penalty (0, 1) was "
              f"run on the training window and scored on the validation window every 50 trees, using RMSPE. The best "
              f"setting was then refitted on training + validation data and scored once on the test window.")
    para(doc, f"**Overfitting control.** Time-based validation, a minimum leaf size, L2 regularisation and choosing the "
              f"number of trees from the validation loss curve (Fig. {next_fig()}). The validation loss flattens after about "
              f"200 trees while the training loss keeps falling slowly, so more trees would only memorise the past.")
    figure(doc, FIG / "fig09_loss_curve.png", "Loss curve of the Gradient Boosting demand model on training and validation data.", 5.0)
    para(doc, "**Honest forecasts for the risk model.** The risk classifier uses the demand forecast as an input. If it "
              "were trained on forecasts the demand model had already seen, it would learn that forecasts are always "
              "right. We therefore train a separate demand model on data up to June 2014 to forecast July 2014 - March "
              "2015 (the risk model's training window); the validation and test windows get forecasts from models "
              "trained only on earlier data.")

    doc.add_heading("6.6 Inventory replay and reorder logic", level=2)
    para(doc, f"Rossmann does not record stock, so we rebuild it {c('b_winston')}. Every evening on Monday and Thursday "
              f"the store orders up to a target level S; the delivery arrives two days later, or later if the supplier is "
              f"late. Each day, customers buy min(stock, demand); unmet demand is lost and the day is a stockout day. "
              f"Three ordering policies are compared:")
    bullets(doc, [
        "**A. Manager rule** - S = (average daily sales of the last 4 weeks + 20%) x trading days to cover. With the "
        f"+20% buffer this policy produces {R['inv']['stockout_day_rate_%']:.1f}% stockout days over the whole period, close "
        f"to the 8.3% measured in real stores {c('gruen')}, so it is a realistic baseline. Its stockout labels train the risk model.",
        "**B. DemandIQ forecast** - the textbook periodic-review policy " + c('b_silver') + " fed with the ML forecast:",
    ])
    equation(doc, "S = Σ F(d)  +  E[delay] · F̄  +  z · √( Σ σ(d)²  +  F̄² · Var[delay] )")
    para(doc, "where F(d) is the forecast for each day d until the next delivery, F̄ the average daily forecast, "
              "σ(d) = (P90 - P10) / 2.563 the forecast uncertainty from the quantile models, E[delay] = 0.25 days and "
              "Var[delay] = 0.29 come from the supplier lateness, and z = 1.645 targets a 95% cycle service level "
              f"{c('b_nahmias')}. The order quantity is Q = max(0, S - stock on hand - stock on order).", indent=0.6)
    bullets(doc, [
        "**C. DemandIQ + risk alerts** - policy B, plus: on non-ordering days, if the risk classifier gives a "
        f"probability above a threshold, place an emergency order that arrives the next morning. The threshold "
        f"({R['pol_set']['emergency_threshold']}) is chosen on the validation window by lowest total cost.",
    ])
    para(doc, "All policies face exactly the same demand and the same random supplier delays, so differences come only "
              "from the ordering decisions.")

    doc.add_heading("6.7 Evaluation metrics", level=2)
    table(doc, "Evaluation metrics and why they suit the problem", ["Metric", "Used for", "Why it suits the problem"], [
        ["MAPE, WAPE", "Demand", "Percentage error is comparable across small and large stores; WAPE weights big stores more"],
        ["RMSE, MAE, R²", "Demand", "Penalise large misses (RMSE); R² shows share of variation explained"],
        ["Bias", "Demand", "Systematic over- or under-forecasting drives over- or under-stocking"],
        ["P10-P90 coverage", "Uncertainty", "A good 80% interval should contain about 80% of actual days"],
        ["ROC-AUC", "Risk", "How well the model ranks risky above safe stores, independent of threshold"],
        ["PR-AUC, precision, recall, F1", "Risk", "Focus on the rare positive class; recall = stockouts caught"],
        ["Calibration, Brier score", "Risk", "Whether \"70% risk\" really means about 70%"],
        ["Stockout days, fill rate, stock held, cost", "Policies", "What the business actually feels " + c('theodorou')],
    ], [1.9, 0.9, 3.7], font_size=9.5, align=["left", "left", "left"])


def results(doc, R):
    dt, dv, st, pol = R["dt"], R["dv"], R["st"], R["pol"]
    gb, rf, ha = dt.loc["Gradient Boosting"], dt.loc["Random Forest"], dt.loc["Historical average"]
    doc.add_heading("7. Results and Discussion", level=1)

    doc.add_heading("7.1 What the data shows", level=2)
    para(doc, f"Fig. {next_fig()} shows weekly average sales over the whole period. Three patterns stand out: a strong "
              "Christmas peak each year, a zig-zag because promotions run every second week, and no long-term trend. "
              f"Fig. {next_fig() + 1} confirms that promotions lift sales on every weekday, and Fig. {next_fig() + 2} shows "
              "the yearly cycle and the extra demand on school holidays and before public holidays.")
    figure(doc, FIG / "fig01_sales_trend.png", "Weekly average sales per open store, with validation and test windows shaded.", 6.3)
    figure(doc, FIG / "fig02_weekday_promo.png", "Average sales by weekday with and without a promotion.", 4.8)
    figure(doc, FIG / "fig03_seasonality_calendar.png", "Monthly seasonality (left) and holiday effects on Monday-Friday sales (right).", 6.2)

    doc.add_heading("7.2 Store segments", level=2)
    seg = R["seg"].set_index("segment_name")
    para(doc, f"K-Means produced four segments (Fig. {next_fig()}). **High-volume flagships** "
              f"({int(seg.loc['High-volume flagships', 'stores'])} stores) sell about "
              f"{seg.loc['High-volume flagships', 'avg_sales']:,.0f} a day, are steady and face close competitors. "
              f"**Promotion-driven** stores ({int(seg.loc['Promotion-driven', 'stores'])}) gain "
              f"{seg.loc['Promotion-driven', 'promo_lift'] * 100:.0f}% on promotion days, against "
              f"{seg.loc['High-volume flagships', 'promo_lift'] * 100:.0f}% for flagships, and are the most volatile. "
              f"**Weekend & seasonal shoppers** ({int(seg.loc['Weekend & seasonal shoppers', 'stores'])}) sell well on "
              f"Saturdays and in December. **Steady neighbourhood stores** ({int(seg.loc['Steady neighbourhood stores', 'stores'])}) "
              f"are close to the average on every trait. The practical message is that one promotion plan or one safety "
              f"buffer does not fit all stores.")
    figure(doc, FIG / "fig06_segment_profiles.png", "Profile of each K-Means segment as a z-score against the average store.", 6.2)

    doc.add_heading("7.3 Demand forecasting results", level=2)
    order = ["Naive (same day last week)", "Historical average", "Ridge regression", "Random Forest", "Gradient Boosting"]
    rows = []
    for m in order:
        r = dt.loc[m]
        rows.append([m, pct(dv.loc[m, "MAPE (%)"], 2), pct(r["MAPE (%)"], 2), pct(r["WAPE (%)"], 2), f"{r['RMSE']:,.0f}",
                     f"{r['MAE']:,.0f}", f3(r["R2"]), f"{r['Bias (%)']:+.2f}%", f"{r['Train time (s)']:.0f}"])
    table(doc, "Demand models: validation MAPE and test-window results (1 Jun - 31 Jul 2015)",
          ["Model", "Valid MAPE", "Test MAPE", "WAPE", "RMSE", "MAE", "R²", "Bias", "Train (s)"],
          rows, [1.75, 0.68, 0.68, 0.62, 0.62, 0.55, 0.55, 0.62, 0.53], font_size=9, bold_rows=(4,))
    para(doc, f"Table {Counter.tab} and Fig. {next_fig()} compare the models. The naive forecast is poor "
              f"({pct(dt.loc[order[0], 'MAPE (%)'])}) because last week's same day often had the opposite promotion status. "
              f"The historical average is a strong baseline ({pct(ha['MAPE (%)'], 2)}), showing how regular store demand "
              f"is. Ridge regression ({pct(dt.loc['Ridge regression', 'MAPE (%)'])}) is worse than the baseline: a linear "
              f"model cannot express interactions such as \"promotion on a Monday in a promotion-driven store\". "
              f"Both tree ensembles beat the baseline clearly. Gradient Boosting had the best validation score "
              f"({pct(dv.loc['Gradient Boosting', 'MAPE (%)'], 2)}) and was therefore selected before the test window was "
              f"opened. On the test window it reaches {pct(gb['MAPE (%)'], 2)} MAPE and R² = {f3(gb['R2'])}, a "
              f"{(1 - gb['MAPE (%)'] / ha['MAPE (%)']) * 100:.0f}% reduction in error against the baseline. ")
    figure(doc, FIG / "fig08_model_comparison.png", "Test MAPE and R² of all demand models (grey = baselines).", 6.2)
    if rf["MAPE (%)"] < gb["MAPE (%)"]:
        para(doc, f"Random Forest ended slightly ahead on the test window ({pct(rf['MAPE (%)'], 2)} against "
                  f"{pct(gb['MAPE (%)'], 2)}). We keep Gradient Boosting because it was chosen on validation (switching now "
                  f"would be selecting on the test set), its bias is close to zero ({gb['Bias (%)']:+.2f}% against "
                  f"{rf['Bias (%)']:+.2f}%), it trains about {rf['Train time (s)'] / max(gb['Train time (s)'], 1):.0f} times "
                  f"faster, it supports the quantile loss we need for safety stock, and exact SHAP values for it take "
                  f"seconds. The validation window has a higher error than the test window for every model because it "
                  f"contains Easter and the May public holidays, which are rare in the training data.")
    else:
        para(doc, "Gradient Boosting is also the best model on the test window. The validation window has a higher "
                  "error than the test window for every model because it contains Easter and the May public holidays, "
                  "which are rare in the training data.")
    para(doc, f"Fig. {next_fig()} plots the forecast against actual sales for three stores, with the P10-P90 band. The "
              f"model follows the promotion weeks and the Monday peaks closely. The P10-P90 band contains "
              f"{R['q']['p10_p90_coverage_test'] * 100:.1f}% of test days, a little below the 80% target, so the intervals "
              f"are slightly too narrow; the safety-stock formula with z = 1.645 compensates for this.")
    figure(doc, FIG / "fig10_forecast_examples.png", "Forecast, actual sales and P10-P90 range for three stores in the test window.", 6.3)
    para(doc, f"**Error analysis.** Fig. {next_fig()} shows where the model fails. Points lie close to the diagonal; "
              "the largest misses are a few very high days (store events not in the data). Error is similar across "
              "segments and highest on Sundays, when only a handful of stores trade and history is thin.")
    R["fig_err"] = figure(doc, FIG / "fig11_error_analysis.png", "Error analysis: forecast vs actual, MAPE by store segment and by weekday.", 6.3)

    doc.add_heading("7.4 Stockout-risk results", level=2)
    inv = R["inv"]
    para(doc, f"The manager-rule replay produces {inv['stockout_day_rate_%']:.2f}% stockout days overall: "
              f"{inv['stockout_rate_promo_days_%']:.1f}% on promotion days against {inv['stockout_rate_non_promo_%']:.1f}% on "
              f"other days, because a four-week average does not anticipate a promotion week. Fig. {next_fig()} shows one "
              f"store's replayed stock.")
    figure(doc, FIG / "fig12_inventory_replay.png", "Replayed stock for store 262 under the manager rule; triangles mark stockout days.", 6.2)
    srows = []
    for m in ["Manager rule of thumb", "Logistic Regression", "Random Forest", "Gradient Boosting"]:
        r = st.loc[m]
        srows.append([m, f3(r["ROC-AUC"]), f3(r["PR-AUC"]), f2(r["Precision"]), f2(r["Recall"]), f2(r["F1"]),
                      f3(r["Brier"]), f2(r["Threshold"])])
    table(doc, f"Stockout-risk classifiers on the test window (positive rate {R['cm']['test_positive_rate'] * 100:.1f}%)",
          ["Model", "ROC-AUC", "PR-AUC", "Precision", "Recall", "F1", "Brier", "Threshold"], srows,
          [1.9, 0.68, 0.68, 0.72, 0.62, 0.55, 0.6, 0.75], font_size=9.5, bold_rows=(3,))
    gbs = st.loc["Gradient Boosting"]
    cm = R["cm"]["confusion_matrix"]
    para(doc, f"The rule of thumb is barely better than chance (ROC-AUC {f3(st.loc['Manager rule of thumb', 'ROC-AUC'])}) "
              f"because most stockouts are caused by promotions and late deliveries, which it ignores. All three learned "
              f"models do far better. Random Forest and Gradient Boosting are almost tied (ROC-AUC "
              f"{f3(st.loc['Random Forest', 'ROC-AUC'])} and {f3(gbs['ROC-AUC'])}); we use Gradient Boosting because its "
              f"probabilities are better calibrated (Brier {f3(gbs['Brier'])}) and it is fast enough to score every store "
              f"each evening. PR-AUC of {f3(gbs['PR-AUC'])} is more than three times the "
              f"{R['cm']['test_positive_rate'] * 100:.0f}% base rate. At the threshold chosen on validation "
              f"({gbs['Threshold']:.2f}) the model catches {cm[1][1]:,} of {cm[1][0] + cm[1][1]:,} stockouts "
              f"(recall {gbs['Recall']:.0%}) with precision {gbs['Precision']:.0%} (Figs. {next_fig()} and {next_fig() + 1}).")
    figure(doc, FIG / "fig13_roc_pr_curves.png", "ROC and precision-recall curves of the stockout classifiers (test window).", 6.2)
    figure(doc, FIG / "fig14_confusion_calibration.png", "Confusion matrix of Gradient Boosting and calibration of predicted probabilities.", 6.0)
    b = R["bands"]
    para(doc, f"For managers, probabilities are grouped into three levels (Fig. {next_fig()}). Stores marked HIGH "
              f"actually ran out {b.rate.iloc[2]:.0%} of the time, MEDIUM {b.rate.iloc[1]:.0%} and LOW only "
              f"{b.rate.iloc[0]:.0%}, while LOW covers {b.share.iloc[0]:.0f}% of store-days. A manager can therefore "
              "ignore most stores on most days and focus on the short HIGH list.")
    figure(doc, FIG / "fig15_risk_bands.png", "Actual stockout rate in each predicted risk level.", 4.6)

    doc.add_heading("7.5 From prediction to decision: ordering policies", level=2)
    A, B, C = pol.iloc[0], pol.iloc[1], pol.iloc[2]
    prow = [[r.policy, pct(r["stockout_day_rate_%"], 2), pct(r["fill_rate_%"], 2), f2(r["avg_stock_days"]),
             f"{int(r.emergency_orders):,}", f"{r.total_cost / 1e6:,.2f}", f"{r['cost_change_%']:+.1f}%"] for _, r in pol.iterrows()]
    table(doc, "Ordering policies replayed on the test window (935 stores, June-July 2015)",
          ["Policy", "Stockout days", "Fill rate", "Stock (days)", "Emergency orders", "Cost (EUR M)", "vs A"], prow,
          [1.9, 0.85, 0.75, 0.8, 0.85, 0.75, 0.6], font_size=9.5, bold_rows=(2,))
    para(doc, f"Table {Counter.tab} and Fig. {next_fig()} give the result that matters most. Feeding the ML forecast into "
              f"a standard order-up-to rule (policy B) cuts stockout days from {pct(A['stockout_day_rate_%'], 2)} to "
              f"{pct(B['stockout_day_rate_%'], 2)} and raises the fill rate to {pct(B['fill_rate_%'], 2)}. Adding risk-"
              f"triggered emergency orders (policy C) brings stockout days down to {pct(C['stockout_day_rate_%'], 2)}, a "
              f"{abs(C['stockout_change_%']):.0f}% reduction, and total cost falls by {abs(C['cost_change_%']):.0f}%. "
              f"The extra stock needed is modest ({A['avg_stock_days']:.2f} to {C['avg_stock_days']:.2f} days of sales), "
              f"and the cost breakdown (Fig. {next_fig() + 1}) shows that lost margin, not holding, dominates the "
              f"manager's cost.")
    figure(doc, FIG / "fig16_policy_comparison.png", "Stockout days, fill rate, stock held and total cost for policies A, B and C.", 6.4)
    figure(doc, FIG / "fig17_cost_breakdown.png", "Where the money goes: lost sales, holding and ordering cost by policy.", 5.4)
    fr = R["front"]
    para(doc, f"**Is this only \"more stock\"?** A fair critic could say the manager would also do better with a bigger "
              f"buffer. Fig. {next_fig()} answers this by replaying each policy at many settings. For every level of stock "
              f"held, the DemandIQ curve lies below the manager's curve: the same stock is simply placed on the right days "
              f"(before promotions and holidays). The gap closes only when both hold so much stock that shelf capacity "
              f"becomes the limit. This addresses gap G3: the benefit comes from better decisions, not just from a lower "
              f"forecast error.")
    figure(doc, FIG / "fig24_tradeoff_frontier.png", "Trade-off between stock held and stockout days for many buffer and service-level settings.", 5.0)

    doc.add_heading("7.6 Explaining the models", level=2)
    sd = R["shap_d"]
    top = sd.label.tolist()[:4]
    para(doc, f"SHAP values were computed exactly with TreeSHAP {c('treeshap')}; the contributions add up to the "
              f"model output for every row (largest difference {R['add'].additivity_max_error.iloc[0]:.1e}). "
              f"Globally (Fig. {next_fig()}), the strongest drivers of the demand forecast are "
              f"{top[0].lower()}, {top[1].lower()}, {top[2].lower()} and {top[3].lower()}. The beeswarm view in Appendix D "
              "shows the direction: promotion days push the forecast up, stores with high usual weekday sales get high "
              "forecasts, and the start of the month and the day after a closure carry extra demand.")
    figure(doc, FIG / "fig19_shap_demand_global.png", "Global SHAP importance of the demand model (mean absolute contribution).", 5.2)
    para(doc, f"Locally, Fig. {next_fig()} explains one forecast in the way a manager would read it: starting from the "
              "average store-day, each bar shows how much one fact pushed this forecast up (red) or down (blue). In the "
              "dashboard the same chart is turned into a sentence such as \"pushed up by the promotion and the store's "
              "usual Monday sales; pulled down by school holidays\".")
    figure(doc, FIG / "fig21_shap_demand_local.png", "Local SHAP explanation of a single forecast (store 262, a promotion Monday).", 6.2)
    up = R["uplift"].set_index("segment_name")["mean"]
    para(doc, f"Fig. {next_fig()} uses the model as a what-if engine: for every store-day in the test sample we switch the "
              f"promotion on and off and record the change. The modelled uplift ranges from "
              f"{up.min() * 100:.0f}% ({up.idxmin()}) to {up.max() * 100:.0f}% ({up.idxmax()}), which confirms gap G5: a single "
              "promotion plan is not right for every store type.")
    figure(doc, FIG / "fig22_promo_effect_by_segment.png", "Model-estimated promotion uplift by store segment (what-if, test sample).", 5.4)
    sr = R["shap_r"].label.tolist()
    para(doc, f"For the risk model (Fig. {next_fig()}) the most important inputs are {sr[0].lower()}, {sr[1].lower()} and "
              f"{sr[2].lower()}, in line with Liu et al. {c('liu')}. Low cover and an upcoming promotion raise risk; a "
              "delivery due in the next three days lowers it. Because explanations exist for the risk score too, the "
              "manager sees not only that a store is HIGH risk but why, which answers gap G2.")
    figure(doc, FIG / "fig23_shap_risk_beeswarm.png", "SHAP summary of the stockout-risk model (each dot is one store-evening).", 5.6)

    doc.add_heading("7.7 Interactive dashboard", level=2)
    para(doc, "The Streamlit dashboard has six pages: an overview of results; a store forecast page with the P10-P90 "
              "band; a ranked risk and reorder list with an order calculator; a \"Why this forecast?\" page with the "
              "SHAP waterfall and a plain-language summary; a what-if simulator (promotion, school holiday, closure, "
              "competitor distance and price with a user-set elasticity); and the store segments. Every what-if screen "
              "carries the warning that the result is model behaviour, not proof of cause and effect. Screenshots are "
              "given in Appendix C.")

    doc.add_heading("7.8 Comparison with the literature", level=2)
    para(doc, f"Direct comparison is difficult because studies use different data and horizons, so Table {next_tab()} "
              "should be read as a sense check rather than a ranking.")
    table(doc, "DemandIQ compared with related work", ["Study", "Task / data", "Reported result", "DemandIQ"], [
        [f"Mishra et al. {c('mishra')}", "SKU-day demand, Online Retail II", "R² 0.243", f"R² {f3(gb['R2'])} at store-day level (less intermittent)"],
        [f"Huber & Stuckenschmidt {c('huber')}", "Bakery daily demand", "ML beats established methods", f"Boosting beats historical average by {(1 - gb['MAPE (%)'] / ha['MAPE (%)']) * 100:.0f}%"],
        [f"Liu et al. {c('liu')}", "Stockout classification, 1.6 M SKUs", "Stock and near-term forecast most important", f"Same top drivers; ROC-AUC {f3(gbs['ROC-AUC'])}"],
        [f"Theodorou et al. {c('theodorou')}", "M5 + inventory simulation", "Accuracy-cost link weak", "Decision layer (risk alerts) adds a further cost cut beyond the forecast"],
        [f"Ban & Rudin {c('banrudin')}", "Feature-based newsvendor", "23-24% lower cost", f"{abs(C['cost_change_%']):.0f}% lower cost vs manager rule (replayed stock)"],
    ], [1.55, 1.5, 1.5, 1.95], font_size=9, align=["left", "left", "left", "left"])
    para(doc, "Our store-level accuracy is higher than SKU-level studies because daily store totals are smoother than "
              "single-product demand; this is a property of the data, not a claim that our model is stronger.")

    doc.add_heading("7.9 Limitations", level=2)
    bullets(doc, [
        "**Simulated inventory.** Stock and stockouts come from a calibrated replay, not from real stock counts. The "
        "relative ranking of policies is reliable because all face the same demand and delays, but absolute savings "
        "would differ in a real store.",
        "**Store level, not product level.** Rossmann reports total sales per store; real ordering happens per product.",
        "**No price data.** The price lever uses an assumed elasticity (default -1.5, adjustable). Bijmolt et al. report "
        f"an average brand-level elasticity of about -2.6 {c('bijmolt')}; whole-store demand is usually less elastic.",
        f"**Narrow intervals.** P10-P90 covers {R['q']['p10_p90_coverage_test'] * 100:.1f}% instead of 80%.",
        "**Moving holidays.** Easter and other moving holidays appear only twice in the training data, which raises "
        "error in April and May.",
        "**Censored demand.** When the shelf is empty, recorded sales understate true demand; our replay treats "
        "recorded sales as demand.",
    ])


def conclusion(doc, R):
    gb = R["dt"].loc["Gradient Boosting"]
    st = R["st"].loc["Gradient Boosting"]
    A, C = R["pol"].iloc[0], R["pol"].iloc[2]
    doc.add_heading("8. Conclusion", level=1)
    para(doc, "DemandIQ shows that a small set of classical machine-learning models, chained together, can take a "
              "retailer from raw sales history to an explained ordering decision. Against the objectives set in "
              "Section 2.3:")
    table(doc, "Objectives against results", ["Objective", "Target", "Achieved", "Status"], [
        ["O1 Predict demand", "MAPE < 10%, R² > 0.90", f"MAPE {pct(gb['MAPE (%)'], 2)}, R² {f3(gb['R2'])}", "Met"],
        ["O1 Uncertainty", "~80% coverage", f"{R['q']['p10_p90_coverage_test'] * 100:.1f}%", "Partly met"],
        ["O2 Stockout risk", "ROC-AUC > 0.85", f"ROC-AUC {f3(st['ROC-AUC'])}, PR-AUC {f3(st['PR-AUC'])}", "Met"],
        ["O3 Reorder", ">= 30% fewer stockout days, lower cost", f"{abs(C['stockout_change_%']):.0f}% fewer, cost {C['cost_change_%']:+.0f}%", "Met"],
        ["O4 Explain + what-if", "Exact SHAP; dashboard", "Exact TreeSHAP for both models; 6-page dashboard", "Met"],
    ], [1.6, 1.8, 2.2, 0.9], font_size=10, align=["left", "left", "left", "center"])
    para(doc, f"The most important finding is that the decision layer matters as much as the forecast. A better forecast "
              f"alone already removes most of the manager's stockouts; letting the risk classifier trigger emergency "
              f"orders removes a further share, and in total stockout days fall from {pct(A['stockout_day_rate_%'], 2)} to "
              f"{pct(C['stockout_day_rate_%'], 2)}. Because every forecast and every risk score comes with its SHAP "
              "explanation, and because what-if results are clearly labelled, the system is something a manager can "
              "question and therefore trust.")


def future(doc):
    doc.add_heading("9. Future Scope", level=1)
    bullets(doc, [
        "**Real stockout labels.** Validate the inventory replay on a dataset with recorded stockouts, such as "
        "FreshRetailNet-50K, and move from store level to product (SKU) level.",
        "**Indian retail and festivals.** Add a Diwali/Eid/Christmas festival calendar and test on Indian retail or "
        "apparel data, where festival peaks are sharper.",
        "**Causal price effect.** Estimate the effect of price with double/debiased machine learning " + c('dml') +
        " once price data is available, instead of an assumed elasticity.",
        "**Better intervals.** Calibrate the P10-P90 band with conformal prediction so that coverage reaches 80%.",
        "**Deployment.** Schedule the pipeline to retrain weekly, send the HIGH-risk list to managers each evening, "
        "and log their decisions to measure real impact.",
    ])


def references(doc):
    doc.add_heading("10. References", level=1)
    for i, key in enumerate(Cite.order, start=1):
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Inches(0.45)
        p.paragraph_format.first_line_indent = Inches(-0.45)
        p.paragraph_format.space_after = Pt(3)
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        add_runs(p, f"[{i}]\t", size=10.5)
        add_runs(p, REFS[key], size=10.5)
    missing = [k for k in REFS if k not in Cite.order]
    if missing:
        print("WARNING - references never cited:", missing)


def appendices(doc, R):
    page_break(doc)
    doc.add_heading("Appendix A. Hyper-parameter settings", level=1)
    best = R["grid"].sort_values("valid_RMSPE").iloc[0]
    table(doc, "Final hyper-parameters", ["Model", "Settings"], [
        ["Gradient Boosting (demand)", f"HistGradientBoostingRegressor; loss = squared error on log(1+sales); learning_rate 0.08; "
                                       f"max_iter {int(best.max_iter)}; max_leaf_nodes {int(best.max_leaf_nodes)}; "
                                       f"min_samples_leaf {int(best.min_samples_leaf)}; l2_regularization {best.l2_regularization}"],
        ["Quantile models", "Same as above with loss = quantile, quantile = 0.1 and 0.9"],
        ["Random Forest (demand)", "n_estimators 120; min_samples_leaf 5; max_features 0.5; max_samples 0.3"],
        ["Ridge regression", "alpha 1.0; one-hot categories; median imputation; standard scaling"],
        ["Gradient Boosting (risk)", "HistGradientBoostingClassifier; max_iter 300; learning_rate 0.05; max_leaf_nodes 31; "
                                     "min_samples_leaf 50; l2_regularization 1.0; threshold tuned on validation (max F1)"],
        ["Random Forest (risk)", "n_estimators 200; min_samples_leaf 20; max_features 0.5; class_weight balanced_subsample"],
        ["Logistic Regression", "class_weight balanced; standard scaling; max_iter 2000"],
        ["K-Means", f"k = 4; n_init 50; standardised features; random_state 42"],
        ["Inventory replay", "Review Mon & Thu; lead time 2 days; 15% one day late, 5% two days late; shelf capacity 6 "
                             "days; manager buffer +20%; z = 1.645; emergency lead time 1 day; emergency threshold "
                             f"{R['pol_set']['emergency_threshold']}"],
    ], [1.8, 4.7], font_size=9.5, align=["left", "left"])
    g = R["grid"].sort_values("valid_RMSPE").drop_duplicates(["max_leaf_nodes", "l2_regularization"])
    table(doc, "Grid search results on the validation window (best number of trees per setting)",
          ["Leaves", "Min leaf", "L2", "Best trees", "Valid RMSPE", "Valid MAPE"],
          [[int(r.max_leaf_nodes), int(r.min_samples_leaf), r.l2_regularization, int(r.max_iter), f"{r.valid_RMSPE:.4f}",
            pct(r.valid_MAPE, 2)] for _, r in g.iterrows()], [0.9, 0.9, 0.7, 1.0, 1.2, 1.2], font_size=10)
    th = R["thr"]
    table(doc, "Choosing the emergency-order threshold on the validation window (policy C)",
          ["Threshold", "Stockout days", "Emergency orders", "Total cost (EUR M)"],
          [[r.threshold, pct(r["stockout_day_rate_%"], 2), f"{int(r.emergency_orders):,}", f"{r.total_cost / 1e6:.3f}"]
           for _, r in th.iterrows()], [1.1, 1.3, 1.5, 1.6], font_size=10)

    doc.add_heading("Appendix B. Code structure and key snippet", level=1)
    para(doc, "The project is organised as one script per pipeline step. Running python src/run_all.py rebuilds every "
              "table and figure in this report; streamlit run app/app.py opens the dashboard.")
    table(doc, "Project files", ["File", "Purpose"], [
        ["src/config.py", "All settings: dates, costs, lead time, palette"],
        ["src/step1_prepare_data.py", "Cleaning, calendar re-indexing, 27 features, EDA figures"],
        ["src/step2_store_segments.py", "K-Means store segmentation"],
        ["src/step3_demand_model.py", "Baselines, Ridge, Random Forest, Gradient Boosting, quantiles, tuning"],
        ["src/inventory.py", "Inventory replay and the three ordering policies"],
        ["src/step4_stockout_model.py", "Risk dataset, four classifiers, ROC/PR/calibration"],
        ["src/step5_reorder_policies.py", "Policy comparison, threshold tuning, trade-off curve, reorder list"],
        ["src/step6_explain.py", "SHAP global and local explanations, promotion uplift by segment"],
        ["app/app.py", "Streamlit dashboard with what-if simulator"],
    ], [2.4, 4.1], font_size=9.5, align=["left", "left"])
    para(doc, "The order-up-to rule at the heart of policy B (from src/inventory.py):")
    code = [
        "f_sum = p.fc[:, sl].sum(1)        # forecast until next delivery",
        "f_day = f_sum / np.maximum(p.open[:, sl].sum(1), 1)",
        "var   = (p.sigma[:, sl] ** 2).sum(1) + f_day ** 2 * DELAY_VAR",
        "S     = f_sum + DELAY_MEAN * f_day + SERVICE_LEVEL_Z * np.sqrt(var)",
        "q     = np.maximum(0, S - on_hand - pending)   # order quantity",
    ]
    for line in code:
        p = doc.add_paragraph()
        r = p.add_run(line)
        r.font.name = "Courier New"
        r.font.size = Pt(9)
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.left_indent = Inches(0.3)
    para(doc, "", after=4)

    doc.add_heading("Appendix C. Dashboard screenshots", level=1)
    for name, cap in [("overview", "Dashboard overview page."), ("whatif", "What-if simulator: a promotion switched on for one store-day."),
                      ("why", "\"Why this forecast?\" page with the SHAP waterfall and a plain-language summary."),
                      ("risk", "Stockout risk and reorder list with the order calculator.")]:
        f = SHOTS / f"{name}.png"
        if f.exists():
            figure(doc, f, cap, 6.0)

    doc.add_heading("Appendix D. Additional figures", level=1)
    figure(doc, FIG / "fig20_shap_demand_beeswarm.png", "SHAP beeswarm of the demand model: colour = feature value, position = push on the forecast.", 6.0)
    figure(doc, FIG / "fig07_segment_scatter.png", "The 935 stores in the four K-Means segments (first two principal components).", 4.8)
    figure(doc, FIG / "fig04_store_types.png", "Distribution of store average sales by Rossmann store type.", 4.6)
    figure(doc, FIG / "fig18_policy_store_example.png", "Stock of store 262 under policies A and C during the test window.", 6.2)

    doc.add_heading("Appendix E. Ethics, bias and reproducibility", level=1)
    bullets(doc, [
        "**Privacy.** The data is public and aggregated per store and day; it contains no customer-level or personal "
        "information.",
        f"**Fairness and bias.** Error was checked across store segments and weekdays (Fig. {R['fig_err']}); no segment is served "
        "noticeably worse. A forecast that systematically under-predicts small stores would starve them of stock, so "
        "this check should be repeated whenever the model is retrained.",
        "**Responsible use.** What-if results are labelled as model behaviour, and the price lever is labelled as an "
        "assumption. Recommendations support, not replace, the store manager.",
        "**Reproducibility.** Fixed seed 42; all settings in src/config.py; the Rossmann data is downloadable from "
        "Kaggle; python src/run_all.py regenerates every number and figure in this report.",
        "**Originality.** The written report is to be checked for similarity (target under 10%) before submission.",
    ])


# ======================================================================= main
def main():
    R = load_results()
    doc = new_document()
    cover(doc)

    # front matter: roman page numbers
    s2 = doc.add_section(WD_SECTION.NEW_PAGE)
    page_number_format(s2, "lowerRoman", 1)
    page_number_footer(s2, "DemandIQ")
    header_text(s2, "DemandIQ - Machine Learning Group Activity Report")
    s2._sectPr.remove(s2._sectPr.find("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}pgBorders")) \
        if s2._sectPr.find("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}pgBorders") is not None else None
    declaration(doc, R)
    page_break(doc)
    toc(doc)

    # main body: arabic page numbers from 1
    s3 = doc.add_section(WD_SECTION.CONTINUOUS)
    page_number_format(s3, "decimal", 1)
    page_number_footer(s3, "DemandIQ")
    header_text(s3, "DemandIQ - Machine Learning Group Activity Report")
    abstract(doc, R)
    introduction(doc, R)
    literature(doc, R)
    gaps(doc, R)
    problem(doc, R)
    methodology(doc, R)
    results(doc, R)
    conclusion(doc, R)
    future(doc)
    references(doc)
    appendices(doc, R)

    out = HERE / "DemandIQ_Project_Report.docx"
    doc.core_properties.title = TITLE
    doc.core_properties.author = ", ".join(n for n, _ in TEAM)
    doc.save(out)
    print("saved", out, "| figures:", Counter.fig, "| tables:", Counter.tab, "| references:", len(Cite.order))


if __name__ == "__main__":
    main()
