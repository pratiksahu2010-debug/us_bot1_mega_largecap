# US SMALL-MID CAP & GROWTH BOT

Standalone US stock alert bot - one of three independent deployments.
Same VWAP-mandatory, 10-point scoring, early+confirmed signal system as
the NSE and crypto bots, adapted for US equities.

Not investment advice - a technical screening tool. Backtest before
trusting it with real capital.

## ⚠️ About the data source - please read

You asked for Delta Exchange, but **Delta Exchange doesn't offer US stock
data** - it's an India-based crypto derivatives exchange (BTC/ETH/altcoin
futures and options), not a source for equities like AAPL or MSFT. This
bot uses **Alpaca Markets** instead - free API key, free real-time IEX
data feed, free paper trading account, no card required. It plays the
same role for US stocks that Angel One played for NSE and Binance played
for crypto.

**One data-quality note:** Alpaca's free tier uses the **IEX feed**, one
of several US exchanges, not the full consolidated SIP tape. Volume
figures here are IEX volume, not total US market volume - fine for
technical screening, but keep in mind when interpreting the
volume-above-average condition.

## Setup

**1. Alpaca account (free, no card needed for data):**
   - Sign up at https://alpaca.markets
   - From the dashboard, generate an API Key ID + Secret Key (paper
     trading keys work fine for market data access)
   - These become `ALPACA_API_KEY` and `ALPACA_API_SECRET`

**2. Telegram bot:** same as before - @BotFather → `/newbot` → save
token; message the bot once → `https://api.telegram.org/bot<TOKEN>/getUpdates`
(or message @userinfobot) → get your chat id.

**3. Environment variables on Render:**
```
DRY_RUN=false
TELEGRAM_TOKEN=...
TELEGRAM_CHAT_ID=...
ALPACA_API_KEY=...
ALPACA_API_SECRET=...
```
Start with `DRY_RUN=true` to test the full pipeline against synthetic
data first, with zero Alpaca calls made.

**4. Deploy:** push this folder to its own repo → Render → New Web
Service (or Blueprint via `render.yaml`, service name pre-set to
`us-smallmid-growth-alert-bot`) → Build command `pip install -r requirements.txt` →
Start command `gunicorn main:app --bind 0.0.0.0:$PORT --workers 1
--threads 4 --timeout 120`. Set `PYTHON_VERSION=3.12.7` if deploying
manually.

**5. Verify:**
```
/health           - confirms service up, shows symbol count
/telegram_test    - sends a test message, shows Telegram's raw API response
/status           - full diagnostic: valid Alpaca symbols, recent errors, early+confirmed counts
/trigger?force=true - runs a scan immediately, ignoring market hours (for testing anytime)
```

## Market hours

9:30 AM - 4:00 PM US Eastern, Monday-Friday. The code checks the actual
US Eastern time using Python's `zoneinfo`, correctly handling daylight
saving transitions automatically - no matter what timezone Render's
server itself runs in (typically UTC).

## Optimization: batched data fetching

Unlike the NSE bot (one API call per symbol, rate-limited to 1/second)
this bot fetches **up to 50 symbols in a single HTTP request**, since
Alpaca's bars endpoint natively supports comma-separated multi-symbol
requests. For 120 symbols, that's about 3 requests per scan instead of
120 - meaningfully faster and lighter on rate limits.

## Two-tier alerts

- 🚨 **Confirmed alert** (score 8-10/10) - the full setup
- 👀 **Early/watch signal** (score 6-7/10) - a heads-up that a setup is
  building, before full confirmation, with its own independent 1-hour
  cooldown so it doesn't compete with confirmed-alert cooldowns

VWAP is mandatory for both tiers - no VWAP means no signal of any kind.

## Editing the symbol list

Edit `bots_config/symbols.json` - a flat JSON array of tickers like
`"AAPL"`. If missing, the full built-in list in `config.py` is used
automatically - never a crippled fallback.

## Known limitations

- No persistent disk on Render's free/Starter tier without an add-on -
  `data/alerts.db` resets on redeploy/restart unless you add a paid disk.
- IEX-only data feed (see note above) - not the full consolidated tape.
- No backtesting included - validate the scoring rules against historical
  data before trusting them with capital.
