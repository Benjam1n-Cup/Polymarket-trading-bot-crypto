# Polymarket Arbitrage Bot - Product Requirements Document

## Executive Summary

This document outlines the requirements for building an automated arbitrage trading bot for Polymarket, a decentralized prediction market platform. The MVP focuses on **pure arbitrage** - buying YES + NO tokens when their combined price is less than $1, guaranteeing risk-free profit regardless of outcome.

---

## Table of Contents

1. [Market Context](#market-context)
2. [Strategy Deep Dive](#strategy-deep-dive)
3. [Technical Architecture](#technical-architecture)
4. [MVP Scope](#mvp-scope)
5. [API Integration](#api-integration)
6. [Implementation Phases](#implementation-phases)
7. [Risk Analysis](#risk-analysis)
8. [Success Metrics](#success-metrics)

---

## Market Context

### How Polymarket Works

Polymarket is a prediction market where users trade on outcomes of real-world events. Each market has binary outcomes (YES/NO), and each outcome is represented by an ERC-1155 token on Polygon.

**Key Mechanics:**
- YES token + NO token always resolve to $1.00 total (one wins, one loses)
- Tokens trade between $0.00 and $1.00
- When market resolves, winning tokens pay $1.00, losing tokens pay $0.00
- Trading uses USDC on Polygon blockchain

### The Arbitrage Opportunity

In efficient markets, YES + NO prices should equal ~$1.00 (minus fees). However, due to:
- Market volatility (especially crypto markets with 15-min resolution)
- Latency between traders
- Liquidity imbalances
- Information asymmetry

...prices temporarily diverge, creating arbitrage windows.

**Example:**
```
YES price: $0.48
NO price:  $0.49
Total:     $0.97

Action: Buy $100 YES + $100 NO = $97 spent
Outcome: One token pays $100, other pays $0
Profit: $100 - $97 = $3 (3.09% return)
```

---

## Strategy Deep Dive

### Strategy 1: Pure Arbitrage (MVP)

**Concept:** Simultaneously buy YES and NO tokens when combined price < $1.00

**Profit Formula:**
```
Profit = (1 - YES_price - NO_price) × trade_size - fees
```

**Requirements:**
- Combined price < $0.99 (accounting for ~1% fees)
- Sufficient liquidity on both sides
- Fast execution before prices correct

**Target Markets:**
- High-volume markets (>$100k daily volume)
- Fast-resolving markets (crypto prices, sports)
- Markets with active trading creating price movement

**Expected Returns:**
- Per-trade profit: 0.5-3%
- Trade frequency: 10-100 per day (depends on market conditions)
- Monthly return potential: 5-30% on capital

### Strategy 2: Statistical Arbitrage (Future)

**Concept:** Find correlated markets that should move together

**Example:**
- "Trump wins presidency" at 55%
- "GOP wins Senate" at 45%

These are correlated - if Trump wins, GOP Senate is more likely. When correlation breaks:
- Short the relatively expensive market
- Long the relatively cheap market
- Close when they converge

### Strategy 3: Cross-Platform Arbitrage (Future)

**Concept:** Price differences between Polymarket and other platforms (Binance predictions, Kalshi, etc.)

---

## Technical Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        ARBITRAGE BOT                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   Scanner    │───▶│   Analyzer   │───▶│   Executor   │      │
│  │              │    │              │    │              │      │
│  │ • Poll APIs  │    │ • Calc arb   │    │ • Place orders│     │
│  │ • Track bids │    │ • Check liq  │    │ • Monitor fill│     │
│  │ • Watch asks │    │ • Risk check │    │ • Log trades  │     │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│         │                   │                   │               │
│         ▼                   ▼                   ▼               │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                     Data Layer                              ││
│  │  • Market cache  • Position tracking  • Trade history       ││
│  └─────────────────────────────────────────────────────────────┘│
│                              │                                  │
└──────────────────────────────│──────────────────────────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        ▼                      ▼                      ▼
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│  Gamma API   │      │   CLOB API   │      │   Polygon    │
│              │      │              │      │   Network    │
│ • Markets    │      │ • Orderbook  │      │              │
│ • Metadata   │      │ • Orders     │      │ • Settlement │
│ • Events     │      │ • Trades     │      │ • Wallet     │
└──────────────┘      └──────────────┘      └──────────────┘
```

### Component Details

#### 1. Scanner Module
- Real-time WebSocket streaming (6 parallel connections)
- Each connection handles up to 500 assets (250 markets)
- Monitors up to 1,500 markets simultaneously
- Filters by liquidity ($10k+ default) and resolution date (7 days default)

#### 2. Analyzer Module
- Calculates arbitrage opportunities in real-time
- Checks: `best_ask_yes + best_ask_no < threshold`
- Validates sufficient liquidity at target prices
- Applies risk filters (max position, market health)

#### 3. Executor Module
- **Async CLOB client** with native async HTTP (httpx + HTTP/2)
- Native EIP-712 order signing (~7ms per order)
- Parallel order submission for YES/NO pairs
- Connection pooling for reduced latency
- Monitors fill status with async status checks
- 10-second timeout with auto-cancellation

#### 4. Data Layer
- SQLite/PostgreSQL for trade history
- In-memory cache for real-time data
- Position tracking per market
- P&L calculations

---

## MVP Scope

### MVP Features (Phase 1) ✅ Implemented

| Feature | Priority | Status | Description |
|---------|----------|--------|-------------|
| Market Scanner | P0 | ✅ | Real-time WebSocket price monitoring |
| Arbitrage Detection | P0 | ✅ | Identify YES+NO < threshold opportunities |
| Order Execution | P0 | ✅ | Place orders with 10s timeout + auto-cancel |
| Position Tracking | P0 | ✅ | Track open positions per market |
| Basic Logging | P0 | ✅ | Structured logging with structlog |
| Configuration | P1 | ✅ | Environment variable configuration |
| Dry Run Mode | P1 | ✅ | Simulate trades without execution |
| Trade History | P1 | ✅ | SQLite storage of all trades |
| Slack Alerts | P2 | ✅ | Notifications for trades/errors |
| Web Dashboard | P2 | ✅ | Real-time monitoring with order visibility |
| Order Monitoring | P1 | ✅ | Track order status, fills, cancellations |
| Resolution Filtering | P1 | ✅ | Skip markets resolving beyond N days |

### MVP Non-Goals

- Statistical arbitrage
- Machine learning models
- Copy trading
- High-frequency market making

---

## API Integration

### Polymarket API Ecosystem

#### 1. Gamma Markets API
**Base URL:** `https://gamma-api.polymarket.com`

**Key Endpoints:**
```
GET /markets                    # List all markets
GET /markets/{id}               # Single market details
GET /markets?active=true        # Active markets only
GET /events                     # Event groupings
```

**Response Structure:**
```json
{
  "id": "0x...",
  "question": "Will BTC exceed $100k by Dec 31?",
  "outcomes": ["Yes", "No"],
  "outcomePrices": ["0.65", "0.35"],
  "volume": "1500000",
  "liquidity": "250000",
  "endDate": "2024-12-31T00:00:00Z",
  "active": true,
  "closed": false,
  "tokens": [
    {"outcome": "Yes", "token_id": "12345..."},
    {"outcome": "No", "token_id": "67890..."}
  ]
}
```

#### 2. CLOB (Central Limit Order Book) API
**Base URL:** `https://clob.polymarket.com`

**Key Endpoints:**
```
GET /book                       # Orderbook for a token
GET /markets                    # Market info with token IDs
GET /price                      # Current prices
POST /order                     # Place order (signed)
DELETE /order/{id}              # Cancel order
GET /orders                     # User's open orders
GET /trades                     # User's trade history
```

**Orderbook Response:**
```json
{
  "market": "0x...",
  "asset_id": "12345...",
  "bids": [
    {"price": "0.48", "size": "1000"},
    {"price": "0.47", "size": "2500"}
  ],
  "asks": [
    {"price": "0.49", "size": "800"},
    {"price": "0.50", "size": "1500"}
  ]
}
```

**Order Placement:**
```json
POST /order
{
  "order": {
    "salt": "random_nonce",
    "maker": "0xYourAddress",
    "signer": "0xYourAddress",
    "taker": "0x0000...",
    "tokenId": "12345...",
    "makerAmount": "100000000",  // USDC (6 decimals)
    "takerAmount": "200000000",  // Outcome tokens
    "side": "BUY",
    "expiration": "0",
    "nonce": "0",
    "feeRateBps": "0",
    "signatureType": 2
  },
  "signature": "0x...",
  "owner": "0xYourAddress"
}
```

#### 3. Data API
**Base URL:** `https://data-api.polymarket.com`

```
GET /markets/{id}/history       # Price history
GET /markets/{id}/trades        # Recent trades
GET /activity                   # Platform activity
```

### Authentication

CLOB API uses **L2 Authentication** via the `py-clob-client` library:

1. Generate API credentials from your wallet:
   ```python
   from py_clob_client.client import ClobClient
   client = ClobClient('https://clob.polymarket.com', key=private_key, chain_id=137)
   creds = client.create_or_derive_api_creds()
   # Returns: api_key, api_secret, api_passphrase
   ```

2. Use credentials for all API requests:
   - `POLY_API_KEY` - API key
   - `POLY_API_SECRET` - API secret
   - `POLY_API_PASSPHRASE` - API passphrase

3. ClobClient handles order signing (EIP-712) automatically

**Note:** API credentials are derived from your wallet and can be regenerated anytime.

---

## Implementation Phases

### Phase 1: Foundation (MVP)

#### 1.1 Project Setup
- [ ] Initialize Python project with Poetry/pip
- [ ] Set up configuration management (env vars, config files)
- [ ] Implement logging infrastructure
- [ ] Create basic project structure

#### 1.2 API Client
- [ ] Gamma API client (market discovery)
- [ ] CLOB API client (orderbook, orders)
- [ ] Rate limiting and error handling
- [ ] Response parsing and validation

#### 1.3 Wallet Integration
- [ ] Web3.py integration for Polygon
- [ ] EIP-712 signing for orders
- [ ] USDC balance checking
- [ ] Transaction monitoring

#### 1.4 Scanner
- [ ] Market polling loop
- [ ] Orderbook caching
- [ ] Configurable polling interval
- [ ] Market filtering (volume, liquidity)

#### 1.5 Arbitrage Detection
- [ ] Calculate YES + NO spreads
- [ ] Check liquidity depth at target prices
- [ ] Apply minimum profit threshold
- [ ] Generate trade signals

#### 1.6 Order Execution
- [ ] Order construction
- [ ] Order signing
- [ ] Simultaneous YES + NO placement
- [ ] Fill monitoring and confirmation

#### 1.7 Position Management
- [ ] Track open positions
- [ ] Calculate unrealized P&L
- [ ] Handle market resolution
- [ ] Position limits

### Phase 2: Robustness

- [ ] Retry logic for failed orders
- [ ] Partial fill handling
- [ ] Network error recovery
- [ ] Database persistence
- [ ] Graceful shutdown

### Phase 3: Monitoring

- [ ] Telegram bot integration
- [ ] Performance metrics
- [ ] Error alerting
- [ ] Daily summary reports

### Phase 4: Optimization

**Completed:**
- [x] Reduce latency (async CLOB client with httpx + HTTP/2)
- [x] Connection pooling for order submission
- [x] Parallel order signing (thread pool for CPU-bound EIP-712)

**High Impact (Future):**
- [ ] Pre-signed order templates (~7ms savings per order)
  - Pre-sign orders for hot markets at multiple price points
  - When opportunity appears, select nearest template and submit immediately
- [ ] Parallel YES/NO signing in submit flow
  - Sign both orders concurrently before posting both
- [ ] WebSocket order book maintenance
  - Maintain local order book state from deltas
  - Detect opportunities without additional API calls

**Medium Impact (Future):**
- [ ] ProcessPoolExecutor for signing (avoid GIL contention)
- [ ] Connection warming (periodic pings to keep HTTP/2 alive)
- [ ] Market prioritization scoring (track historical arbitrage frequency)
- [ ] Smart order sizing based on liquidity

**Lower Impact (Future):**
- [ ] DNS caching optimization
- [ ] TCP tuning (TCP_NODELAY, buffer sizes)
- [ ] Memory pre-allocation for order structures
- [ ] Backtesting framework

---

## Risk Analysis

### Technical Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| API rate limiting | Medium | Implement backoff, cache aggressively |
| Order execution latency | High | Use fastest endpoints, minimize processing |
| Partial fills | Medium | Handle gracefully, track exposure |
| Network congestion | Medium | Monitor gas prices, use priority fees |
| API changes | Low | Version API clients, monitor changelogs |

### Financial Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Slippage | High | Check orderbook depth, use limit orders |
| One-sided execution | High | Atomic execution or immediate hedge |
| Capital lockup | Medium | Set position limits per market |
| Smart contract risk | Low | Use official Polymarket contracts only |

### Operational Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Bot downtime | Medium | VPS with monitoring, auto-restart |
| Wallet compromise | Critical | Use dedicated wallet, limit funds |
| Market manipulation | Low | Avoid thin markets, set min liquidity |

### Edge Cases to Handle

1. **Market resolution during trade:** Check market status before execution
2. **Price moves between detection and execution:** Re-validate before placing
3. **Insufficient balance:** Pre-check USDC and token balances
4. **Duplicate orders:** Track pending orders, implement idempotency
5. **Gas price spikes:** Set max gas limits, pause during spikes

---

## Success Metrics

### MVP Success Criteria

| Metric | Target |
|--------|--------|
| Successful arbitrage trades | >10 per day |
| Trade success rate | >90% |
| Average profit per trade | >0.5% |
| System uptime | >99% |
| Max drawdown | <5% of capital |

### KPIs to Track

**Trading Metrics:**
- Total trades executed
- Win rate (profitable vs unprofitable)
- Average profit per trade
- Total volume traded
- Fees paid

**Operational Metrics:**
- API response times
- Order fill rates
- System uptime
- Error frequency

**Financial Metrics:**
- Total P&L (realized + unrealized)
- ROI on capital deployed
- Sharpe ratio
- Max drawdown

---

## Tech Stack

### Core
- **Language:** Python 3.11+
- **Async:** asyncio + aiohttp
- **Blockchain:** web3.py
- **Database:** SQLite (MVP) → PostgreSQL (scale)

### Dependencies
```
aiohttp          # Async HTTP client (WebSocket)
httpx            # Async HTTP client (order execution, HTTP/2)
web3             # Ethereum/Polygon interaction
eth-account      # Wallet and signing (EIP-712)
py-clob-client   # Polymarket L2 API client (fallback)
python-dotenv    # Configuration
structlog        # Structured logging
sqlite3          # Trade storage (built-in)
fastapi          # Dashboard web framework
uvicorn          # ASGI server
```

### Infrastructure
- **Runtime:** EU-based VPS (Polymarket blocks US IPs)
- **Monitoring:** Web dashboard + Slack alerts
- **Deployment:** Docker container or systemd service

---

## Configuration

### Environment Variables
```bash
# Wallet
PRIVATE_KEY=0x...
WALLET_ADDRESS=0x...

# Polymarket L2 API Credentials (generate with py-clob-client)
POLY_API_KEY=...
POLY_API_SECRET=...
POLY_API_PASSPHRASE=...

# Network
POLYGON_RPC_URL=https://polygon-rpc.com
CHAIN_ID=137

# Trading
MIN_PROFIT_THRESHOLD=0.005      # 0.5% minimum profit
MAX_POSITION_SIZE=100           # Max $100 per trade
MIN_LIQUIDITY_USD=10000         # $10k minimum market liquidity
MAX_DAYS_UNTIL_RESOLUTION=7     # Skip markets resolving later
NUM_WS_CONNECTIONS=6            # WebSocket connections (250 markets each)
DRY_RUN=true                    # Set to false for live trading

# Dashboard (optional - omit password for no auth)
DASHBOARD_USERNAME=admin
DASHBOARD_PASSWORD=...

# Alerts
SLACK_WEBHOOK_URL=...
```

### Contract Approvals

Before trading, approve Polymarket contracts to spend USDC.e:

```bash
python scripts/approve_usdc.py
```

Required approvals:
- **CTF Exchange** (`0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E`) - ERC20 + ERC1155
- **Neg Risk Exchange** (`0xC5d563A36AE78145C45a50134d48A1215220f80a`) - ERC20 + ERC1155
- **Neg Risk Adapter** (`0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296`) - ERC20

After approvals, sync with Polymarket:
```python
client.update_balance_allowance()
```

---

## File Structure

```
rarb/
├── src/rarb/
│   ├── __init__.py
│   ├── bot.py                  # Main bot entry point
│   ├── config.py               # Configuration loading
│   ├── api/
│   │   ├── gamma.py            # Gamma API client
│   │   ├── websocket.py        # WebSocket client
│   │   └── models.py           # API response models
│   ├── scanner/
│   │   └── realtime_scanner.py # WebSocket price monitoring
│   ├── analyzer/
│   │   └── arbitrage.py        # Opportunity detection
│   ├── executor/
│   │   ├── executor.py         # Order execution + monitoring (with SOCKS5 proxy)
│   │   └── async_clob.py       # Async CLOB client (httpx + EIP-712 signing)
│   ├── dashboard/
│   │   ├── app.py              # FastAPI dashboard
│   │   └── templates/
│   │       └── dashboard.html  # Dashboard UI
│   ├── tracking/
│   │   ├── portfolio.py        # Balance tracking
│   │   └── trades.py           # Trade history
│   └── utils/
│       └── logging.py          # Logging setup
├── scripts/
│   ├── approve_usdc.py         # Contract approval script
│   └── check_wallet.py         # Wallet balance checker
├── infra/
│   ├── opentofu/               # Infrastructure provisioning
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   └── ansible/                # Server configuration
│       ├── playbooks/
│       └── roles/
├── tests/
├── .env.example
├── pyproject.toml
├── README.md
└── PRD.md
```

---

## Appendix

### A. Polymarket Fee Structure

- **Trading fee:** ~1% (varies by market)
- **Gas fees:** Polygon gas (typically <$0.01)
- **No deposit/withdrawal fees**

### B. Useful Resources

- Polymarket Docs: https://docs.polymarket.com
- CLOB API Reference: https://docs.polymarket.com/#clob-api
- Polygon RPC: https://polygon-rpc.com

### C. Example Arbitrage Calculation

```python
# Market: "Will ETH > $4000 by Friday?"
yes_ask = 0.52  # Best ask for YES
no_ask = 0.46   # Best ask for NO
total = yes_ask + no_ask  # 0.98

# Opportunity exists: total < 1.00
spread = 1.00 - total  # 0.02 (2%)

# With $1000 capital
yes_cost = 1000 * yes_ask  # $520
no_cost = 1000 * no_ask    # $460
total_cost = 980           # $980

# Outcome (either wins)
payout = 1000              # $1000
gross_profit = 20          # $20
fees = 980 * 0.01          # ~$9.80
net_profit = 10.20         # $10.20 (1.04% net return)
```

### D. Order Signing (EIP-712)

```python
from eth_account import Account
from eth_account.messages import encode_typed_data

order_types = {
    "Order": [
        {"name": "salt", "type": "uint256"},
        {"name": "maker", "type": "address"},
        {"name": "signer", "type": "address"},
        {"name": "taker", "type": "address"},
        {"name": "tokenId", "type": "uint256"},
        {"name": "makerAmount", "type": "uint256"},
        {"name": "takerAmount", "type": "uint256"},
        {"name": "expiration", "type": "uint256"},
        {"name": "nonce", "type": "uint256"},
        {"name": "feeRateBps", "type": "uint256"},
        {"name": "side", "type": "uint8"},
        {"name": "signatureType", "type": "uint8"},
    ]
}

domain = {
    "name": "Polymarket CTF Exchange",
    "version": "1",
    "chainId": 137,
    "verifyingContract": "0x..."
}

# Sign order
signable = encode_typed_data(domain, order_types, order_data)
signature = Account.sign_message(signable, private_key)
```

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 0.1 | 2024-XX-XX | Initial PRD |
| 0.2 | 2024-12-21 | L2 auth, contract approvals, order monitoring, dashboard order visibility |
| 0.3 | 2024-12-22 | AWS infra (OpenTofu + Ansible), SOCKS5 proxy support, removed Kalshi |
| 0.4 | 2025-12-22 | Multi-connection scanner (6 WS, 1500 markets), HTTPS dashboard with Caddy |
| 0.5 | 2025-12-22 | Async CLOB client (httpx + HTTP/2), native EIP-712 signing, parallel order execution |
