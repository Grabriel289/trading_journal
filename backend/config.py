from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DATABASE_URL = f"sqlite:///{DATA_DIR / 'cryptojournal.db'}"

BINANCE_BASE_URL = "https://api.binance.com"
BINANCE_FAPI_URL = "https://fapi.binance.com"
HTTP_TIMEOUT_SECONDS = 10.0

# Background jobs
import os

BG_JOBS_ENABLED = os.environ.get("BG_JOBS_ENABLED", "true").lower() == "true"
PRICE_CACHE_REFRESH_SECONDS = 60
FUNDING_SYNC_HOURS = 8
DAILY_SNAPSHOT_HOUR_UTC = 0  # 00:00 UTC

# Logging — see backend/util/logging.py
LOG_LEVEL  = os.environ.get("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = os.environ.get("LOG_FORMAT", "text").lower()  # "json" or "text"
