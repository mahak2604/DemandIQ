"""
DemandIQ - central settings.

Every number that controls the pipeline lives here, so the team can explain
(and change) any choice from one place.
"""
from pathlib import Path

# ---------------------------------------------------------------- paths
ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
PROC_DIR = ROOT / "data" / "processed"
FIG_DIR = ROOT / "outputs" / "figures"
TAB_DIR = ROOT / "outputs" / "tables"
MODEL_DIR = ROOT / "outputs" / "models"
for _d in (PROC_DIR, FIG_DIR, TAB_DIR, MODEL_DIR):
    _d.mkdir(parents=True, exist_ok=True)

RANDOM_STATE = 42

# ---------------------------------------------------------------- time split
# Strictly by date - never random - because this is a time series.
TRAIN_END = "2015-03-31"      # training data: Jan 2013 - Mar 2015
VALID_END = "2015-05-31"      # validation (tuning): Apr - May 2015
TEST_END = "2015-07-31"       # test (held out):    Jun - Jul 2015

# The stockout model needs demand forecasts that were *not* fitted on the same
# rows. A first demand model trained up to this date produces honest forecasts
# for the stockout model's training window.
RISK_FORECAST_CUTOFF = "2014-06-30"

# ---------------------------------------------------------------- features
# All sales-history features are at least 7 days old. That means one model can
# forecast any day in the coming week - exactly what a replenishment order needs.
HISTORY_GAP = 7

# ---------------------------------------------------------------- store segments
N_SEGMENTS = 4

# ---------------------------------------------------------------- inventory
# Rossmann publishes sales, not stock. We replay a realistic ordering process
# over the real demand series to obtain stock levels and stockout labels.
REVIEW_DAYS = (0, 3)           # orders placed on Monday and Thursday
LEAD_TIME = 2                  # days from order to delivery
P_LATE_1 = 0.15                # share of deliveries one day late
P_LATE_2 = 0.05                # share of deliveries two days late
MANAGER_BUFFER = 1.20          # rule of thumb: "last 4 weeks' average + 20%"
SHELF_CAPACITY_DAYS = 6        # back-room + shelf space, in days of average sales
RISK_WINDOW = 3                # "will this store run out in the next 3 days?"

# DemandIQ ordering
SERVICE_LEVEL_Z = 1.645        # 95% cycle service level
EMERGENCY_LEAD = 1             # an expedited order arrives next day
RISK_THRESHOLD = 0.50          # alert threshold for an emergency order

# Costs, per unit of sales value (Rossmann sales are in euros)
COST_LOST_SALE = 0.30          # lost gross margin on a sale we could not make
COST_HOLDING = 0.0007          # per unit per day (~25%/year on cost of goods)
COST_ORDER = 25.0              # fixed cost of a regular delivery
COST_EMERGENCY = 75.0          # fixed cost of an expedited delivery

# ---------------------------------------------------------------- plot style
PALETTE = {
    "navy": "#1F3A5F",
    "teal": "#2E8B8B",
    "amber": "#D98E04",
    "red": "#B23A48",
    "grey": "#8A8F98",
    "light": "#E9EEF3",
    "green": "#4C8C4A",
}
