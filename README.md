# Polymarket Bot | Polymarket Trading Bot | Polymarket Trading Bot - 5 min market | Polymarket Arbitrage Bot

Polymarket Bot, Polymarket Trading Bot, Polymarket 5min market Trading Bot, Polymarket Automatic Trading Bot

A high-performance, automated trading system for [Polymarket](https://polymarket.com) prediction markets. Built in Python with real-time WebSocket streaming, gasless L2 execution, and a risk-management framework suited to short-term and high-frequency environments.



<img width="1058" height="698" alt="image" src="https://github.com/user-attachments/assets/fbe3a09e-e33b-40d7-8eed-d0cfe2f54caa" />



## Contact

| Channel | Link |
|---------|------|
| **Email** | benjamin.bigdev@gmail.com |
| **Telegram** | [@BenjaminCup](https://t.me/BenjaminCup) |
| **X (Twitter)** | [@benjaminccup](https://x.com/benjaminccup) |

---

## If you'd like, I can show you a profitable bot in action through a meeting.

# 1. Polymarket Endcycle Sniper bot (Introduction)

## Recording Video

https://github.com/user-attachments/assets/b038aa3b-e42b-4f72-ac5d-a130cdb56a9f

---
## Running Bot Screenshot

<img width="1796" height="937" alt="github-update-4-" src="https://github.com/user-attachments/assets/6b5f2782-a0f8-4333-9727-7699cd88c839" />

<img width="1796" height="930" alt="github-update-5-" src="https://github.com/user-attachments/assets/13d4b57a-7268-4102-ba28-93017026884f" />

---
## Result Screenshot

<img width="1384" height="895" alt="github-update-1" src="https://github.com/user-attachments/assets/e95f5fd9-df93-4d8f-be58-bee7568619c0" />

<img width="1489" height="920" alt="github-update-3" src="https://github.com/user-attachments/assets/33237de3-cd03-4a27-9c78-13455b925572" />

---
## Telegram Trial Version Bot
You can also test the bot directly on Telegram.

<img width="457" height="273" alt="image" src="https://github.com/user-attachments/assets/8f3035da-67d2-4182-9e66-8959e0bb7574" />

https://github.com/user-attachments/assets/4b9d029d-8e20-460b-af72-48412934293f

https://t.me/benjamin_polymarket_trading_bot

---
# 2. Polymarket Copy Trading Bot (Introduction)
An open-source bot that automatically copies trades from top Polymarket traders to your wallet—so you can follow proven strategies 24/7 without watching the market yourself.

Whether you're new to prediction markets or you want to scale your copy-trading across multiple wallets, this bot is built to be **simple to run**, **transparent**, and **under your control**.

https://github.com/user-attachments/assets/1bf1babc-8aa6-4be0-b1ec-4e193f52b965



# 3. Polymarket Ladder Trading Bot (Introduction)
This bot does not speculate on market direction.
Instead, it captures spread by selling both YES and NO outcome tokens at prices whose combined value exceeds $1.
The strategy focuses on market making, not directional trading.
<img width="1098" height="727" alt="image" src="https://github.com/user-attachments/assets/69f7c1d7-20c6-4b30-928b-5df382795c8a" />


https://github.com/user-attachments/assets/7ba03ed4-f00d-4564-bf78-67c5159bb5c3

<img width="1803" height="861" alt="polymarket-trading-ladder-bot-pnl" src="https://github.com/user-attachments/assets/6b9c55c5-f822-46ff-b956-ec9939736653" />


---
---
# 1. Polymarket Endcycle Sniper bot (Explain)

## **🚀 Key Features**

* **Signal + Execution Pipeline**: Combines real-time orderbook + spot prices vs strike → generates UP/DOWN signals → executes optionally.
* **Buy-Above Strategy**: Enter momentum trades when an outcome is expensive (`YES > threshold`) with risk exit and optional hedge.
* **Buy-Opposite Strategy**: Contrarian trades when one side spikes (`> threshold`) → buys the other outcome.
* **Multi-Asset Support**: Run BTC, ETH, SOL, XRP simultaneously.
* **Configurable & Extensible**: YAML + environment variable overrides (`POLYBOT5M_*`).
* **Redeem Automation**: Auto redeem positions after resolution using Builder relayer (gasless).

---

## **📊 How It Works**

### 1. **Main Pipeline (`polybot5m run`)**

Generates UP/DOWN signals every 5 minutes using:

1. **Market Discovery**: Finds active 5-minute slug (e.g., `btc-updown-5m-{epoch_ts}`) → fetches `condition_id` & asset IDs via Gamma API.
2. **Orderbook Capture**: Uses CLOB WebSocket → stores in memory for analysis.
3. **Price History**: Rolling midpoint (bid+ask)/2 over tracking window (default 60s).
4. **Reference Price**: Real-time spot from Coinbase or Binance; optional strike price scrape.
5. **Signal Engine**: Compares first-half vs second-half midpoint averages → predicts **UP** or **DOWN**.
6. **Optional Execution**: Market or limit buy at best ask per asset if credentials and `execution.enabled`.

**Flow Diagram (simplified)**:

```
Market Discovery → CLOB Orderbook → Price History → Spot vs Strike → Signal Engine → Execute
```

---

### 2. **Buy-Above Strategy (`scripts/run_5m_core.py`)**

* **Trigger**: When `best_ask > threshold` (e.g., 0.95) → market buy YES.
* **Risk Management**: Optional stop-loss (`sell_on_drop`) and hedge (`hedge_on_risk`).
* **Redeem**: Auto redeem after resolution with `redeem_delay_seconds`.
* **Multi-Cycle**: Supports multiple assets and epochs in parallel.

---

### 3. **Buy-Opposite Strategy (`scripts/test_buy_opposite_098.py`)**

* **Trigger**: When one outcome spikes above threshold (e.g., >0.98), buy the **other** outcome.
* **Use Case**: Profits from mean reversion when price spikes are temporary.
* **Multi-Cycle**: Repeat for multiple assets and epochs.

---

## **🗂 Project Layout**

```
polymarket-trading-bot-5m-v4/
├── config/
│   └── default.yaml          # All configs: bot, api, markets, entry, risk, execution, buy_above, buy_opposite
├── src/polybot5m/
│   ├── cli.py                # Main run
│   ├── entry/engine.py       # Signal computation
│   ├── data/                 # APIs, WS, orderbook, price_diff, scrape
│   └── execution/            # CLOB client, executor, redeem
├── scripts/
│   ├── run_5m_core.py        # Buy-above
│   ├── test_buy_opposite_098.py  # Buy-opposite
│   ├── run_until_resolution.py   # Full cycle
│   └── step01-12_*.py        # Step-by-step tests
└── exports/                  # Logs & activity JSONL
```

---

## **⚙ Configuration (High-Level)**

| Section             | Purpose                                                |
| ------------------- | ------------------------------------------------------ |
| **bot**             | `dry_run`, `log_level`                                 |
| **api**             | Gamma & CLOB URLs                                      |
| **markets**         | Enabled assets & intervals                             |
| **entry**           | Signal sampling, tracking window, confidence threshold |
| **risk**            | Stop-loss %, max positions                             |
| **execution**       | API keys, private key, order type, buy/sell style      |
| **buy_above**       | Threshold, amount, cycles, risk, hedge                 |
| **buy_opposite**    | Threshold, amount, offset, cycles                      |
| **reference_price** | Coinbase/Binance, optional strike scrape               |

> ⚡ **Tip**: Override any config with `POLYBOT5M_*` environment variables.

---

## **💰 How It Can Make Money**

1. **Main Run**: Predicts 5-minute market outcomes better than average → executes trades.
2. **Buy-Above**: Exploits momentum when YES price is high; profits if outcome wins more often than implied by price.
3. **Buy-Opposite**: Profits from mean-reversion on price spikes.

> ⚠️ **Risk Note**: All strategies are directional speculation. Losses can occur if prediction is wrong or price slips.

---

## **🏁 Beginner Workflow (WORKFLOW_BEGINNER.md)**

1. **Setup**:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e .
   ```

   Optional: Playwright for strike scraping.

2. **Verify Config**: Run step scripts (`step01_config.py`, `step02_slug.py`) without network keys.

3. **Dry-Run Main Pipeline**:

   ```bash
   .venv/bin/polybot5m run --dry-run
   .venv/bin/python scripts/run_until_resolution.py --cycles 1
   ```

4. **Dry-Run Strategy Scripts**:

   ```bash
   .venv/bin/python scripts/run_5m_core.py --dry-run --cycles 1
   .venv/bin/python scripts/test_buy_opposite_098.py --dry-run --cycles 1
   ```

5. **Add Credentials**: `.env` file with CLOB & Builder keys for execution/redeem.

6. **First Live Run**: Start with `dry_run=False`, small amount, one cycle → verify signals and execution.

> 📌 **Quick Reference Table**: Install → signals → dry-run strategies → add credentials → first live run.

---

## **💻 Running It**

```bash
# Main pipeline
.venv/bin/polybot5m run
.venv/bin/polybot5m -c config/default.yaml run

# Buy-above strategy
.venv/bin/python scripts/run_5m_core.py --dry-run --cycles 1

# Buy-opposite strategy
.venv/bin/python scripts/test_buy_opposite_098.py --dry-run --cycles 5

# Full cycle until resolution
.venv/bin/python scripts/run_until_resolution.py
```

> Ensure API keys and private key are set for execution; redeem uses Builder relayer keys.

---

## **📌 Summary**

| Aspect            | polymarket-trading-bot-5m-v4                                         |
| ----------------- | -------------------------------------------------------------------- |
| **Role**          | Signal + execution bot for 5m crypto UP/DOWN markets                 |
| **Main Run**      | Orderbook + spot vs strike → UP/DOWN signal → optional execution     |
| **Strategies**    | Buy-above (momentum + risk exit), Buy-opposite (contrarian)          |
| **Markets**       | BTC, ETH, SOL, XRP (configurable)                                    |
| **Data Sources**  | Gamma, CLOB WS, Coinbase/Binance WS, optional strike scrape          |
| **Config**        | YAML + `POLYBOT5M_*` env overrides                                   |
| **Beginner Path** | Clone → setup → dry-run → try strategies → add keys → first live run |

# 2. Polymarket Copy Trading Bot (Explain)

## ✨ Why use this bot?

- **Real copy trading** — Mirrors every trade from the proxy wallets you choose (buy, sell, merge).
- **Your keys, your rules** — Runs on your machine with your wallet; no custody, no middleman.
- **Flexible sizing** — Copy by **percentage** of the trader’s order, or a **fixed USD amount** per trade.
- **Multi-wallet** — Run one executor and copy into several follower wallets at once.
- **Monitor + Executor** — Run a **monitor** (sleuth) to watch traders and fill the DB, and a separate **executor** to place orders (great for scaling or separating concerns).
- **PnL at a glance** — Check copy-trading performance with `npm run check-copy-pnl`.
- **Preview mode** — Dry-run: see what *would* be traded without sending real orders.
---
## 🏗️ How it works

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Trade Monitor   │────▶│     MongoDB      │◀────│ Trade Executor   │
│  (sleuth)        │     │  (pending trades)│     │ (places orders)   │
│  • Polls API     │     │                  │     │ • Validates       │
│  • Saves trades  │     │                  │     │ • Copy % or $     │
└──────────────────┘     └──────────────────┘     │ • Multi-wallet   │
        │                          │               └────────┬─────────┘
        │                          │                        │
        ▼                          ▼                        ▼
  Polymarket API            Your config              Polymarket CLOB
  (activity, positions)      (COPY_STRATEGY, etc.)    (orders)
```

- **Monitor** fetches target traders’ activity and positions, deduplicates, and stores new trades.
- **Executor** reads pending trades, applies your copy strategy (percentage or fixed size), validates balance/positions, and posts orders for each follower wallet.
- You can run **monitor** and **executor** together (`npm run dev`) or **separately** (`npm run monitor` + `npm run executor`).

---

## 📊 PnL and monitoring

- **Copy-trading PnL** — Run `npm run check-copy-pnl` to see value, initial cost, unrealized/realized PnL, and position count for your follower wallet(s). Data comes from the Polymarket positions API.
- **Logs** — The bot logs trades, balance checks, and errors; use your normal process (e.g. `logs/` directory, PM2, Docker logs) to monitor.

---

## 🔒 Security and safety

- **Private keys** — Stored only in your `.env`; never committed. Use a dedicated wallet with limited funds.
- **Preview mode** — Use `PREVIEW_MODE=true` to test without sending orders.
- **Limits** — `MAX_ORDER_SIZE_USD`, `MIN_ORDER_SIZE_USD`, and optional `MAX_POSITION_SIZE_USD` / `MAX_DAILY_VOLUME_USD` help cap risk.

---


# 3. Polymarket Ladder Trading Bot (5m / 15m / 1h / 4h / 1d crypto Up/Down markets) (Explain)

## Overview

Polymarket trading bot is designed to provide automated liquidity in Polymarket prediction markets.

## Bot Workflow

## 🔄 Polymarket Bot Workflow

<table>
<tr>
<td>

**1. Split collateral**

Divide USDC into YES/NO outcome tokens.

**2. Pair selling**

Sell both YES and NO tokens simultaneously.

**3. Market resolution**

Wait until the prediction market resolves.

**4. Redeem**

Redeem the winning tokens for collateral.

</td>

<td>

<img src="https://github.com/user-attachments/assets/565fd7a8-db16-4799-ae8f-77d9fc6226d4" width="500">

</td>
</tr>
</table>
Profit is generated from spread capture, where the bot sells both outcomes at prices that sum to greater than $1.

## Strategy Concept

When a market is created on Polymarket:

- YES token = pays $1 if event happens

- NO token = pays $1 if event does not happen

### The bot:

Converts USDC.e into YES + NO tokens

Sells both tokens

Ensures the sum of prices ≥ target spread

Example:
| Token | Sell Price |
| ----- | ---------- |
| YES   | 0.54       |
| NO    | 0.49       |


Total received:

```
0.54 + 0.49 = 1.03
```

Cost to create pair:

```
1.00
```

Profit before fees:

```
1.03 - 1.00 = 0.03 per pair
```
Typical range:

```
Total received ≈ 1.03 – 1.10
```

After the market resolves:

* One token becomes **$1**
* The other becomes **$0**

The bot redeems the winning token.

---

# Strategy Flow

The bot runs a **state machine** cycle:

```
IDLE
  ↓
SPLIT
  ↓
PAIR_SELL
  ↓
MONITOR
  ↓
REDEEM
  ↓
IDLE
```

### Phase Explanation

| Phase     | Description                                |
| --------- | ------------------------------------------ |
| SPLIT     | Convert USDC.e into YES and NO tokens      |
| PAIR_SELL | Sell YES and NO tokens in sequential pairs |
| MONITOR   | Wait for market resolution                 |
| REDEEM    | Redeem winning tokens for USDC.e           |

---

# Pair Selling Logic

The bot sells tokens **in pairs** rather than all at once.


<table>
<tr>
<td>
### For every pair:
  
**1. Fetch orderbook**

**2. Read best bid prices**

**3. Compute optimal sell prices**

**4. Place YES and NO limit orders**

**5. Wait until both fill**

**6. Retry if timeout occurs**

</td>

<td>

<img width="1096" height="718" alt="image" src="https://github.com/user-attachments/assets/12bb8ba0-cf26-422e-942b-b6e9e1961565" />

</td>
</tr>
</table>

---

## Dynamic Pricing

Sell prices are calculated using:

```
yes_price = best_bid_yes + spread
no_price  = best_bid_no  + spread
```

Then the bot enforces:

```
yes_price + no_price ≥ min_pair_sum
```

Example configuration:

```
best_bid_yes = 0.49
best_bid_no  = 0.50
spread       = 0.01
```

Calculated:

```
yes_price = 0.50
no_price  = 0.51
sum = 1.01
```

If `min_pair_sum = 1.03`, the bot increases both prices proportionally.
### If running continuously
| Markets       | Cycles per hour | Hourly Profit |
| ------------- | --------------- | ------------- |
| 1 market (5m) | 12              | ~$36          |
| 2 markets     | 12              | ~$72          |
| 4 markets     | 12              | ~$144         |




```
polymarket-trading-ladder-bot
│
├── config
│   ├── default.yaml
│   └── paper.yaml
│
├── src/polybot5m
│
│   ├── cli.py
│   ├── config.py
│   ├── constants.py
│   ├── engine.py
│
│   ├── data
│   │   ├── gamma.py
│   │   └── slug_builder.py
│
│   └── execution
│       ├── clob_client.py
│       ├── executor.py
│       ├── split.py
│       └── redeem.py
│
└── exports
    └── liquidity_maker_activity.json
```

---

# Configuration

Main configuration file:

```
config/default.yaml
```

Example:

```yaml
liquidity_maker:
  portfolio_allocation_usdc: 100

  pair_size: 5
  min_pair_sum: 1.03

  price_follow_spread: 0.01

  pair_sell_timeout_seconds: 300
  order_check_interval_seconds: 5

  redeem_delay_seconds: 10
  stagger_delay_seconds: 2
```

---

# Important Parameters

| Parameter                    | Description                 |
| ---------------------------- | --------------------------- |
| portfolio_allocation_usdc    | USDC used per market cycle  |
| pair_size                    | Shares per YES/NO pair      |
| min_pair_sum                 | Minimum combined sell price |
| price_follow_spread          | Price offset above best bid |
| pair_sell_timeout_seconds    | Cancel orders if not filled |
| order_check_interval_seconds | Poll order status           |

---

# Supported Markets

Designed for **short-term Polymarket crypto markets**:


| Asset | 5m | 15m | 1h | 4h | 1d |
|------|------|------|------|------|------|
| BTC | ✅ | ✅ | ✅ | ✅ | ✅ |
| ETH | ✅ | ✅ | ✅ | ✅ | ✅ |
| SOL | ✅ | ✅ | ✅ | ✅ | ✅ |
| XRP | ✅ | ✅ | ✅ | ✅ | ✅ |

Slug format:

```
{symbol}-updown-{interval}-{epoch_timestamp}
```

Example:

```
btc-updown-5m-1709916600
```

---

# Run Modes

## Paper Trading (Recommended First)

Uses **real orderbook data** but **no real trades**.

```
polybot5m -c config/paper.yaml run
```

or

```
polybot5m run --dry-run
```

---

## Live Trading

Example:

```
polybot5m run --cycles 1 --allocation 10
```

Meaning:

* run one cycle
* allocate **$10 per market**

---

## Custom Run

```
polybot5m run \
  --allocation 500 \
  --cycles 5
```

---

# Environment Variables

Required for **live trading**.

```
PRIVATE_KEY=
FUNDER=

API_KEY=
API_SECRET=
API_PASSPHRASE=
```

Optional builder relayer keys:

```
BUILDER_API_KEY_1=
BUILDER_API_SECRET_1=
BUILDER_API_PASSPHRASE_1=
```

Multiple keys can be used to avoid rate limits.

---

# Activity Logs

Trading activity is exported to:

```
exports/liquidity_maker_activity.json
```

Example record:

```json
{
  "market": "btc-updown-5m",
  "action": "pair_sell",
  "yes_price": 0.52,
  "no_price": 0.51,
  "size": 5,
  "timestamp": 1709916600
}
```

---

# Summary

| Feature       | Description                |
| ------------- | -------------------------- |
| Strategy      | Liquidity market making | Ladder Sell Logic   |
| Profit source | Spread capture             |
| Market type   | Polymarket 5m / 15m / 1h / 4h / 1d crypto |
| Language      | Python / Rust              |
| APIs          | Gamma API + CLOB API       |
| Execution     | Builder Relayer            |

---



