"""
Global configuration for the Rider Operations Intelligence Dashboard.
"""
from dotenv import load_dotenv
import os

# ─── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
MASTER_FILE = os.path.join(DATA_DIR, "master_orders.csv")
UPLOAD_LOG_FILE = os.path.join(DATA_DIR, "upload_log.csv")

load_dotenv()

# ─── PocketBase Configuration ─────────────────────────────────────────────────
POCKETBASE_URL = os.getenv("POCKETBASE_URL", "").strip()
POCKETBASE_API_TOKEN = os.getenv("POCKETBASE_API_TOKEN", "").strip()
POCKETBASE_MASTER_COLLECTION = os.getenv("POCKETBASE_MASTER_COLLECTION", "master_orders")
POCKETBASE_UPLOAD_LOG_COLLECTION = os.getenv("POCKETBASE_UPLOAD_LOG_COLLECTION", "upload_log")
POCKETBASE_ADMIN_EMAIL = os.getenv("POCKETBASE_ADMIN_EMAIL", "").strip()
POCKETBASE_ADMIN_PASSWORD = os.getenv("POCKETBASE_ADMIN_PASSWORD", "").strip()
POCKETBASE_ADMIN_TOKEN = os.getenv("POCKETBASE_ADMIN_TOKEN", "").strip()
try:
    POCKETBASE_PAGE_SIZE = int(os.getenv("POCKETBASE_PAGE_SIZE", "200"))
except ValueError:
    POCKETBASE_PAGE_SIZE = 200

# ─── Shift Buckets ───────────────────────────────────────────────────────────
SHIFT_BUCKETS = {
    "Morning":   (6, 11),    # 06:00 – 10:59
    "Lunch":     (11, 14),   # 11:00 – 13:59
    "Afternoon": (14, 17),   # 14:00 – 16:59
    "Evening":   (17, 21),   # 17:00 – 20:59
    "Night":     (21, 6),    # 21:00 – 05:59 (wraps midnight)
}

SHIFT_ORDER = ["Morning", "Lunch", "Afternoon", "Evening", "Night"]

# ─── Required & Optional Columns ─────────────────────────────────────────────
REQUIRED_COLUMNS = ["order_id", "order_datetime", "rider_name", "order_status"]

OPTIONAL_COLUMNS = [
    "pickup_time", "dispatch_time", "delivered_time",
    "vendor", "zone", "cancellation_reason",
]
MASTER_COLLECTION_FIELDS = [
    "order_id", "order_datetime", "rider_name", "order_status",
    "dispatch_time", "pickup_time", "delivered_time",
    "dispatched_at", "delivered_at", "vendor", "zone", "cancellation_reason", "meta",
]
UPLOAD_LOG_COLLECTION_FIELDS = [
    "timestamp", "filename", "rows_in_file", "rows_after_cleaning", "rows_dropped_during_cleaning",
    "rows_added", "duplicates_removed", "total_master_rows", "errors",
]

# ─── Column Alias Mapping (raw export header → internal name) ────────────────
# Keys = internal standardized name, Values = list of accepted aliases
COLUMN_ALIASES = {
    "order_id":       ["order_id", "Order ID", "order id", "OrderID"],
    "order_datetime": ["order_datetime", "Created At", "created_at", "created at", "Order Date", "order_date"],
    "rider_name":     ["rider_name", "Rider Name", "rider", "Rider"],
    "order_status":   ["order_status", "Order Status", "status", "Status"],
    "delivered_at":   ["delivered_at", "Delivered At", "delivered at", "delivered_time", "Delivered Time"],
    "dispatched_at":  ["dispatched_at", "Dispatched At", "dispatched at", "dispatch_time", "Dispatch Time"],
}

# ─── Rider Categories ────────────────────────────────────────────────────────
RIDER_CATEGORIES = {
    "Core":     "Works ≥5 days/week, high consistency, high completion",
    "Peak":     "Active mostly during peak shifts, good productivity",
    "Flexible": "Spread across shifts/days, moderate consistency",
    "Backup":   "Low frequency but available, decent completion rate",
    "At-risk":  "Declining activity or low completion rate",
    "Inactive": "No activity in the last 14 days",
}

# ─── Scoring Weights (for deployment ranking) ─────────────────────────────────
SCORING_WEIGHTS = {
    "productivity":   0.30,
    "attendance":     0.25,
    "completion":     0.20,
    "recency":        0.15,
    "shift_match":    0.10,
}

# ─── Misc ─────────────────────────────────────────────────────────────────────
WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DEFAULT_RIDERS_PER_SHIFT = 5
INACTIVE_DAYS_THRESHOLD = 14
RECENT_TREND_WINDOW_DAYS = 14
