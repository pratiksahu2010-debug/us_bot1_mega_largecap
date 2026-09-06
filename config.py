"""
config.py
---------
US stock alert bot - one of three standalone deployments (see BOT_NAME
below). Data source: Alpaca Markets (free API key, free IEX real-time
feed, no card required) - see alpaca_feed.py.

Market hours: 9:30 AM - 4:00 PM US Eastern, Mon-Fri. Uses the named
timezone "America/New_York" so daylight saving transitions are handled
automatically by APScheduler - no manual DST adjustment needed.
"""

import os
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

BOT_ID = "USBOT3"
BOT_NAME = "US SMALL-MID CAP & GROWTH BOT"
TELEGRAM_DISPLAY_NAME = "@USSmallMidGrowthAlertBot"

# ---------------------------------------------------------------------------
# Symbol universe - built directly into this file so a missing/uncommitted
# symbols.json can never silently shrink your monitored list. Override by
# editing bots_config/symbols.json (a flat JSON array) - if present, it
# takes priority over this built-in list.
#
# NOTE: ticker validity changes over time (mergers, rebrands, delistings).
# alpaca_feed.validate_symbols() checks every symbol against Alpaca's live
# active-assets list at boot and cleanly skips anything no longer
# tradeable - check the boot log after first deploy for exactly what (if
# anything) got skipped.
# ---------------------------------------------------------------------------
_BUILT_IN_SYMBOLS = [
    "PLTR", "SOFI", "RIVN", "LCID", "COIN", "RBLX", "SNAP", "PINS", "ROKU", "DKNG", "AFRM",
    "UPST", "CHPT", "FUBO", "OPEN", "CRWD", "DDOG", "NET", "MDB", "SNOW", "TEAM", "HUBS",
    "TWLO", "OKTA", "ZS", "S", "PATH", "U", "ASAN", "PCTY", "BILL", "FSLY", "ESTC", "GTLB",
    "CFLT", "PD", "SMAR", "APPN", "DOMO", "AI", "SOUN", "BBAI", "IONQ", "RGTI", "QUBT", "MARA",
    "RIOT", "CLSK", "HUT", "BITF", "CIFR", "WULF", "SAVA", "INCY", "EXEL", "RARE", "BMRN",
    "ALNY", "IONS", "SRPT", "ARWR", "FOLD", "CROX", "DECK", "YETI", "FIVE", "OLLI", "BURL",
    "ULTA", "LULU", "CAVA", "SG", "WING", "SHAK", "CMG", "PLNT", "XPOF", "CHWY", "W", "CVNA",
    "CARG", "VRM", "ETSY", "DOCU", "ZM", "ENPH", "SEDG", "FSLR", "RUN", "NOVA", "PLUG", "BE",
    "ARKK", "SPCE", "ACHR", "JOBY", "LILM", "EVGO", "BLNK", "QS", "FCEL", "CLNE", "DNA",
    "BEAM", "NTLA", "CRSP", "EDIT", "ONON", "BROS", "DUOL", "RDDT", "APP", "DASH", "ABNB",
    "UBER", "LYFT", "AXON", "CELH", "ELF"
]

_SYMBOLS_PATH = BASE_DIR / "bots_config" / "symbols.json"
SYMBOLS = _BUILT_IN_SYMBOLS
try:
    with open(_SYMBOLS_PATH) as f:
        _override = json.load(f)
    if isinstance(_override, list) and len(_override) > 0:
        SYMBOLS = _override
        print(f"[config] Loaded {len(SYMBOLS)} symbols from bots_config/symbols.json (override)")
    else:
        print(f"[config] bots_config/symbols.json empty/invalid, using built-in list ({len(SYMBOLS)} symbols)")
except (FileNotFoundError, json.JSONDecodeError):
    print(f"[config] bots_config/symbols.json not found, using built-in list ({len(SYMBOLS)} symbols) - this is fine")

# ---------------------------------------------------------------------------
# Strict rule thresholds - same shape as the NSE version (equities, not
# crypto, so bands are NOT widened the way the crypto bot's are).
# ---------------------------------------------------------------------------
RSI_LONG_MIN, RSI_LONG_MAX = 40, 65
RSI_SHORT_MIN, RSI_SHORT_MAX = 35, 60
ADX_MIN = 25
VWAP_MAX_DISTANCE_PCT = 2.0
CONFIDENCE_HIGH_PCT = 0.5
CONFIDENCE_MEDIUM_PCT = 1.5
VOLUME_LOOKBACK = 20
EMA_FAST, EMA_SLOW = 9, 21
RSI_PERIOD = 14
ADX_PERIOD = 14

SCORE_ALERT_THRESHOLD = 8
EARLY_SIGNAL_ENABLED = True
EARLY_SCORE_MIN = 6
EARLY_COOLDOWN_HOURS = 1
COOLDOWN_HOURS = 2

CANDLE_INTERVAL = "15Min"          # Alpaca timeframe string - change to "5Min" if you prefer
SCAN_INTERVAL_MINUTES = 15         # matches CANDLE_INTERVAL by default - keep these in sync

MARKET_OPEN = "09:30"
MARKET_CLOSE = "16:00"
MORNING_RESET_TIME = "09:25"
DAILY_SUMMARY_TIME = "16:05"
ERROR_SUMMARY_TIME = "16:10"
TIMEZONE = "America/New_York"      # DST-aware - no manual adjustment needed

MAX_CONSECUTIVE_FAILS_BROKEN = 3
MAX_CONSECUTIVE_FAILS_DISABLE = 5

SQLITE_PATH = str(BASE_DIR / "data" / "alerts.db")

# ---------------------------------------------------------------------------
# Telegram - set in Render's Environment tab, NEVER in this file
# ---------------------------------------------------------------------------
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

# ---------------------------------------------------------------------------
# Alpaca Markets - free API key, free real-time IEX data, no card required.
# Sign up at https://alpaca.markets, create a paper trading account, then
# generate an API key/secret from the dashboard. Set in Render's
# Environment tab, NEVER in this file.
# ---------------------------------------------------------------------------
ALPACA_API_KEY = os.environ.get("ALPACA_API_KEY", "").strip()
ALPACA_API_SECRET = os.environ.get("ALPACA_API_SECRET", "").strip()

DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"
PORT = int(os.environ.get("PORT", "10000"))


def validate_and_report():
    print("=" * 60)
    print(f"[config] BOT: {BOT_NAME}")
    print(f"[config] DRY_RUN: {DRY_RUN}")
    print(f"[config] Market hours: {MARKET_OPEN}-{MARKET_CLOSE} {TIMEZONE}, scan every {SCAN_INTERVAL_MINUTES} min")
    checks = [
        ("TELEGRAM_TOKEN", TELEGRAM_TOKEN), ("TELEGRAM_CHAT_ID", TELEGRAM_CHAT_ID),
        ("ALPACA_API_KEY", ALPACA_API_KEY), ("ALPACA_API_SECRET", ALPACA_API_SECRET),
    ]
    any_missing = False
    for name, value in checks:
        if value:
            print(f"[config]   {name}: SET (length {len(value)})")
        else:
            print(f"[config]   {name}: *** MISSING OR EMPTY *** - set this in Render > Environment")
            any_missing = True
    if any_missing and not DRY_RUN:
        print("[config] WARNING: one or more required env vars are missing and DRY_RUN is false.")
    print("=" * 60)


validate_and_report()
