"""Cross-platform scanner for Polymarket vs Kalshi arbitrage."""

import asyncio
from dataclasses import dataclass
from decimal import Decimal
from typing import Callable, Optional

from rarb.api.gamma import GammaClient
from rarb.api.kalshi import KalshiClient, KalshiMarket
from rarb.api.models import Market as PolyMarket
from rarb.config import get_settings
from rarb.matcher.event_matcher import EventMatcher, MatchedEvent
from rarb.utils.logging import get_logger

log = get_logger(__name__)


@dataclass
class CrossPlatformOpportunity:
    """An arbitrage opportunity between Polymarket and Kalshi."""
    match: MatchedEvent
    direction: str  # "buy_poly_sell_kalshi" or "buy_kalshi_sell_poly"
    poly_price: Decimal
    kalshi_price: Decimal
    spread: Decimal
    spread_pct: Decimal
    max_size: Decimal  # In dollars


CrossPlatformCallback = Callable[[CrossPlatformOpportunity], None]


class CrossPlatformScanner:
    """
    Scanner for cross-platform arbitrage between Polymarket and Kalshi.

    Periodically fetches markets from both platforms, matches equivalent
    events, and detects price discrepancies.
    """

    def __init__(
        self,
        on_opportunity: Optional[CrossPlatformCallback] = None,
        poll_interval: float = 30.0,
        min_spread: float = 0.02,  # 2% minimum spread
        min_liquidity: float = 5000.0,
        max_markets: int = 200,
    ) -> None:
        settings = get_settings()

        self.gamma = GammaClient()
        self.kalshi = KalshiClient()
        self.matcher = EventMatcher(min_confidence=0.5)

        self._on_opportunity = on_opportunity
        self.poll_interval = poll_interval
        self.min_spread = Decimal(str(min_spread))
        self.min_liquidity = min_liquidity
        self.max_markets = max_markets

        # State
        self._poly_markets: list[PolyMarket] = []
        self._kalshi_markets: list[KalshiMarket] = []
        self._matches: list[MatchedEvent] = []
        self._running = False

        # Stats
        self._scan_count = 0
        self._opportunities_found = 0

    async def load_polymarket_markets(self) -> list[PolyMarket]:
        """Load markets from Polymarket."""
        log.info("Loading Polymarket markets...")

        markets = await self.gamma.fetch_all_active_markets(
            min_liquidity=self.min_liquidity,
        )

        # Sort by liquidity and take top N
        markets.sort(key=lambda m: m.liquidity, reverse=True)
        markets = markets[:self.max_markets]

        self._poly_markets = markets
        log.info("Polymarket markets loaded", count=len(markets))

        return markets

    async def load_kalshi_markets(self) -> list[KalshiMarket]:
        """Load markets from Kalshi."""
        log.info("Loading Kalshi markets...")

        try:
            markets = await self.kalshi.get_markets(status="open", limit=500)
            self._kalshi_markets = markets
            log.info("Kalshi markets loaded", count=len(markets))
            return markets
        except Exception as e:
            log.error("Failed to load Kalshi markets", error=str(e))
            return []

    async def match_markets(self) -> list[MatchedEvent]:
        """Match markets between platforms."""
        if not self._poly_markets or not self._kalshi_markets:
            return []

        matches = self.matcher.match_batch(
            self._poly_markets,
            self._kalshi_markets,
        )

        self._matches = matches
        return matches

    def find_opportunities(self) -> list[CrossPlatformOpportunity]:
        """Find arbitrage opportunities from matched markets."""
        opportunities = []

        for match in self._matches:
            opp = self._check_opportunity(match)
            if opp:
                opportunities.append(opp)

        return opportunities

    def _check_opportunity(
        self,
        match: MatchedEvent,
    ) -> Optional[CrossPlatformOpportunity]:
        """Check if a matched event has an arbitrage opportunity."""
        poly_yes = match.polymarket.yes_price
        kalshi_yes = match.kalshi.yes_ask

        if not poly_yes or not kalshi_yes:
            return None

        # Calculate spread
        spread = abs(kalshi_yes - poly_yes)
        spread_pct = spread / min(poly_yes, kalshi_yes) if min(poly_yes, kalshi_yes) > 0 else Decimal("0")

        if spread < self.min_spread:
            return None

        # Determine direction
        if kalshi_yes > poly_yes:
            direction = "buy_poly_sell_kalshi"
            buy_price = poly_yes
            sell_price = kalshi_yes
        else:
            direction = "buy_kalshi_sell_poly"
            buy_price = kalshi_yes
            sell_price = poly_yes

        # Estimate max size based on liquidity
        max_size = min(
            float(match.polymarket.liquidity) * 0.1,  # 10% of poly liquidity
            1000.0,  # Cap at $1000
        )

        return CrossPlatformOpportunity(
            match=match,
            direction=direction,
            poly_price=poly_yes,
            kalshi_price=kalshi_yes,
            spread=spread,
            spread_pct=spread_pct,
            max_size=Decimal(str(max_size)),
        )

    async def scan_once(self) -> list[CrossPlatformOpportunity]:
        """Run a single scan cycle."""
        self._scan_count += 1

        # Load markets from both platforms concurrently
        await asyncio.gather(
            self.load_polymarket_markets(),
            self.load_kalshi_markets(),
        )

        # Match markets
        await self.match_markets()

        # Find opportunities
        opportunities = self.find_opportunities()

        for opp in opportunities:
            self._opportunities_found += 1

            log.info(
                "Cross-platform opportunity",
                poly=opp.match.polymarket.question[:40],
                kalshi=opp.match.kalshi.ticker,
                direction=opp.direction,
                poly_price=f"${float(opp.poly_price):.2f}",
                kalshi_price=f"${float(opp.kalshi_price):.2f}",
                spread=f"{float(opp.spread_pct) * 100:.1f}%",
            )

            if self._on_opportunity:
                try:
                    result = self._on_opportunity(opp)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    log.error("Opportunity callback error", error=str(e))

        return opportunities

    async def run(self) -> None:
        """Run the scanner continuously."""
        self._running = True

        log.info(
            "Starting cross-platform scanner",
            poll_interval=self.poll_interval,
            min_spread=f"{float(self.min_spread) * 100:.1f}%",
        )

        # Check Kalshi connectivity
        try:
            balance = await self.kalshi.get_balance()
            log.info("Kalshi connected", balance=f"${float(balance):.2f}")
        except Exception as e:
            log.error("Kalshi connection failed", error=str(e))
            log.warning("Running in Polymarket-only mode")

        while self._running:
            try:
                await self.scan_once()

                # Log periodic stats
                if self._scan_count % 10 == 0:
                    log.info(
                        "Cross-platform scanner stats",
                        scans=self._scan_count,
                        poly_markets=len(self._poly_markets),
                        kalshi_markets=len(self._kalshi_markets),
                        matches=len(self._matches),
                        opportunities=self._opportunities_found,
                    )

            except Exception as e:
                log.error("Scan cycle error", error=str(e))

            await asyncio.sleep(self.poll_interval)

    def stop(self) -> None:
        """Stop the scanner."""
        log.info("Stopping cross-platform scanner")
        self._running = False

    async def close(self) -> None:
        """Close all connections."""
        self.stop()
        await self.gamma.close()
        await self.kalshi.close()

    def get_stats(self) -> dict:
        """Get scanner statistics."""
        return {
            "scan_count": self._scan_count,
            "poly_markets": len(self._poly_markets),
            "kalshi_markets": len(self._kalshi_markets),
            "matched_events": len(self._matches),
            "opportunities_found": self._opportunities_found,
        }

    async def __aenter__(self) -> "CrossPlatformScanner":
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()
