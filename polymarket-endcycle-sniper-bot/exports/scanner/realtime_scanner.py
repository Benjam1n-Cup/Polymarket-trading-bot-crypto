"""Real-time market scanner using WebSocket streaming."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Awaitable, Callable, Optional

from rarb.api.gamma import GammaClient
from rarb.api.models import Market
from rarb.api.websocket import (
    OrderBookUpdate,
    PriceChange,
    WebSocketClient,
)
from rarb.config import get_settings
from rarb.data.database import init_async_db
from rarb.data.repositories import AlertRepository, StatsRepository
from rarb.notifications.slack import get_notifier
from rarb.utils.logging import get_logger

log = get_logger(__name__)

# Maximum assets per WebSocket connection
MAX_ASSETS_PER_WS = 500
# Default number of WebSocket connections
DEFAULT_WS_CONNECTIONS = 6


@dataclass
class MarketPrices:
    """Tracks current prices for a market's YES and NO tokens."""
    market: Market
    yes_best_bid: Optional[Decimal] = None
    yes_best_ask: Optional[Decimal] = None
    no_best_bid: Optional[Decimal] = None
    no_best_ask: Optional[Decimal] = None
    # Size available at best ask prices
    yes_best_ask_size: Optional[Decimal] = None
    no_best_ask_size: Optional[Decimal] = None

    @property
    def combined_ask(self) -> Optional[Decimal]:
        """Cost to buy both YES and NO at best ask."""
        if self.yes_best_ask is None or self.no_best_ask is None:
            return None
        return self.yes_best_ask + self.no_best_ask

    @property
    def arbitrage_profit(self) -> Optional[Decimal]:
        """Potential profit from arbitrage (1 - combined_ask)."""
        combined = self.combined_ask
        if combined is None:
            return None
        return Decimal("1") - combined

    @property
    def has_arbitrage(self) -> bool:
        """Check if arbitrage opportunity exists."""
        profit = self.arbitrage_profit
        if profit is None:
            return False
        settings = get_settings()
        return profit > Decimal(str(settings.min_profit_threshold))


@dataclass
class ArbitrageAlert:
    """Alert for detected arbitrage opportunity."""
    market: Market
    yes_ask: Decimal
    no_ask: Decimal
    combined_cost: Decimal
    profit_pct: Decimal
    timestamp: float
    # Size available at ask prices
    yes_size_available: Decimal = Decimal("0")
    no_size_available: Decimal = Decimal("0")


# Callback type for arbitrage alerts
ArbitrageCallback = Callable[[ArbitrageAlert], None]


class RealtimeScanner:
    """
    Real-time market scanner using WebSocket streaming.

    Instead of polling, this scanner:
    1. Loads markets from Gamma API
    2. Subscribes to WebSocket for real-time price updates
    3. Triggers callbacks instantly when arbitrage is detected

    Supports multiple WebSocket connections to monitor more markets.
    """

    def __init__(
        self,
        on_arbitrage: Optional[ArbitrageCallback] = None,
        on_markets_loaded: Optional[Callable[[list["Market"]], Awaitable[None]]] = None,
        min_liquidity: Optional[float] = None,
        max_days_until_resolution: Optional[int] = None,
        num_connections: Optional[int] = None,
    ) -> None:
        settings = get_settings()

        self.gamma = GammaClient()

        # Use settings from config, allow override via constructor
        self.min_liquidity = min_liquidity if min_liquidity is not None else settings.min_liquidity_usd
        self.max_days_until_resolution = (
            max_days_until_resolution if max_days_until_resolution is not None
            else settings.max_days_until_resolution
        )
        self.num_connections = num_connections if num_connections is not None else settings.num_ws_connections

        # Calculate max markets based on connections
        # Each connection can handle 500 assets = 250 markets (YES + NO tokens)
        self.max_markets = (MAX_ASSETS_PER_WS // 2) * self.num_connections

        # Create multiple WebSocket clients
        self.ws_clients: list[WebSocketClient] = []
        for i in range(self.num_connections):
            client = WebSocketClient(
                on_book=self._on_book_update,
                on_price_change=self._on_price_change,
            )
            self.ws_clients.append(client)

        self._on_arbitrage = on_arbitrage
        self._on_markets_loaded = on_markets_loaded

        # State
        self._markets: dict[str, Market] = {}  # market_id -> Market
        self._token_to_market: dict[str, str] = {}  # token_id -> market_id
        self._market_prices: dict[str, MarketPrices] = {}  # market_id -> MarketPrices
        self._running = False

        # Track active opportunities for duration calculation
        self._active_opportunities: dict[str, datetime] = {}  # market_id -> first_seen

        # Stats
        self._price_updates = 0
        self._arbitrage_alerts = 0

        log.info(
            "Scanner initialized",
            num_connections=self.num_connections,
            max_markets=self.max_markets,
            min_liquidity=self.min_liquidity,
            max_days=self.max_days_until_resolution,
        )

    async def load_markets(self) -> list[Market]:
        """Load active markets from Gamma API."""
        log.info("Loading markets from Gamma API...")

        markets = await self.gamma.fetch_all_active_markets(
            min_liquidity=self.min_liquidity,
            max_days_until_resolution=self.max_days_until_resolution,
        )

        # Sort by liquidity and take top N
        markets.sort(key=lambda m: m.liquidity, reverse=True)
        markets = markets[:self.max_markets]

        # Build lookup tables
        self._markets = {}
        self._token_to_market = {}
        self._market_prices = {}

        for market in markets:
            self._markets[market.id] = market
            self._token_to_market[market.yes_token.token_id] = market.id
            self._token_to_market[market.no_token.token_id] = market.id
            self._market_prices[market.id] = MarketPrices(market=market)

        log.info(
            "Markets loaded",
            count=len(markets),
            min_liquidity=self.min_liquidity,
            max_days=self.max_days_until_resolution,
        )

        return markets

    async def subscribe_to_markets(self) -> None:
        """Subscribe to WebSocket updates for all loaded markets."""
        # Clear old subscriptions for fresh start
        for client in self.ws_clients:
            client._subscribed_assets.clear()

        # Collect all token IDs (YES and NO for each market)
        token_ids = []
        for market in self._markets.values():
            token_ids.append(market.yes_token.token_id)
            token_ids.append(market.no_token.token_id)

        log.info("Subscribing to tokens", count=len(token_ids), connections=len(self.ws_clients))

        # Distribute tokens across connections
        # Each connection can handle MAX_ASSETS_PER_WS (500) tokens
        for i, client in enumerate(self.ws_clients):
            start = i * MAX_ASSETS_PER_WS
            end = start + MAX_ASSETS_PER_WS
            batch = token_ids[start:end]
            if batch:
                log.info(f"Connection {i+1}: subscribing to {len(batch)} tokens")
                await client.subscribe(batch)

    def _on_book_update(self, update: OrderBookUpdate) -> None:
        """Handle orderbook snapshot update."""
        # Get size at best ask price
        best_ask_size = None
        if update.asks:
            best_ask_price = min(a.price for a in update.asks)
            for a in update.asks:
                if a.price == best_ask_price:
                    best_ask_size = a.size
                    break

        # Debug: log when we receive book updates with size data
        if best_ask_size is not None and best_ask_size > 0:
            log.debug(
                "Book update with size",
                asset_id=update.asset_id[:20] + "...",
                best_ask=float(update.best_ask) if update.best_ask else None,
                best_ask_size=float(best_ask_size),
                num_asks=len(update.asks),
            )

        self._update_prices(
            update.asset_id,
            update.best_bid,
            update.best_ask,
            best_ask_size,
        )

    def _on_price_change(self, change: PriceChange) -> None:
        """Handle real-time price change."""
        self._price_updates += 1
        best_ask_size = None

        # If this is a SELL-side change at the best ask, use the size directly
        if (
            change.side == "SELL"
            and change.best_ask is not None
            and change.price == change.best_ask
        ):
            best_ask_size = change.size
        else:
            # Fall back to cached orderbook for size
            orderbook = None
            for client in self.ws_clients:
                orderbook = client.get_orderbook(change.asset_id)
                if orderbook:
                    break
            if orderbook and orderbook.asks:
                best_ask_price = min(a.price for a in orderbook.asks)
                for a in orderbook.asks:
                    if a.price == best_ask_price:
                        best_ask_size = a.size
                        break

        self._update_prices(
            change.asset_id,
            change.best_bid,
            change.best_ask,
            best_ask_size,
        )

    def _update_prices(
        self,
        token_id: str,
        best_bid: Optional[Decimal],
        best_ask: Optional[Decimal],
        best_ask_size: Optional[Decimal] = None,
    ) -> None:
        """Update prices for a token and check for arbitrage."""
        market_id = self._token_to_market.get(token_id)
        if not market_id:
            return

        market = self._markets.get(market_id)
        if not market:
            return

        prices = self._market_prices.get(market_id)
        if not prices:
            return

        # Update the appropriate side
        if token_id == market.yes_token.token_id:
            prices.yes_best_bid = best_bid
            prices.yes_best_ask = best_ask
            if best_ask_size is not None:
                prices.yes_best_ask_size = best_ask_size
        elif token_id == market.no_token.token_id:
            prices.no_best_bid = best_bid
            prices.no_best_ask = best_ask
            if best_ask_size is not None:
                prices.no_best_ask_size = best_ask_size

        # Check for arbitrage
        self._check_arbitrage(prices)

    def _check_arbitrage(self, prices: MarketPrices) -> None:
        """Check if market has arbitrage opportunity and trigger alert."""
        # Track near-misses for diagnostics (profit > 0 but below threshold)
        profit = prices.arbitrage_profit
        if profit is not None and profit > Decimal("0"):
            settings = get_settings()
            # Log near-misses (within 0.5% of threshold) at debug level
            if profit < Decimal(str(settings.min_profit_threshold)):
                if profit > Decimal(str(settings.min_profit_threshold)) - Decimal("0.005"):
                    log.debug(
                        "Near-miss arbitrage",
                        market=prices.market.question[:40],
                        profit=f"{float(profit) * 100:.3f}%",
                        threshold=f"{settings.min_profit_threshold * 100:.1f}%",
                        combined=f"${float(prices.combined_ask):.4f}" if prices.combined_ask else "N/A",
                    )
                # Track the best near-miss for stats logging
                if not hasattr(self, '_best_near_miss') or profit > self._best_near_miss:
                    self._best_near_miss = profit
                    self._best_near_miss_market = prices.market.question[:40]

        if not prices.has_arbitrage:
            # If this market had an active opportunity that just ended, update its duration
            market_id = prices.market.id
            if market_id in self._active_opportunities:
                first_seen = self._active_opportunities.pop(market_id)
                duration_secs = (datetime.now(timezone.utc) - first_seen).total_seconds()
                log.info(
                    "Opportunity closed",
                    market=prices.market.question[:40],
                    duration_secs=f"{duration_secs:.3f}s",
                )
                # Update the alert's duration in the database
                asyncio.create_task(self._update_alert_duration(
                    prices.market.question[:60],
                    duration_secs,
                ))
            return

        # Check resolution date - skip markets that resolve too far in the future
        settings = get_settings()
        if prices.market.end_date:
            now = datetime.now(timezone.utc)
            # Make end_date timezone-aware if it isn't
            end_date = prices.market.end_date
            if end_date.tzinfo is None:
                end_date = end_date.replace(tzinfo=timezone.utc)
            days_until = (end_date - now).days
            if days_until > settings.max_days_until_resolution:
                log.debug(
                    "Skipping arbitrage - resolution too far",
                    market=prices.market.question[:30],
                    days_until=days_until,
                    max_days=settings.max_days_until_resolution,
                )
                return

        # We have an opportunity!
        combined = prices.combined_ask
        profit = prices.arbitrage_profit

        if combined is None or profit is None:
            return

        self._arbitrage_alerts += 1

        # Track when opportunity first appeared
        market_id = prices.market.id
        now = datetime.now(timezone.utc)
        if market_id not in self._active_opportunities:
            self._active_opportunities[market_id] = now
        first_seen = self._active_opportunities[market_id]
        duration_secs = (now - first_seen).total_seconds()

        # Try to get fresh liquidity data from cached orderbooks if missing
        yes_size = prices.yes_best_ask_size
        no_size = prices.no_best_ask_size

        if yes_size is None or no_size is None:
            # Look up orderbooks from WebSocket clients
            for client in self.ws_clients:
                if yes_size is None:
                    yes_book = client.get_orderbook(prices.market.yes_token.token_id)
                    if yes_book and yes_book.asks:
                        best_ask_price = min(a.price for a in yes_book.asks)
                        for a in yes_book.asks:
                            if a.price == best_ask_price:
                                yes_size = a.size
                                prices.yes_best_ask_size = yes_size  # Update cache
                                break
                if no_size is None:
                    no_book = client.get_orderbook(prices.market.no_token.token_id)
                    if no_book and no_book.asks:
                        best_ask_price = min(a.price for a in no_book.asks)
                        for a in no_book.asks:
                            if a.price == best_ask_price:
                                no_size = a.size
                                prices.no_best_ask_size = no_size  # Update cache
                                break
                if yes_size is not None and no_size is not None:
                    break

        alert = ArbitrageAlert(
            market=prices.market,
            yes_ask=prices.yes_best_ask or Decimal("0"),
            no_ask=prices.no_best_ask or Decimal("0"),
            combined_cost=combined,
            profit_pct=profit,
            timestamp=asyncio.get_event_loop().time(),
            yes_size_available=yes_size or Decimal("0"),
            no_size_available=no_size or Decimal("0"),
        )

        # Calculate days until resolution for logging
        days_until_resolution = None
        if prices.market.end_date:
            now = datetime.now(timezone.utc)
            end_date = prices.market.end_date
            if end_date.tzinfo is None:
                end_date = end_date.replace(tzinfo=timezone.utc)
            days_until_resolution = (end_date - now).days

        log.info(
            "ARBITRAGE DETECTED",
            market=prices.market.question[:50],
            yes_ask=f"${float(alert.yes_ask):.4f}",
            no_ask=f"${float(alert.no_ask):.4f}",
            combined=f"${float(alert.combined_cost):.4f}",
            profit=f"{float(alert.profit_pct) * 100:.2f}%",
            yes_liq=f"${float(alert.yes_size_available):.2f}",
            no_liq=f"${float(alert.no_size_available):.2f}",
            resolves_in=f"{days_until_resolution}d" if days_until_resolution is not None else "unknown",
            open_for=f"{duration_secs:.1f}s",
        )

        # Trigger callback FIRST - execution is time-critical
        if self._on_arbitrage:
            try:
                result = self._on_arbitrage(alert)
                if asyncio.iscoroutine(result):
                    asyncio.create_task(result)
            except Exception as e:
                log.error("Arbitrage callback error", error=str(e))

        # Save alert to database (non-blocking, creates async task)
        # Duration is set later when opportunity closes via _update_alert_duration
        self._save_alert(alert, first_seen, None)

        # Send Slack notification (already async)
        try:
            notifier = get_notifier()
            asyncio.create_task(notifier.notify_arbitrage(
                market=prices.market.question,
                yes_ask=alert.yes_ask,
                no_ask=alert.no_ask,
                combined=alert.combined_cost,
                profit_pct=alert.profit_pct,
            ))
        except Exception as e:
            log.debug("Slack notification failed", error=str(e))

    async def run(self) -> None:
        """Run the real-time scanner."""
        self._running = True

        # Initialize database
        await init_async_db()

        log.info(
            "Starting real-time scanner",
            num_connections=self.num_connections,
            max_markets=self.max_markets,
        )

        # Load markets
        markets = await self.load_markets()

        # Call on_markets_loaded callback if provided (for pre-caching neg_risk, etc.)
        if self._on_markets_loaded:
            try:
                await self._on_markets_loaded(markets)
            except Exception as e:
                log.warning("on_markets_loaded callback failed", error=str(e))

        # Connect all WebSocket clients
        for i, client in enumerate(self.ws_clients):
            await client.connect()
            log.info(f"WebSocket connection {i+1} established")

        # Subscribe to markets (distributes across connections)
        await self.subscribe_to_markets()

        # Run all WebSocket listeners plus periodic tasks
        tasks = [
            self._run_websocket_with_reconnect(i, client)
            for i, client in enumerate(self.ws_clients)
        ]
        tasks.extend([
            self._periodic_market_refresh(),
            self._periodic_stats(),
            self._zombie_connection_watchdog(),
        ])
        await asyncio.gather(*tasks)

    async def _run_websocket_with_reconnect(self, conn_id: int, client: WebSocketClient) -> None:
        """Run a single WebSocket connection with automatic reconnection."""
        while self._running:
            try:
                # Listen until disconnected
                await client.listen()

            except Exception as e:
                log.error(f"WebSocket {conn_id+1} error", error=str(e))

            if not self._running:
                break

            # Reconnect with backoff
            delay = min(client._reconnect_delay, 30)
            log.info(f"Reconnecting WebSocket {conn_id+1}", delay=delay)
            await asyncio.sleep(delay)
            client._reconnect_delay = min(delay * 2, 60)

            # Reconnect
            try:
                await client.connect()
                # Re-subscribe this connection's tokens
                token_ids = list(self._token_to_market.keys())
                start = conn_id * MAX_ASSETS_PER_WS
                end = start + MAX_ASSETS_PER_WS
                batch = token_ids[start:end]
                if batch:
                    await client.subscribe(batch)
            except Exception as e:
                log.error(f"WebSocket {conn_id+1} reconnect failed", error=str(e))

    async def _periodic_market_refresh(self, interval: float = 600) -> None:
        """Periodically refresh market list (every 10 min)."""
        while self._running:
            await asyncio.sleep(interval)

            try:
                log.info("Refreshing market list...")
                old_count = len(self._markets)
                await self.load_markets()
                new_count = len(self._markets)

                # Only resubscribe if markets changed significantly
                if abs(new_count - old_count) > 10:
                    log.info("Market list changed, reconnecting all WebSockets")
                    # Close all connections to trigger reconnect
                    for client in self.ws_clients:
                        client._subscribed_assets.clear()
                        if client._ws:
                            await client._ws.close()
            except Exception as e:
                log.error("Market refresh error", error=str(e))

    async def _zombie_connection_watchdog(self, check_interval: float = 30, stale_threshold: float = 60) -> None:
        """
        Watchdog to detect and fix zombie WebSocket connections.

        A zombie connection appears connected (state=OPEN) but isn't receiving
        any data. This happens when the remote server silently drops us without
        sending a close frame.

        Args:
            check_interval: How often to check connections (seconds)
            stale_threshold: How long without messages before forcing reconnect (seconds)
        """
        # Wait a bit for initial connections to receive data
        await asyncio.sleep(check_interval)

        while self._running:
            for i, client in enumerate(self.ws_clients):
                if not client.is_connected:
                    continue

                seconds_silent = client.seconds_since_last_message

                # If connection has been silent for too long, it's probably a zombie
                if seconds_silent > stale_threshold:
                    log.warning(
                        "Zombie connection detected - forcing reconnect",
                        conn_id=i + 1,
                        seconds_silent=f"{seconds_silent:.0f}s",
                        threshold=f"{stale_threshold:.0f}s",
                    )

                    # Force close the connection to trigger reconnect
                    try:
                        if client._ws:
                            await client._ws.close(code=4000, reason="Zombie connection detected")
                    except Exception as e:
                        log.debug("Error closing zombie connection", error=str(e))

            await asyncio.sleep(check_interval)

    async def _periodic_stats(self, interval: float = 60) -> None:
        """Log periodic statistics and write to shared state file."""
        while self._running:
            await asyncio.sleep(interval)

            stats = self.get_stats()

            # Include best near-miss in stats if available
            best_spread = None
            best_spread_market = None
            if hasattr(self, '_best_near_miss') and self._best_near_miss:
                best_spread = f"{float(self._best_near_miss) * 100:.3f}%"
                best_spread_market = getattr(self, '_best_near_miss_market', None)

            # Get connection health info
            connection_ages = [
                f"{int(c.seconds_since_last_message)}s" if c.is_connected else "down"
                for c in self.ws_clients
            ]

            log.info(
                "Scanner stats",
                markets=stats["markets"],
                price_updates=stats["price_updates"],
                arbitrage_alerts=stats["arbitrage_alerts"],
                ws_connections=stats["ws_connections"],
                conn_ages=",".join(connection_ages),
                best_spread=best_spread,
            )

            # Log best near-miss market details if significant
            if best_spread and best_spread_market:
                log.debug(
                    "Best spread seen",
                    market=best_spread_market,
                    spread=best_spread,
                )

            # Write stats to database for dashboard (non-blocking)
            asyncio.create_task(self._write_stats_async(stats))

    async def _write_stats_async(self, stats: dict) -> None:
        """Write stats to database asynchronously."""
        try:
            await StatsRepository.update(
                markets=stats.get("markets", 0),
                price_updates=stats.get("price_updates", 0),
                arbitrage_alerts=stats.get("arbitrage_alerts", 0),
                ws_connected=stats.get("ws_connected", False),
                ws_connections=stats.get("ws_connections", ""),
                subscribed_tokens=stats.get("subscribed_tokens", 0),
            )
        except Exception as e:
            log.debug("Failed to write stats to database", error=str(e))

    def _save_alert(
        self,
        alert: ArbitrageAlert,
        first_seen: Optional[datetime] = None,
        duration_secs: Optional[float] = None,
    ) -> None:
        """Save arbitrage alert to database (non-blocking)."""
        # Schedule async save as a task
        asyncio.create_task(
            self._save_alert_async(alert, first_seen, duration_secs)
        )

    async def _save_alert_async(
        self,
        alert: ArbitrageAlert,
        first_seen: Optional[datetime] = None,
        duration_secs: Optional[float] = None,
    ) -> None:
        """Save arbitrage alert to database asynchronously."""
        try:
            # Calculate days until resolution
            days_until = None
            if alert.market.end_date:
                now = datetime.now(timezone.utc)
                end_date = alert.market.end_date
                if end_date.tzinfo is None:
                    end_date = end_date.replace(tzinfo=timezone.utc)
                days_until = (end_date - now).days

            # Include resolution date as ISO string for proper formatting
            resolution_date = None
            if alert.market.end_date:
                if alert.market.end_date.tzinfo is None:
                    resolution_date = alert.market.end_date.replace(tzinfo=timezone.utc).isoformat()
                else:
                    resolution_date = alert.market.end_date.isoformat()

            await AlertRepository.insert(
                market=alert.market.question[:60],
                yes_ask=float(alert.yes_ask),
                no_ask=float(alert.no_ask),
                combined=float(alert.combined_cost),
                profit=float(alert.profit_pct),
                timestamp=datetime.now(timezone.utc).isoformat(),
                platform="polymarket",
                days_until_resolution=days_until,
                resolution_date=resolution_date,
                first_seen=first_seen.isoformat() if first_seen else None,
                duration_secs=round(duration_secs, 1) if duration_secs is not None else None,
            )
        except Exception as e:
            log.debug("Failed to save alert to database", error=str(e))

    async def _update_alert_duration(self, market: str, duration_secs: float) -> None:
        """Update the duration of an alert when the opportunity closes."""
        try:
            updated = await AlertRepository.update_duration(market, duration_secs)
            if updated:
                log.debug(
                    "Updated alert duration",
                    market=market[:30],
                    duration_secs=f"{duration_secs:.3f}s",
                )
        except Exception as e:
            log.debug("Failed to update alert duration", error=str(e))

    def stop(self) -> None:
        """Stop the scanner."""
        log.info("Stopping real-time scanner")
        self._running = False

    async def close(self) -> None:
        """Close all connections."""
        self.stop()
        for client in self.ws_clients:
            await client.close()
        await self.gamma.close()

    def get_stats(self) -> dict:
        """Get scanner statistics."""
        # Aggregate stats from all WebSocket connections
        connected = sum(1 for c in self.ws_clients if c.is_connected)
        total_subscribed = sum(c.subscribed_count for c in self.ws_clients)
        return {
            "markets": len(self._markets),
            "price_updates": self._price_updates,
            "arbitrage_alerts": self._arbitrage_alerts,
            "ws_connected": connected == len(self.ws_clients),
            "ws_connections": f"{connected}/{len(self.ws_clients)}",
            "subscribed_tokens": total_subscribed,
        }

    async def __aenter__(self) -> "RealtimeScanner":
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()
