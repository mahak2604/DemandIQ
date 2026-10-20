"""IEEE reference list. Numbers are assigned in order of first citation."""

REFS = {
    # ---------------------------------------------------------------- research papers
    "seyedan": 'M. Seyedan and F. Mafakheri, "Predictive big data analytics for supply chain demand forecasting: Methods, applications, and research opportunities," _J. Big Data_, vol. 7, Art. no. 53, 2020, doi: 10.1186/s40537-020-00329-2.',
    "m5": 'S. Makridakis, E. Spiliotis, and V. Assimakopoulos, "M5 accuracy competition: Results, findings, and conclusions," _Int. J. Forecast._, vol. 38, no. 4, pp. 1346-1364, 2022, doi: 10.1016/j.ijforecast.2021.11.013.',
    "lightgbm": 'G. Ke, Q. Meng, T. Finley, T. Wang, W. Chen, W. Ma, Q. Ye, and T.-Y. Liu, "LightGBM: A highly efficient gradient boosting decision tree," in _Proc. Adv. Neural Inf. Process. Syst. (NIPS)_, vol. 30, 2017, pp. 3146-3154.',
    "gurali": 'Ö. Gür Ali, S. Sayın, T. van Woensel, and J. Fransoo, "SKU demand forecasting in the presence of promotions," _Expert Syst. Appl._, vol. 36, no. 10, pp. 12340-12348, 2009, doi: 10.1016/j.eswa.2009.04.052.',
    "huber": 'J. Huber and H. Stuckenschmidt, "Daily retail demand forecasting using machine learning with emphasis on calendric special days," _Int. J. Forecast._, vol. 36, no. 4, pp. 1420-1438, 2020, doi: 10.1016/j.ijforecast.2020.02.005.',
    "spiliotis": 'E. Spiliotis, S. Makridakis, A.-A. Semenoglou, and V. Assimakopoulos, "Comparison of statistical and machine learning methods for daily SKU demand forecasting," _Oper. Res. Int. J._, vol. 22, no. 3, pp. 3037-3061, 2022, doi: 10.1007/s12351-020-00605-2.',
    "tft": 'B. Lim, S. Ö. Arık, N. Loeff, and T. Pfister, "Temporal fusion transformers for interpretable multi-horizon time series forecasting," _Int. J. Forecast._, vol. 37, no. 4, pp. 1748-1764, 2021.',
    "liu": 'Y. Liu, D. Kalaitzi, M. Wang, and C. Papanagnou, "A machine learning approach to inventory stockout prediction," _J. Digit. Econ._, vol. 4, pp. 144-155, 2025, doi: 10.1016/j.jdec.2025.06.002.',
    "theodorou": 'E. Theodorou, E. Spiliotis, and V. Assimakopoulos, "Forecast accuracy and inventory performance: Insights on their relationship from the M5 competition data," _Eur. J. Oper. Res._, vol. 322, no. 2, pp. 414-426, 2025, doi: 10.1016/j.ejor.2024.12.033.',
    "bertsimas": 'D. Bertsimas and N. Kallus, "From predictive to prescriptive analytics," _Manage. Sci._, vol. 66, no. 3, pp. 1025-1044, 2020, doi: 10.1287/mnsc.2018.3253.',
    "banrudin": 'G.-Y. Ban and C. Rudin, "The big data newsvendor: Practical insights from machine learning," _Oper. Res._, vol. 67, no. 1, pp. 90-108, 2019, doi: 10.1287/opre.2018.1757.',
    "shap": 'S. M. Lundberg and S.-I. Lee, "A unified approach to interpreting model predictions," in _Proc. Adv. Neural Inf. Process. Syst. (NIPS)_, vol. 30, 2017, pp. 4765-4774.',
    "mishra": 'L. N. Mishra, B. Senapati, S. K. Nayak, and A. J. Rangari, "Explainable retail demand forecasting: A hybrid LightGBM-SHAP framework for inventory optimization," _IEEE Access_, vol. 14, pp. 43613-43633, 2026, doi: 10.1109/ACCESS.2026.3675540.',
    "rozanec": 'J. M. Rožanec, B. Fortuna, and D. Mladenić, "Knowledge graph-based rich and confidentiality preserving explainable artificial intelligence (XAI)," _Inf. Fusion_, vol. 81, pp. 91-102, 2022, doi: 10.1016/j.inffus.2021.11.015.',
    "dml": 'V. Chernozhukov, D. Chetverikov, M. Demirer, E. Duflo, C. Hansen, W. Newey, and J. Robins, "Double/debiased machine learning for treatment and structural parameters," _Econom. J._, vol. 21, no. 1, pp. C1-C68, 2018.',
    # ---------------------------------------------------------------- method foundations & data
    "fildes": 'R. Fildes, S. Ma, and S. Kolassa, "Retail forecasting: Research and practice," _Int. J. Forecast._, vol. 38, no. 4, pp. 1283-1318, 2022.',
    "gruen": 'T. W. Gruen, D. S. Corsten, and S. Bharadwaj, _Retail Out-of-Stocks: A Worldwide Examination of Extent, Causes and Consumer Responses_. Washington, DC, USA: Grocery Manufacturers of America, 2002.',
    "rossmann": 'Rossmann, "Rossmann Store Sales," Kaggle competition dataset, 2015. [Online]. Available: https://www.kaggle.com/c/rossmann-store-sales',
    "breiman": 'L. Breiman, "Random forests," _Mach. Learn._, vol. 45, no. 1, pp. 5-32, 2001.',
    "friedman": 'J. H. Friedman, "Greedy function approximation: A gradient boosting machine," _Ann. Statist._, vol. 29, no. 5, pp. 1189-1232, 2001.',
    "koenker": 'R. Koenker and G. Bassett, "Regression quantiles," _Econometrica_, vol. 46, no. 1, pp. 33-50, 1978.',
    "macqueen": 'J. MacQueen, "Some methods for classification and analysis of multivariate observations," in _Proc. 5th Berkeley Symp. Math. Statist. Probab._, vol. 1, 1967, pp. 281-297.',
    "rousseeuw": 'P. J. Rousseeuw, "Silhouettes: A graphical aid to the interpretation and validation of cluster analysis," _J. Comput. Appl. Math._, vol. 20, pp. 53-65, 1987.',
    "treeshap": 'S. M. Lundberg, G. Erion, H. Chen, A. DeGrave, J. M. Prutkin, B. Nair, R. Katz, J. Himmelfarb, N. Bansal, and S.-I. Lee, "From local explanations to global understanding with explainable AI for trees," _Nat. Mach. Intell._, vol. 2, no. 1, pp. 56-67, 2020.',
    "sklearn": 'F. Pedregosa _et al._, "Scikit-learn: Machine learning in Python," _J. Mach. Learn. Res._, vol. 12, pp. 2825-2830, 2011.',
    "bijmolt": 'T. H. A. Bijmolt, H. J. van Heerde, and R. G. M. Pieters, "New empirical generalizations on the determinants of price elasticity," _J. Mark. Res._, vol. 42, no. 2, pp. 141-156, 2005.',
    # ---------------------------------------------------------------- reference books
    "b_fpp": 'R. J. Hyndman and G. Athanasopoulos, _Forecasting: Principles and Practice_, 3rd ed. Melbourne, Australia: OTexts, 2021.',
    "b_box": 'G. E. P. Box, G. M. Jenkins, G. C. Reinsel, and G. M. Ljung, _Time Series Analysis: Forecasting and Control_, 5th ed. Hoboken, NJ, USA: Wiley, 2015.',
    "b_gilliland": 'M. Gilliland, _The Business Forecasting Deal: Exposing Myths, Eliminating Bad Practices, Providing Practical Solutions_. Hoboken, NJ, USA: Wiley, 2010.',
    "b_silver": 'E. A. Silver, D. F. Pyke, and D. J. Thomas, _Inventory and Production Management in Supply Chains_, 4th ed. Boca Raton, FL, USA: CRC Press, 2017.',
    "b_chopra": 'S. Chopra and P. Meindl, _Supply Chain Management: Strategy, Planning, and Operation_, 6th ed. Boston, MA, USA: Pearson, 2016.',
    "b_nahmias": 'S. Nahmias and T. L. Olsen, _Production and Operations Analysis_, 7th ed. Long Grove, IL, USA: Waveland Press, 2015.',
    "b_zipkin": 'P. H. Zipkin, _Foundations of Inventory Management_. Boston, MA, USA: McGraw-Hill, 2000.',
    "b_axsater": 'S. Axsäter, _Inventory Control_, 3rd ed. Cham, Switzerland: Springer, 2015.',
    "b_winston": 'W. L. Winston, _Operations Research: Applications and Algorithms_, 4th ed. Belmont, CA, USA: Thomson Brooks/Cole, 2004.',
    "b_esl": 'T. Hastie, R. Tibshirani, and J. Friedman, _The Elements of Statistical Learning: Data Mining, Inference, and Prediction_, 2nd ed. New York, NY, USA: Springer, 2009.',
    "b_islr": 'G. James, D. Witten, T. Hastie, and R. Tibshirani, _An Introduction to Statistical Learning_, 2nd ed. New York, NY, USA: Springer, 2021.',
    "b_bishop": 'C. M. Bishop, _Pattern Recognition and Machine Learning_. New York, NY, USA: Springer, 2006.',
    "b_murphy": 'K. P. Murphy, _Probabilistic Machine Learning: An Introduction_. Cambridge, MA, USA: MIT Press, 2022.',
    "b_geron": 'A. Géron, _Hands-On Machine Learning with Scikit-Learn, Keras, and TensorFlow_, 3rd ed. Sebastopol, CA, USA: O\'Reilly Media, 2022.',
    "b_kuhn_apm": 'M. Kuhn and K. Johnson, _Applied Predictive Modeling_. New York, NY, USA: Springer, 2013.',
    "b_kuhn_fes": 'M. Kuhn and K. Johnson, _Feature Engineering and Selection: A Practical Approach for Predictive Models_. Boca Raton, FL, USA: CRC Press, 2019.',
    "b_he": 'H. He and Y. Ma, Eds., _Imbalanced Learning: Foundations, Algorithms, and Applications_. Hoboken, NJ, USA: Wiley-IEEE Press, 2013.',
    "b_molnar": 'C. Molnar, _Interpretable Machine Learning: A Guide for Making Black Box Models Explainable_, 2nd ed. 2022. [Online]. Available: https://christophm.github.io/interpretable-ml-book/',
    "b_pearl": 'J. Pearl, M. Glymour, and N. P. Jewell, _Causal Inference in Statistics: A Primer_. Chichester, U.K.: Wiley, 2016.',
    "b_provost": 'F. Provost and T. Fawcett, _Data Science for Business_. Sebastopol, CA, USA: O\'Reilly Media, 2013.',
}

BOOKS = [k for k in REFS if k.startswith("b_")]
PAPERS = ["seyedan", "m5", "lightgbm", "gurali", "huber", "spiliotis", "tft", "liu", "theodorou",
          "bertsimas", "banrudin", "shap", "mishra", "rozanec", "dml"]


class Cite:
    order = []

    @classmethod
    def n(cls, key):
        if key not in REFS:
            raise KeyError(key)
        if key not in cls.order:
            cls.order.append(key)
        return cls.order.index(key) + 1

    @classmethod
    def c(cls, *keys):
        return ", ".join(f"[{cls.n(k)}]" for k in keys)
