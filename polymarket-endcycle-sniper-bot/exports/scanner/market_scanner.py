"""Market scanner for polling and tracking markets."""

import asyncio
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Callable, Optional

from rarb.api.clob import ClobClient
from rarb.api.gamma import GammaClient
from rarb.api.models import Market, OrderBook
from rarb.config import get_settings
from rarb.utils.logging import get_logger

log = get_logger(__name__)


@dataclass
class MarketSnapshot:
    """A snapshot of a market with current orderbook data."""

    market: Market
    yes_orderbook: OrderBook
    no_orderbook: OrderBook

    @property
    def yes_best_ask(self) -> Optional[Decimal]:
        """Best ask price for YES token."""
        return self.yes_orderbook.best_ask

    @property
    def no_best_ask(self) -> Optional[Decimal]:
        """Best ask price for NO token."""
        return self.no_orderbook.best_ask

    @property
    def yes_best_bid(self) -> Optional[Decimal]:
        """Best bid price for YES token."""
        return self.yes_orderbook.best_bid

    @property
    def no_best_bid(self) -> Optional[Decimal]:
        """Best bid price for NO token."""
        return self.no_orderbook.best_bid

    @property
    def combined_ask(self) -> Optional[Decimal]:
        """Combined cost to buy both YES and NO at best ask."""
        yes_ask = self.yes_best_ask
        no_ask = self.no_best_ask
        if yes_ask is None or no_ask is None:
            return None
        return yes_ask + no_ask

    @property
    def arbitrage_spread(self) -> Optional[Decimal]:
        """Potential arbitrage profit (1 - combined_ask)."""
        combined = self.combined_ask
        if combined is None:
            return None
        return Decimal("1") - combined

    @property
    def min_liquidity_at_ask(self) -> Optional[Decimal]:
        """Minimum size available at best ask for either side."""
        yes_size = self.yes_orderbook.best_ask_size
        no_size = self.no_orderbook.best_ask_size
        if yes_size is None or no_size is None:
            return None
        return min(yes_size, no_size)


@dataclass
class ScannerState:
    """Current state of the market scanner."""

    markets: dict[str, Market] = field(default_factory=dict)
    snapshots: dict[str, MarketSnapshot] = field(default_factory=dict)
    last_market_refresh: float = 0
    scan_count: int = 0
    error_count: int = 0


class MarketScanner:
    """
    Scans Polymarket for arbitrage opportunities.

    Responsibilities:
    - Periodically refresh the list of active markets
    - Poll orderbooks for tracked markets
    - Emit snapshots for analysis
    """

    def __init__(
        self,
        gamma_client: Optional[GammaClient] = None,
        clob_client: Optional[ClobClient] = None,
        poll_interval: Optional[float] = None,
        market_refresh_interval: float = 300,  # 5 minutes
        min_volume: float = 0,
        min_liquidity: float = 0,
    ) -> None:
        settings = get_settings()

        self.gamma = gamma_client or GammaClient()
        self.clob = clob_client or ClobClient()
        self.poll_interval = poll_interval or settings.poll_interval_seconds
        self.market_refresh_interval = market_refresh_interval
        self.min_volume = min_volume
        self.min_liquidity = min_liquidity or settings.min_liquidity_usd

        self.state = ScannerState()
        self._running = False
        self._callbacks: list[Callable[[MarketSnapshot], None]] = []

    def on_snapshot(self, callback: Callable[[MarketSnapshot], None]) -> None:
        """Register a callback for market snapshots."""
        self._callbacks.append(callback)

    async def _emit_snapshot(self, snapshot: MarketSnapshot) -> None:
        """Emit a snapshot to all registered callbacks."""
        for callback in self._callbacks:
            try:
                result = callback(snapshot)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                log.error("Snapshot callback error", error=str(e))

    async def refresh_markets(self) -> None:
        """Refresh the list of active markets from Gamma API."""
        log.info("Refreshing market list...")

        try:
            markets = await self.gamma.fetch_all_active_markets(
                min_volume=self.min_volume,
                min_liquidity=self.min_liquidity,
            )

            # Update state
            self.state.markets = {m.id: m for m in markets}
            self.state.last_market_refresh = asyncio.get_event_loop().time()

            log.info("Market list refreshed", count=len(markets))

        except Exception as e:
            log.error("Failed to refresh markets", error=str(e))
            self.state.error_count += 1

    async def scan_market(self, market: Market) -> Optional[MarketSnapshot]:
        """
        Scan a single market and return a snapshot.

        Args:
            market: The market to scan

        Returns:
            MarketSnapshot or None if scan failed
        """
        try:
            # Fetch orderbooks for both tokens concurrently
            yes_ob, no_ob = await asyncio.gather(
                self.clob.get_orderbook(market.yes_token.token_id),
                self.clob.get_orderbook(market.no_token.token_id),
            )

            snapshot = MarketSnapshot(
                market=market,
                yes_orderbook=yes_ob,
                no_orderbook=no_ob,
            )

            return snapshot

        except Exception as e:
            log.debug(
                "Failed to scan market",
                market_id=market.id,
                error=str(e),
            )
            return None

    async def scan_all_markets(self) -> list[MarketSnapshot]:
        """
        Scan all tracked markets.

        Returns:
            List of market snapshots
        """
        snapshots: list[MarketSnapshot] = []

        # Create tasks for all markets
        tasks = [
            self.scan_market(market)
            for market in self.state.markets.values()
        ]

        # Execute concurrently with some rate limiting
        # Process in batches to avoid overwhelming the API
        batch_size = 20
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i : i + batch_size]
            results = await asyncio.gather(*batch, return_exceptions=True)

            for result in results:
                if isinstance(result, MarketSnapshot):
                    snapshots.append(result)
                elif isinstance(result, Exception):
                    log.debug("Scan error in batch", error=str(result))

        # Update state
        self.state.snapshots = {s.market.id: s for s in snapshots}
        self.state.scan_count += 1

        return snapshots

    async def run_once(self) -> list[MarketSnapshot]:
        """
        Run a single scan cycle.

        Returns:
            List of market snapshots
        """
        loop = asyncio.get_event_loop()
        current_time = loop.time()

        # Check if we need to refresh markets
        time_since_refresh = current_time - self.state.last_market_refresh
        if time_since_refresh >= self.market_refresh_interval or not self.state.markets:
            await self.refresh_markets()

        # Scan markets
        snapshots = await self.scan_all_markets()

        # Emit snapshots
        for snapshot in snapshots:
            await self._emit_snapshot(snapshot)

        return snapshots

    async def run(self) -> None:
        """
        Run the scanner continuously.

        This will poll markets at the configured interval until stopped.
        """
        self._running = True
        log.info(
            "Starting market scanner",
            poll_interval=self.poll_interval,
            min_volume=self.min_volume,
            min_liquidity=self.min_liquidity,
        )

        try:
            while self._running:
                try:
                    snapshots = await self.run_once()
                    log.debug(
                        "Scan complete",
                        markets=len(snapshots),
                        scan_count=self.state.scan_count,
                    )
                except Exception as e:
                    log.error("Scan cycle error", error=str(e))
                    self.state.error_count += 1

                # Wait for next cycle
                await asyncio.sleep(self.poll_interval)

        finally:
            await self.close()

    def stop(self) -> None:
        """Stop the scanner."""
        log.info("Stopping market scanner")
        self._running = False

    async def close(self) -> None:
        """Close all connections."""
        await self.gamma.close()
        await self.clob.close()

    async def __aenter__(self) -> "MarketScanner":
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args: object) -> None:
        """Async context manager exit."""
        self.stop()
        await self.close()
