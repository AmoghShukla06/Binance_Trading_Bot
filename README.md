# Binance Futures Testnet Trading Bot

A clean, production-style Python CLI for placing orders on the [Binance Futures Testnet](https://testnet.binancefuture.com) (USDT-M perpetuals).

---

## Features

| Category | Details |
|---|---|
| **Order types** | MARKET, LIMIT, STOP_MARKET (bonus) |
| **Sides** | BUY, SELL |
| **CLI framework** | Click (interactive prompts, colour output, `--help`) |
| **Auth** | HMAC-SHA256 signed requests |
| **Logging** | Rotating file log (`logs/trading_bot.log`) + coloured console |
| **Error handling** | Validation errors, API errors, network failures |
| **Structure** | Separated client / service / validation / CLI layers |

---

## Project Structure

```
trading_bot/
├── bot/
│   ├── __init__.py
│   ├── client.py          # Binance REST client (signing, session, logging)
│   ├── orders.py          # Order service layer (param building, formatting)
│   ├── validators.py      # Input validation (raises ValueError)
│   └── logging_config.py  # Rotating file + console logging setup
├── cli.py                 # Click CLI entry point
├── logs/                  # Auto-created; contains trading_bot.log
├── requirements.txt
└── README.md
```

---

## Setup

### 1. Get Testnet credentials

1. Register / log in at <https://testnet.binancefuture.com>
2. Go to **API Management** and generate a new API key + secret
3. Keep both values handy for the next step

### 2. Install dependencies

```bash
# Create a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

### 3. Set credentials

**Option A — Environment variables (recommended)**

```bash
export BINANCE_API_KEY="your_api_key_here"
export BINANCE_API_SECRET="your_api_secret_here"
```

**Option B — CLI flags (every command)**

```bash
python cli.py --api-key YOUR_KEY --api-secret YOUR_SECRET place ...
```

---

## How to Run

All commands must be run from inside the `trading_bot/` directory.

```bash
cd trading_bot
```

### Place a MARKET order

```bash
python cli.py place \
  --symbol BTCUSDT \
  --side BUY \
  --type MARKET \
  --quantity 0.001
```

### Place a LIMIT order

```bash
python cli.py place \
  --symbol BTCUSDT \
  --side SELL \
  --type LIMIT \
  --quantity 0.001 \
  --price 80000
```

### Place a STOP_MARKET order (bonus)

```bash
python cli.py place \
  --symbol BTCUSDT \
  --side SELL \
  --type STOP_MARKET \
  --quantity 0.001 \
  --stop-price 75000
```

### View account balances

```bash
python cli.py account
```

### Increase log verbosity

```bash
python cli.py --log-level DEBUG place --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001
```

### Skip interactive confirmation (pipe-friendly)

```bash
echo "y" | python cli.py place --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001
```

---

## CLI Reference

```
Usage: cli.py [OPTIONS] COMMAND [ARGS]...

  Binance Futures Testnet Trading Bot.

Options:
  --api-key TEXT              Binance API key (or BINANCE_API_KEY env var)
  --api-secret TEXT           Binance API secret (or BINANCE_API_SECRET env var)
  --log-level [DEBUG|INFO|WARNING|ERROR]
  --help                      Show this message and exit.

Commands:
  place    Place a new order on Binance Futures Testnet.
  account  Display Binance Futures account balances.
```

#### `place` options

| Flag | Required | Description |
|---|---|---|
| `--symbol` | ✓ | Trading pair, e.g. `BTCUSDT` |
| `--side` | ✓ | `BUY` or `SELL` |
| `--type` | ✓ | `MARKET`, `LIMIT`, or `STOP_MARKET` |
| `--quantity` | ✓ | Order quantity |
| `--price` | LIMIT only | Limit price |
| `--stop-price` | STOP_MARKET only | Stop trigger price |
| `--time-in-force` | No (default GTC) | `GTC`, `IOC`, `FOK` |
| `--reduce-only` | No | Flag – mark as reduce-only |

---

## Logging

Log files are written to `logs/trading_bot.log` (auto-created).  
The file rotates at 5 MB and keeps 3 backups.

Each log entry includes: timestamp, level, logger name, and message.

```
2025-01-01 12:00:00 | INFO     | trading_bot.orders | Placing BUY MARKET order | symbol=BTCUSDT | qty=0.001 | price=N/A | stopPrice=N/A
2025-01-01 12:00:00 | INFO     | trading_bot.client | → POST /fapi/v1/order | params={...}
2025-01-01 12:00:00 | INFO     | trading_bot.client | ← Response OK | status=200
2025-01-01 12:00:00 | INFO     | trading_bot.orders | Order placed successfully | orderId=... | status=NEW | executedQty=0.001 | avgPrice=...
```

Log files from sample testnet orders are included in the `logs/` directory.

---

## Assumptions

- Only USDT-M perpetual futures are targeted (endpoint: `/fapi/v1/order`).
- The testnet does not support all production features (e.g., OCO on futures).
- `timeInForce` is only sent for `LIMIT` orders (Binance rejects it for MARKET).
- Credentials are **never** logged; only non-signature params are recorded.
- `STOP_MARKET` uses Binance's native stop-market order type (stop trigger → market fill).

---

## Error Handling

| Error type | Behaviour |
|---|---|
| Invalid CLI input | Validation message + exit code 1 |
| Binance API error | Error code + message printed in red + exit 1 |
| Network timeout | Clear message + exit 1 |
| Connection failure | Clear message + exit 1 |
| Unexpected exception | Full traceback in log file + short message on screen |
