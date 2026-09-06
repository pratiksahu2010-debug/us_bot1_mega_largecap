"""
telegram_notify.py
-------------------
US stock version - USD formatting, US Eastern timestamps.
"""

import logging
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

log = logging.getLogger("telegram")

TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}/sendMessage"
ET = ZoneInfo("America/New_York")


def _fmt_price(p: float) -> str:
    if p >= 1000:
        return f"{p:,.2f}"
    return f"{p:.2f}"


def _send(token: str, chat_id: str, text: str, retries: int = 2) -> str:
    if not token or not chat_id:
        log.warning("[TELEGRAM] Missing token/chat_id - message not sent (DRY RUN?)")
        return ""
    url = TELEGRAM_API_BASE.format(token=token)
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    last_err = None
    for attempt in range(retries + 1):
        try:
            resp = requests.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if data.get("ok"):
                return str(data["result"]["message_id"])
            last_err = data
        except Exception as e:
            last_err = e
        log.warning(f"[TELEGRAM] send attempt {attempt+1} failed: {last_err}")
    log.error(f"[TELEGRAM] All attempts failed: {last_err}")
    return ""


def send_trade_alert(token, chat_id, bot_name, signal_result, symbol) -> str:
    r = signal_result
    now_et = datetime.now(ET).strftime("%Y-%m-%d %H:%M:%S ET")

    text = (
        f"📊 *{bot_name}*\n"
        f"🚨 TRADE ALERT: {symbol}\n"
        f"📈 Signal: {r.direction}\n"
        f"💰 Price: ${_fmt_price(r.price)}\n"
        f"📊 RSI: {r.rsi:.1f} ✅\n"
        f"📈 ADX: {r.adx:.1f} ✅\n"
        f"📉 VWAP: ${_fmt_price(r.vwap)} (MANDATORY ✓)\n"
        f"🔴 9 EMA: ${_fmt_price(r.ema9)}\n"
        f"🟡 21 EMA: ${_fmt_price(r.ema21)}\n"
        f"📊 Volume: {int(r.volume):,} (Above Avg: {'YES' if r.volume > r.vol_avg20 else 'NO'})\n"
        f"📏 Distance from VWAP: {r.vwap_distance_pct:.2f}%\n"
        f"⭐ Confidence: {r.confidence}\n"
        f"🎯 Score: {r.score}/10\n"
        f"⏰ Time: {now_et}"
    )
    return _send(token, chat_id, text)


def send_early_signal(token, chat_id, bot_name, signal_result, symbol) -> str:
    r = signal_result
    now_et = datetime.now(ET).strftime("%Y-%m-%d %H:%M:%S ET")

    text = (
        f"👀 *{bot_name}*\n"
        f"⚡ EARLY MOMENTUM SIGNAL: {symbol}\n"
        f"📈 Building: {r.direction}\n"
        f"💰 Price: ${_fmt_price(r.price)}\n"
        f"📉 VWAP: ${_fmt_price(r.vwap)} (MANDATORY ✓)\n"
        f"📊 RSI: {r.rsi:.1f} | ADX: {r.adx:.1f}\n"
        f"🔴 9 EMA: ${_fmt_price(r.ema9)} | 🟡 21 EMA: ${_fmt_price(r.ema21)}\n"
        f"📏 Distance from VWAP: {r.vwap_distance_pct:.2f}%\n"
        f"🎯 Score: {r.score}/10 (confirmation needs 8+)\n"
        f"🔔 Not yet a confirmed trade - monitor for full setup\n"
        f"⏰ Time: {now_et}"
    )
    return _send(token, chat_id, text)


def send_daily_summary(token, chat_id, bot_name, total_alerts, top_symbols, total_early=None):
    lines = [f"📋 *{bot_name} - DAILY SUMMARY*", f"🚨 Confirmed alerts today: {total_alerts}"]
    if total_early is not None:
        lines.append(f"👀 Early/watch signals today: {total_early}")
    if top_symbols:
        lines.append("🔥 Most active symbols:")
        for sym, count in top_symbols:
            lines.append(f"   • {sym}: {count} alert(s)")
    _send(token, chat_id, "\n".join(lines))


def send_error_summary(token, chat_id, bot_name, total_errors, breakdown):
    lines = [f"⚠️ *{bot_name} - ERROR SUMMARY*", f"Total errors today: {total_errors}"]
    for err_type, count in breakdown:
        lines.append(f"   • {err_type}: {count}")
    if not breakdown:
        lines.append("No errors today ✅")
    _send(token, chat_id, "\n".join(lines))


def send_health_check(token, chat_id, bot_name, symbol_count):
    text = (
        f"🤖 *{bot_name} INITIALIZED*\n"
        f"📊 Monitoring: {symbol_count} symbols\n"
        f"⏰ Schedule: US market hours, Mon-Fri\n"
        f"📋 VWAP: MANDATORY\n"
        f"🔒 Strict Mode: score ≥ 8/10 for confirmed alerts, 6-7/10 for early signals\n"
        f"✅ Bot is LIVE and scanning!"
    )
    _send(token, chat_id, text)
