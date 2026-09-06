"""
alpaca_feed.py
--------------
Real-time US stock data via Alpaca Markets - free API key, free IEX
real-time data feed, free paper trading account, no credit card required
for market data access. This plays the same role Angel One played for
NSE and Binance played for crypto, but for US equities.

NOTE: Alpaca's free data tier uses the IEX feed (one of many US exchanges),
not the full consolidated SIP tape that professional terminals use. IEX
volume is a meaningful subset of total US equity volume but not 100% of
it - fine for retail technical scanning, but be aware "volume" here is
IEX volume, not total US market volume, when interpreting the
volume-above-average condition.

Two pieces:
  - REST /v2/stocks/bars for historical intraday bars - BATCHED across up
    to ~50 symbols per call (a real optimization vs. Angel One/Binance,
    which needed one call per symbol - Alpaca's bars endpoint natively
    accepts a comma-separated symbol list).
  - Websocket (wss://stream.data.alpaca.markets/v2/iex) for live trade
    prices between bar closes.

Verify exact endpoint/param names against https://docs.alpaca.markets
before going live - APIs evolve and this is written against the commonly
documented interface as of early 2026.
"""

import json
import logging
import threading
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

import config

log = logging.getLogger("alpaca_feed")

try:
    import websocket  # from websocket-client package
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False
    log.warning("websocket-client not installed - live tick updates disabled, "
                "falling back to REST-only bar data (still works).")

ALPACA_DATA_BASE = "https://data.alpaca.markets"
ALPACA_TRADING_BASE = "https://paper-api.alpaca.markets"  # paper endpoint - fine for market data/asset lookups
ALPACA_WS_URL = "wss://stream.data.alpaca.markets/v2/iex"

BATCH_SIZE = 50  # symbols per REST call - well under Alpaca's URL length limits


class AlpacaFeed:
    def __init__(self):
        self.valid_symbols = set()
        self.live_price = {}
        self._lock = threading.Lock()
        self.ws = None
        self.ws_thread = None

    def _headers(self):
        return {
            "APCA-API-KEY-ID": config.ALPACA_API_KEY,
            "APCA-API-SECRET-KEY": config.ALPACA_API_SECRET,
        }

    # ------------------------------------------------------------------ #
    # Startup validation - confirms every requested symbol is a real,
    # currently-tradeable US equity on Alpaca before polling it.
    # ------------------------------------------------------------------ #
    def validate_symbols(self, symbols: list) -> list:
        if not config.ALPACA_API_KEY or not config.ALPACA_API_SECRET:
            log.error("[ALPACA] Missing API credentials - cannot validate symbols")
            self.valid_symbols = set()
            return []
        try:
            resp = requests.get(
                f"{ALPACA_TRADING_BASE}/v2/assets",
                headers=self._headers(),
                params={"status": "active", "asset_class": "us_equity"},
                timeout=30,
            )
            resp.raise_for_status()
            assets = resp.json()
            tradable = {a["symbol"] for a in assets if a.get("tradable")}
        except Exception as e:
            log.error(f"[ALPACA] Could not fetch asset list ({e}) - "
                      f"skipping validation, will attempt all requested symbols as-is")
            self.valid_symbols = set(symbols)
            return symbols

        valid = [s for s in symbols if s in tradable]
        invalid = [s for s in symbols if s not in tradable]
        self.valid_symbols = set(valid)

        if invalid:
            log.warning(
                f"[ALPACA] {len(invalid)} symbol(s) are NOT currently active/tradeable "
                f"on Alpaca and will be SKIPPED: {invalid}. Common reasons: ticker changed "
                f"(mergers, rebrands), delisted, or a typo. Fix in bots_config/symbols.json."
            )
        log.info(f"[ALPACA] {len(valid)}/{len(symbols)} symbols validated and active")
        return valid

    # ------------------------------------------------------------------ #
    # Historical bars (REST) - BATCHED across multiple symbols per call.
    # Returns {symbol: DataFrame} for a whole batch in one HTTP round trip.
    # ------------------------------------------------------------------ #
    def get_bars_batch(self, symbols: list, retry: bool = True) -> dict:
        """
        Fetches today's intraday bars for UP TO ~50 symbols in a single
        REST call - a genuine optimization vs. one-request-per-symbol.
        Returns {symbol: DataFrame[timestamp,open,high,low,close,volume]}.
        Symbols with no data are simply absent from the returned dict
        (caller treats missing == empty DataFrame == NO_DATA error).
        """
        if config.DRY_RUN:
            return {s: self._mock_candles(s) for s in symbols}

        try:
            now_et = datetime.now(timezone.utc)
            day_start = now_et.replace(hour=0, minute=0, second=0, microsecond=0)
            params = {
                "symbols": ",".join(symbols),
                "timeframe": config.CANDLE_INTERVAL,
                "start": day_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "end": now_et.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "limit": 1000,
                "adjustment": "raw",
                "feed": "iex",
            }
            resp = requests.get(
                f"{ALPACA_DATA_BASE}/v2/stocks/bars",
                headers=self._headers(), params=params, timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            bars_by_symbol = data.get("bars", {}) or {}

            result = {}
            for sym, bars in bars_by_symbol.items():
                if not bars:
                    continue
                df = pd.DataFrame(bars)
                df = df.rename(columns={"t": "timestamp", "o": "open", "h": "high",
                                         "l": "low", "c": "close", "v": "volume"})
                df = df[["timestamp", "open", "high", "low", "close", "volume"]]
                for col in ["open", "high", "low", "close", "volume"]:
                    df[col] = df[col].astype(float)
                result[sym] = df.sort_values("timestamp").reset_index(drop=True)
            return result

        except Exception as e:
            if retry:
                log.warning(f"[ALPACA] Exception fetching batch, retrying once in 3s: {e}")
                time.sleep(3)
                return self.get_bars_batch(symbols, retry=False)
            log.error(f"[ALPACA] Exception fetching batch after retry: {e}")
            for sym in symbols:
                pass  # caller logs per-symbol NO_DATA when the dict lacks the key
            return {}

    def _mock_candles(self, symbol: str) -> pd.DataFrame:
        import numpy as np
        n = 60
        base = 10 + (hash(symbol) % 500)
        rng = np.random.default_rng(abs(hash(symbol)) % (2**32))
        closes = base + np.cumsum(rng.normal(0, base * 0.005, n))
        highs = closes + rng.uniform(0, base * 0.005, n)
        lows = closes - rng.uniform(0, base * 0.005, n)
        opens = closes - rng.normal(0, base * 0.003, n)
        volumes = rng.integers(1000, 200000, n)
        now = datetime.now(timezone.utc)
        timestamps = [(now - timedelta(minutes=config.SCAN_INTERVAL_MINUTES * (n - i))).isoformat() for i in range(n)]
        return pd.DataFrame({
            "timestamp": timestamps, "open": opens, "high": highs,
            "low": lows, "close": closes, "volume": volumes,
        })

    # ------------------------------------------------------------------ #
    # Live websocket price feed
    # ------------------------------------------------------------------ #
    def start_websocket(self, symbols: list):
        if config.DRY_RUN or not WEBSOCKET_AVAILABLE or not symbols:
            log.info("[ALPACA WS] Websocket not started (DRY_RUN, library missing, or no symbols)")
            return
        if not config.ALPACA_API_KEY or not config.ALPACA_API_SECRET:
            log.error("[ALPACA WS] Missing credentials, websocket not started")
            return

        def on_open(ws):
            log.info("[ALPACA WS] Connected, authenticating...")
            ws.send(json.dumps({
                "action": "auth",
                "key": config.ALPACA_API_KEY,
                "secret": config.ALPACA_API_SECRET,
            }))
            ws.send(json.dumps({"action": "subscribe", "trades": symbols}))
            log.info(f"[ALPACA WS] Subscribed to {len(symbols)} symbols")

        def on_message(ws, message):
            try:
                events = json.loads(message)
                for evt in events:
                    if evt.get("T") == "t":  # trade event
                        sym, price = evt.get("S"), evt.get("p")
                        if sym and price is not None:
                            with self._lock:
                                self.live_price[sym] = float(price)
            except Exception as e:
                log.error(f"[ALPACA WS] on_message error: {e}")

        def on_error(ws, error):
            log.error(f"[ALPACA WS] Error: {error}")

        def on_close(ws, code, msg):
            log.warning(f"[ALPACA WS] Connection closed (code={code}), reconnecting in 5s...")
            time.sleep(5)
            self.start_websocket(symbols)

        self.ws = websocket.WebSocketApp(
            ALPACA_WS_URL, on_open=on_open, on_message=on_message,
            on_error=on_error, on_close=on_close,
        )
        self.ws_thread = threading.Thread(target=self.ws.run_forever, daemon=True)
        self.ws_thread.start()
        log.info("[ALPACA WS] Websocket thread started")

    def get_live_price(self, symbol: str):
        with self._lock:
            return self.live_price.get(symbol)


feed = AlpacaFeed()
