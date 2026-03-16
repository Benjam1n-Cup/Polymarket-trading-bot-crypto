"""Command-line interface for rarb."""

import asyncio
import sys
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from rarb import __version__
from rarb.config import get_settings, reload_settings
from rarb.utils.logging import setup_logging

console = Console()


@click.group()
@click.version_option(version=__version__)
def cli() -> None:
    """rarb - Polymarket arbitrage bot."""
    pass


@cli.command()
@click.option("--dry-run/--live", default=True, help="Dry run mode (no real trades)")
@click.option("--realtime/--polling", default=True, help="Use real-time WebSocket (default) or legacy polling")
@click.option("--poll-interval", type=float, help="Seconds between scans (polling mode only)")
@click.option("--min-profit", type=float, help="Minimum profit threshold (e.g., 0.005 for 0.5%)")
@click.option("--max-position", type=float, help="Maximum position size in USD")
@click.option("--log-level", type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]), default="INFO")
def run(
    dry_run: bool,
    realtime: bool,
    poll_interval: Optional[float],
    min_profit: Optional[float],
    max_position: Optional[float],
    log_level: str,
) -> None:
    """Run the arbitrage bot."""
    import os

    # Override settings from CLI
    if dry_run is not None:
        os.environ["DRY_RUN"] = str(dry_run).lower()
    if poll_interval is not None:
        os.environ["POLL_INTERVAL_SECONDS"] = str(poll_interval)
    if min_profit is not None:
        os.environ["MIN_PROFIT_THRESHOLD"] = str(min_profit)
    if max_position is not None:
        os.environ["MAX_POSITION_SIZE"] = str(max_position)
    if log_level:
        os.environ["LOG_LEVEL"] = log_level

    reload_settings()
    setup_logging(log_level)

    settings = get_settings()

    mode = "[yellow]DRY RUN[/yellow]" if settings.dry_run else "[red]LIVE TRADING[/red]"
    engine = "[cyan]REAL-TIME WebSocket[/cyan]" if realtime else "[dim]Legacy Polling[/dim]"
    console.print(f"\n[bold]rarb Arbitrage Bot[/bold] - {mode}")
    console.print(f"[bold]Engine:[/bold] {engine}\n")

    if not settings.dry_run:
        if not settings.private_key or not settings.wallet_address:
            console.print(
                "[red]Error:[/red] Live trading requires PRIVATE_KEY and WALLET_ADDRESS.\n"
                "Set these in your .env file or environment."
            )
            sys.exit(1)

        console.print(f"[dim]Wallet:[/dim] {settings.wallet_address}")

    if not realtime:
        console.print(f"[dim]Poll interval:[/dim] {settings.poll_interval_seconds}s")
    console.print(f"[dim]Min profit:[/dim] {settings.min_profit_threshold * 100:.1f}%")
    console.print(f"[dim]Max position:[/dim] ${settings.max_position_size}")
    console.print()

    try:
        if realtime:
            from rarb.bot import run_realtime_bot
            asyncio.run(run_realtime_bot())
        else:
            from rarb.bot import run_bot
            asyncio.run(run_bot())
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")


@cli.command()
def scan() -> None:
    """Scan markets once and show opportunities."""
    setup_logging("INFO")

    async def _scan() -> None:
        from rarb.analyzer.arbitrage import ArbitrageAnalyzer
        from rarb.scanner.market_scanner import MarketScanner

        console.print("[bold]Scanning markets...[/bold]\n")

        async with MarketScanner() as scanner:
            snapshots = await scanner.run_once()

            console.print(f"Found {len(snapshots)} active markets\n")

            analyzer = ArbitrageAnalyzer()
            opportunities = analyzer.analyze_batch(snapshots)

            if not opportunities:
                console.print("[yellow]No arbitrage opportunities found[/yellow]")
                return

            # Display opportunities
            table = Table(title="Arbitrage Opportunities")
            table.add_column("Market", style="cyan", max_width=40)
            table.add_column("YES Ask", justify="right")
            table.add_column("NO Ask", justify="right")
            table.add_column("Combined", justify="right")
            table.add_column("Profit %", justify="right", style="green")
            table.add_column("Max Size", justify="right")

            for opp in opportunities[:20]:  # Top 20
                table.add_row(
                    opp.market.question[:40],
                    f"${float(opp.yes_ask):.3f}",
                    f"${float(opp.no_ask):.3f}",
                    f"${float(opp.combined_cost):.3f}",
                    f"{float(opp.profit_pct) * 100:.2f}%",
                    f"${float(opp.max_trade_size):.0f}",
                )

            console.print(table)

    asyncio.run(_scan())


@cli.command()
@click.option("--limit", default=30, help="Maximum markets to show")
def markets(limit: int) -> None:
    """List active markets."""
    setup_logging("WARNING")

    async def _markets() -> None:
        from rarb.api.gamma import GammaClient

        console.print("[bold]Fetching markets...[/bold]\n")

        async with GammaClient() as client:
            # Just fetch one page of markets
            raw_markets = await client.get_markets(active=True, limit=100)
            markets = []
            for raw in raw_markets:
                m = client.parse_market(raw)
                if m is not None:
                    markets.append(m)

            # Sort by volume
            markets.sort(key=lambda m: m.volume, reverse=True)

            table = Table(title=f"Active Markets (showing {min(limit, len(markets))} of {len(markets)})")
            table.add_column("Market", style="cyan", max_width=50)
            table.add_column("Volume", justify="right")
            table.add_column("Liquidity", justify="right")
            table.add_column("YES", justify="right")
            table.add_column("NO", justify="right")

            for market in markets[:limit]:
                table.add_row(
                    market.question[:50],
                    f"${float(market.volume):,.0f}",
                    f"${float(market.liquidity):,.0f}",
                    f"${float(market.yes_price):.2f}",
                    f"${float(market.no_price):.2f}",
                )

            console.print(table)

    asyncio.run(_markets())


@cli.command()
def config() -> None:
    """Show current configuration."""
    settings = get_settings()

    table = Table(title="Current Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value")

    # Trading
    table.add_row("Dry Run", str(settings.dry_run))
    table.add_row("Min Profit Threshold", f"{settings.min_profit_threshold * 100:.1f}%")
    table.add_row("Max Position Size", f"${settings.max_position_size}")
    table.add_row("Poll Interval", f"{settings.poll_interval_seconds}s")
    table.add_row("Min Liquidity", f"${settings.min_liquidity_usd}")

    # Network
    table.add_row("Polygon RPC", settings.polygon_rpc_url[:50])
    table.add_row("Chain ID", str(settings.chain_id))

    # Credentials
    wallet = settings.wallet_address or "[not set]"
    has_key = "[set]" if settings.private_key else "[not set]"
    table.add_row("Wallet Address", wallet)
    table.add_row("Private Key", has_key)

    # Alerts
    has_telegram = "[set]" if settings.telegram_bot_token else "[not set]"
    table.add_row("Telegram Bot", has_telegram)

    console.print(table)


@cli.command()
@click.argument("token_id")
def orderbook(token_id: str) -> None:
    """Show orderbook for a token."""
    setup_logging("WARNING")

    async def _orderbook() -> None:
        from rarb.api.clob import ClobClient

        async with ClobClient() as client:
            ob = await client.get_orderbook(token_id)

            console.print(f"\n[bold]Orderbook for {token_id[:20]}...[/bold]\n")

            # Bids
            bid_table = Table(title="Bids (Buy Orders)")
            bid_table.add_column("Price", justify="right", style="green")
            bid_table.add_column("Size", justify="right")

            for level in sorted(ob.bids, key=lambda x: x.price, reverse=True)[:10]:
                bid_table.add_row(f"${float(level.price):.4f}", f"{float(level.size):,.2f}")

            # Asks
            ask_table = Table(title="Asks (Sell Orders)")
            ask_table.add_column("Price", justify="right", style="red")
            ask_table.add_column("Size", justify="right")

            for level in sorted(ob.asks, key=lambda x: x.price)[:10]:
                ask_table.add_row(f"${float(level.price):.4f}", f"{float(level.size):,.2f}")

            console.print(bid_table)
            console.print()
            console.print(ask_table)

            # Summary
            if ob.best_bid and ob.best_ask:
                spread = ob.best_ask - ob.best_bid
                console.print(f"\n[dim]Best Bid:[/dim] ${float(ob.best_bid):.4f}")
                console.print(f"[dim]Best Ask:[/dim] ${float(ob.best_ask):.4f}")
                console.print(f"[dim]Spread:[/dim] ${float(spread):.4f} ({float(spread / ob.best_ask) * 100:.2f}%)")

    asyncio.run(_orderbook())


@cli.command()
@click.option("--dry-run/--live", default=True, help="Dry run mode")
@click.option("--poll-interval", type=float, default=30.0, help="Seconds between scans")
@click.option("--min-spread", type=float, default=0.02, help="Minimum spread (e.g., 0.02 for 2%)")
@click.option("--log-level", type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]), default="INFO")
def crossplatform(
    dry_run: bool,
    poll_interval: float,
    min_spread: float,
    log_level: str,
) -> None:
    """Run cross-platform arbitrage scanner (Polymarket vs Kalshi)."""
    import os

    if dry_run is not None:
        os.environ["DRY_RUN"] = str(dry_run).lower()

    reload_settings()
    setup_logging(log_level)

    settings = get_settings()

    mode = "[yellow]DRY RUN[/yellow]" if settings.dry_run else "[red]LIVE TRADING[/red]"
    console.print(f"\n[bold]Cross-Platform Arbitrage Scanner[/bold] - {mode}")
    console.print(f"[bold]Platforms:[/bold] Polymarket + Kalshi\n")

    # Check credentials
    if not settings.is_kalshi_enabled():
        console.print(
            "[red]Error:[/red] Kalshi credentials not configured.\n"
            "Set KALSHI_API_KEY and KALSHI_PRIVATE_KEY in your .env file."
        )
        sys.exit(1)

    console.print(f"[dim]Poll interval:[/dim] {poll_interval}s")
    console.print(f"[dim]Min spread:[/dim] {min_spread * 100:.1f}%")
    console.print()

    async def _run() -> None:
        from rarb.scanner.crossplatform_scanner import CrossPlatformScanner

        async with CrossPlatformScanner(
            poll_interval=poll_interval,
            min_spread=min_spread,
        ) as scanner:
            await scanner.run()

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")


@cli.command()
def kalshi_test() -> None:
    """Test Kalshi API connection."""
    setup_logging("INFO")

    async def _test() -> None:
        from rarb.api.kalshi import KalshiClient

        console.print("[bold]Testing Kalshi API connection...[/bold]\n")

        settings = get_settings()
        if not settings.is_kalshi_enabled():
            console.print("[red]Error:[/red] Kalshi credentials not configured.")
            return

        async with KalshiClient() as client:
            try:
                # Test balance
                balance = await client.get_balance()
                console.print(f"[green]✓[/green] Connected to Kalshi")
                console.print(f"[dim]Account balance:[/dim] ${float(balance):.2f}\n")

                # Fetch some markets
                markets = await client.get_markets(limit=10)
                console.print(f"[dim]Found {len(markets)} open markets[/dim]\n")

                if markets:
                    table = Table(title="Sample Kalshi Markets")
                    table.add_column("Ticker", style="cyan")
                    table.add_column("Title", max_width=40)
                    table.add_column("YES Bid", justify="right")
                    table.add_column("YES Ask", justify="right")

                    for m in markets[:10]:
                        table.add_row(
                            m.ticker,
                            m.title[:40],
                            f"${float(m.yes_bid):.2f}" if m.yes_bid else "-",
                            f"${float(m.yes_ask):.2f}" if m.yes_ask else "-",
                        )

                    console.print(table)

            except Exception as e:
                console.print(f"[red]✗ Connection failed:[/red] {e}")

    asyncio.run(_test())


@cli.command()
def crossplatform_scan() -> None:
    """Run a single cross-platform scan."""
    setup_logging("INFO")

    async def _scan() -> None:
        from rarb.scanner.crossplatform_scanner import CrossPlatformScanner

        console.print("[bold]Running cross-platform scan...[/bold]\n")

        settings = get_settings()
        if not settings.is_kalshi_enabled():
            console.print("[red]Error:[/red] Kalshi credentials not configured.")
            return

        async with CrossPlatformScanner() as scanner:
            opportunities = await scanner.scan_once()

            stats = scanner.get_stats()
            console.print(f"[dim]Polymarket markets:[/dim] {stats['poly_markets']}")
            console.print(f"[dim]Kalshi markets:[/dim] {stats['kalshi_markets']}")
            console.print(f"[dim]Matched events:[/dim] {stats['matched_events']}")
            console.print()

            if not opportunities:
                console.print("[yellow]No cross-platform arbitrage opportunities found[/yellow]")
                return

            table = Table(title="Cross-Platform Opportunities")
            table.add_column("Polymarket", style="cyan", max_width=30)
            table.add_column("Kalshi", style="magenta")
            table.add_column("Poly Price", justify="right")
            table.add_column("Kalshi Price", justify="right")
            table.add_column("Spread", justify="right", style="green")
            table.add_column("Direction", max_width=20)

            for opp in opportunities:
                table.add_row(
                    opp.match.polymarket.question[:30],
                    opp.match.kalshi.ticker,
                    f"${float(opp.poly_price):.2f}",
                    f"${float(opp.kalshi_price):.2f}",
                    f"{float(opp.spread_pct) * 100:.1f}%",
                    opp.direction.replace("_", " "),
                )

            console.print(table)

    asyncio.run(_scan())


@cli.command()
def status() -> None:
    """Show bot status, balances, and recent activity."""
    setup_logging("WARNING")

    async def _status() -> None:
        from rarb.tracking.portfolio import PortfolioTracker
        from rarb.tracking.trades import TradeLog

        settings = get_settings()
        tracker = PortfolioTracker()
        trade_log = TradeLog()

        console.print("\n[bold]rarb Bot Status[/bold]\n")

        # Current balances
        console.print("[bold cyan]Balances[/bold cyan]")
        balances = await tracker.get_current_balances()

        balance_table = Table(show_header=False, box=None)
        balance_table.add_column("Platform", style="dim")
        balance_table.add_column("Balance", justify="right")

        if balances["polymarket_usdc"] > 0:
            balance_table.add_row("Polymarket (USDC)", f"${balances['polymarket_usdc']:.2f}")
        if balances["kalshi_usd"] > 0:
            balance_table.add_row("Kalshi (USD)", f"${balances['kalshi_usd']:.2f}")

        balance_table.add_row("[bold]Total[/bold]", f"[bold]${balances['total_usd']:.2f}[/bold]")
        console.print(balance_table)

        # Record snapshot
        from rarb.tracking.portfolio import BalanceSnapshot
        snapshot = BalanceSnapshot(
            timestamp=balances["timestamp"],
            polymarket_usdc=balances["polymarket_usdc"],
            kalshi_usd=balances["kalshi_usd"],
            total_usd=balances["total_usd"],
        )
        tracker.record_snapshot(snapshot)

        console.print()

        # Recent trades
        console.print("[bold cyan]Recent Trades[/bold cyan]")
        trades = trade_log.get_trades(limit=10)

        if not trades:
            console.print("[dim]No trades recorded yet[/dim]")
        else:
            trade_table = Table()
            trade_table.add_column("Time", style="dim")
            trade_table.add_column("Platform")
            trade_table.add_column("Market", max_width=25)
            trade_table.add_column("Side")
            trade_table.add_column("Price", justify="right")
            trade_table.add_column("Size", justify="right")

            for t in trades:
                time_str = t.timestamp.split("T")[1][:8] if "T" in t.timestamp else t.timestamp
                side_color = "green" if t.side == "buy" else "red"
                trade_table.add_row(
                    time_str,
                    t.platform,
                    t.market_name[:25],
                    f"[{side_color}]{t.side.upper()} {t.outcome.upper()}[/{side_color}]",
                    f"${t.price:.3f}",
                    f"${t.size:.2f}",
                )

            console.print(trade_table)

        console.print()

        # Trading summary
        console.print("[bold cyan]Summary[/bold cyan]")
        summary = trade_log.get_all_time_summary()

        if summary["trade_count"] > 0:
            console.print(f"[dim]Total trades:[/dim] {summary['trade_count']}")
            console.print(f"[dim]Total cost:[/dim] ${summary['total_cost']:.2f}")
            console.print(f"[dim]Expected profit:[/dim] ${summary['expected_profit']:.2f}")
        else:
            console.print("[dim]No trading activity yet[/dim]")

        console.print()

        # Mode
        mode = "[yellow]DRY RUN[/yellow]" if settings.dry_run else "[red]LIVE[/red]"
        console.print(f"[dim]Mode:[/dim] {mode}")

    asyncio.run(_status())


@cli.command()
def balance() -> None:
    """Show current balances on all platforms."""
    setup_logging("WARNING")

    async def _balance() -> None:
        from rarb.tracking.portfolio import PortfolioTracker

        tracker = PortfolioTracker()
        console.print("\n[bold]Fetching balances...[/bold]\n")

        balances = await tracker.get_current_balances()

        table = Table(title="Platform Balances")
        table.add_column("Platform", style="cyan")
        table.add_column("Balance", justify="right")
        table.add_column("Currency")

        if balances["polymarket_usdc"] > 0 or True:  # Always show
            table.add_row("Polymarket", f"${balances['polymarket_usdc']:.2f}", "USDC")

        if balances["kalshi_usd"] > 0 or True:  # Always show
            table.add_row("Kalshi", f"${balances['kalshi_usd']:.2f}", "USD")

        console.print(table)
        console.print(f"\n[bold]Total:[/bold] ${balances['total_usd']:.2f}")

    asyncio.run(_balance())


@cli.command()
def approve_redemption() -> None:
    """Approve Polymarket exchange contracts for redemption.

    This is required once before you can redeem resolved positions.
    Sets approval for both CTFExchange and NegRiskCTFExchange.
    """
    setup_logging("INFO")
    settings = get_settings()

    if not settings.private_key:
        console.print("[red]Error: PRIVATE_KEY not configured in .env[/red]")
        return

    if not settings.wallet_address:
        console.print("[red]Error: WALLET_ADDRESS not configured in .env[/red]")
        return

    console.print("\n[bold]Setting up redemption approvals...[/bold]\n")
    console.print(f"Wallet: {settings.wallet_address}")

    try:
        from web3 import Web3

        # Polymarket contracts on Polygon
        CTF_ADDRESS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"  # Conditional Tokens
        NEG_RISK_CTF_EXCHANGE = "0xC5d563A36AE78145C45a50134d48A1215220f80a"
        CTF_EXCHANGE = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
        NEG_RISK_ADAPTER = "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296"

        # ERC1155 setApprovalForAll ABI
        APPROVAL_ABI = [
            {
                "inputs": [
                    {"name": "operator", "type": "address"},
                    {"name": "approved", "type": "bool"}
                ],
                "name": "setApprovalForAll",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            },
            {
                "inputs": [
                    {"name": "account", "type": "address"},
                    {"name": "operator", "type": "address"}
                ],
                "name": "isApprovedForAll",
                "outputs": [{"name": "", "type": "bool"}],
                "stateMutability": "view",
                "type": "function"
            }
        ]

        w3 = Web3(Web3.HTTPProvider(settings.polygon_rpc_url))
        wallet = Web3.to_checksum_address(settings.wallet_address)
        private_key = settings.private_key.get_secret_value()

        ctf = w3.eth.contract(address=Web3.to_checksum_address(CTF_ADDRESS), abi=APPROVAL_ABI)

        operators = [
            ("NegRiskCTFExchange", NEG_RISK_CTF_EXCHANGE),
            ("CTFExchange", CTF_EXCHANGE),
            ("NegRiskAdapter", NEG_RISK_ADAPTER),
        ]

        for name, operator_addr in operators:
            operator = Web3.to_checksum_address(operator_addr)

            # Check if already approved
            is_approved = ctf.functions.isApprovedForAll(wallet, operator).call()

            if is_approved:
                console.print(f"[green]✓[/green] {name}: Already approved")
                continue

            console.print(f"[yellow]→[/yellow] {name}: Setting approval...")

            # Build and send transaction
            nonce = w3.eth.get_transaction_count(wallet)
            gas_price = w3.eth.gas_price

            tx = ctf.functions.setApprovalForAll(operator, True).build_transaction({
                'from': wallet,
                'nonce': nonce,
                'gas': 100000,
                'gasPrice': int(gas_price * 1.1),  # 10% buffer
                'chainId': 137,
            })

            signed = w3.eth.account.sign_transaction(tx, private_key)
            tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)

            console.print(f"  TX: {tx_hash.hex()}")

            # Wait for confirmation
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            if receipt['status'] == 1:
                console.print(f"[green]✓[/green] {name}: Approved successfully")
            else:
                console.print(f"[red]✗[/red] {name}: Transaction failed")

        console.print("\n[bold green]Redemption approvals complete![/bold green]")
        console.print("You can now redeem resolved positions.\n")

    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]\n")


@cli.command()
@click.option("--limit", default=20, help="Number of trades to show")
@click.option("--platform", type=click.Choice(["polymarket", "kalshi"]), help="Filter by platform")
def trades(limit: int, platform: Optional[str]) -> None:
    """Show trade history."""
    from rarb.tracking.trades import TradeLog

    trade_log = TradeLog()
    recent = trade_log.get_trades(limit=limit, platform=platform)

    if not recent:
        console.print("\n[yellow]No trades recorded yet[/yellow]\n")
        return

    table = Table(title=f"Recent Trades (showing {len(recent)})")
    table.add_column("Time", style="dim")
    table.add_column("Platform")
    table.add_column("Market", max_width=30)
    table.add_column("Action")
    table.add_column("Price", justify="right")
    table.add_column("Size", justify="right")
    table.add_column("Expected P/L", justify="right")

    for t in recent:
        time_str = t.timestamp.split("T")[0] + " " + t.timestamp.split("T")[1][:8] if "T" in t.timestamp else t.timestamp
        side_color = "green" if t.side == "buy" else "red"
        pl_str = f"${t.profit_expected:.2f}" if t.profit_expected else "-"

        table.add_row(
            time_str,
            t.platform,
            t.market_name[:30],
            f"[{side_color}]{t.side.upper()} {t.outcome.upper()}[/{side_color}]",
            f"${t.price:.3f}",
            f"${t.size:.2f}",
            pl_str,
        )

    console.print(table)

    # Summary
    summary = trade_log.get_all_time_summary()
    console.print(f"\n[dim]Total trades:[/dim] {summary['trade_count']}")
    console.print(f"[dim]Total invested:[/dim] ${summary['total_cost']:.2f}")
    console.print(f"[dim]Expected profit:[/dim] ${summary['expected_profit']:.2f}")


@cli.command()
def pnl() -> None:
    """Show profit/loss summary."""
    from datetime import datetime, timedelta
    from rarb.tracking.portfolio import PortfolioTracker
    from rarb.tracking.trades import TradeLog

    tracker = PortfolioTracker()
    trade_log = TradeLog()

    console.print("\n[bold]Profit & Loss Summary[/bold]\n")

    # Today's trades
    today_summary = trade_log.get_daily_summary()
    console.print("[bold cyan]Today[/bold cyan]")
    console.print(f"  Trades: {today_summary['trade_count']}")
    console.print(f"  Cost: ${today_summary['total_cost']:.2f}")
    console.print(f"  Expected profit: ${today_summary['expected_profit']:.2f}")
    console.print()

    # All-time
    all_time = trade_log.get_all_time_summary()
    console.print("[bold cyan]All Time[/bold cyan]")
    console.print(f"  Total trades: {all_time['trade_count']}")
    console.print(f"  Total invested: ${all_time['total_cost']:.2f}")
    console.print(f"  Expected profit: ${all_time['expected_profit']:.2f}")

    if all_time['first_trade']:
        console.print(f"  First trade: {all_time['first_trade'][:10]}")


@cli.command()
def redeem() -> None:
    """Redeem resolved positions back to USDC."""
    setup_logging("INFO")

    async def _redeem() -> None:
        from rarb.executor.redemption import get_redeemable_positions, redeem_all_positions

        settings = get_settings()

        if not settings.wallet_address:
            console.print("[red]Error:[/red] No wallet address configured")
            return

        console.print("\n[bold]Checking for redeemable positions...[/bold]\n")

        # First show what we'll redeem
        positions = await get_redeemable_positions(settings.wallet_address)

        if not positions:
            console.print("[yellow]No positions to redeem[/yellow]")
            return

        table = Table(title="Redeemable Positions")
        table.add_column("Market", max_width=40)
        table.add_column("Outcome")
        table.add_column("Size", justify="right")
        table.add_column("Value", justify="right")

        total_value = 0
        for p in positions:
            value = float(p.get("currentValue", 0))
            total_value += value
            table.add_row(
                p.get("title", "Unknown")[:40],
                p.get("outcome", "?"),
                str(p.get("size", 0)),
                f"${value:.2f}",
            )

        console.print(table)
        console.print(f"\n[bold]Total to redeem:[/bold] ${total_value:.2f}\n")

        # Confirm
        if settings.dry_run:
            console.print("[yellow]DRY RUN mode - no actual redemption will occur[/yellow]")
            return

        if not click.confirm("Proceed with redemption?"):
            console.print("[dim]Cancelled[/dim]")
            return

        console.print("\n[bold]Redeeming positions...[/bold]\n")
        result = await redeem_all_positions()

        if result.get("error"):
            console.print(f"[red]Error:[/red] {result['error']}")
            return

        console.print(f"[green]Successfully redeemed:[/green] {result['redeemed']} positions")
        if result.get("failed"):
            console.print(f"[red]Failed:[/red] {result['failed']} positions")
        console.print(f"[bold]Total value:[/bold] ${result['total_value']:.2f}")

    asyncio.run(_redeem())


@cli.command()
def positions() -> None:
    """Show current positions from Polymarket."""
    setup_logging("WARNING")

    async def _positions() -> None:
        from rarb.executor.redemption import get_redeemable_positions
        import httpx

        settings = get_settings()

        if not settings.wallet_address:
            console.print("[red]Error:[/red] No wallet address configured")
            return

        console.print("\n[bold]Fetching positions...[/bold]\n")

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://data-api.polymarket.com/positions?user={settings.wallet_address}"
            )
            positions = resp.json()

        if not positions:
            console.print("[yellow]No positions found[/yellow]")
            return

        # Open positions
        open_positions = [p for p in positions if not p.get("redeemable") and float(p.get("size", 0)) > 0]
        if open_positions:
            table = Table(title="Open Positions")
            table.add_column("Market", max_width=40)
            table.add_column("Outcome")
            table.add_column("Size", justify="right")
            table.add_column("Avg Price", justify="right")
            table.add_column("Current", justify="right")
            table.add_column("P&L", justify="right")

            for p in open_positions:
                pnl = float(p.get("cashPnl", 0))
                pnl_color = "green" if pnl >= 0 else "red"
                table.add_row(
                    p.get("title", "Unknown")[:40],
                    p.get("outcome", "?"),
                    str(p.get("size", 0)),
                    f"${float(p.get('avgPrice', 0)):.3f}",
                    f"${float(p.get('curPrice', 0)):.3f}",
                    f"[{pnl_color}]${pnl:.2f}[/{pnl_color}]",
                )

            console.print(table)
            console.print()

        # Redeemable positions
        redeemable = [p for p in positions if p.get("redeemable") and float(p.get("size", 0)) > 0]
        if redeemable:
            table = Table(title="Redeemable Positions (Resolved)")
            table.add_column("Market", max_width=40)
            table.add_column("Outcome")
            table.add_column("Size", justify="right")
            table.add_column("Value", justify="right")
            table.add_column("P&L", justify="right")

            total_value = 0
            for p in redeemable:
                value = float(p.get("currentValue", 0))
                total_value += value
                pnl = float(p.get("cashPnl", 0))
                pnl_color = "green" if pnl >= 0 else "red"
                table.add_row(
                    p.get("title", "Unknown")[:40],
                    p.get("outcome", "?"),
                    str(p.get("size", 0)),
                    f"${value:.2f}",
                    f"[{pnl_color}]${pnl:.2f}[/{pnl_color}]",
                )

            console.print(table)
            console.print(f"\n[bold]Total redeemable:[/bold] ${total_value:.2f}")
            console.print("[dim]Run 'rarb redeem' to claim these positions[/dim]")

    asyncio.run(_positions())


@cli.command()
@click.option("--polygonscan-api-key", envvar="POLYGONSCAN_API_KEY", help="Polygonscan API key")
@click.option("--dry-run", is_flag=True, help="Show what would be inserted without inserting")
def backfill_balance(polygonscan_api_key: Optional[str], dry_run: bool) -> None:
    """Backfill historical balance data from on-chain USDC transfers."""
    import httpx
    from datetime import datetime
    from collections import defaultdict

    settings = get_settings()

    if not settings.wallet_address:
        console.print("[red]Error:[/red] No wallet address configured")
        return

    if not polygonscan_api_key:
        console.print("[red]Error:[/red] No Polygonscan API key provided")
        console.print("[dim]Set POLYGONSCAN_API_KEY env var or use --polygonscan-api-key[/dim]")
        return

    async def _backfill():
        wallet = settings.wallet_address.lower()
        usdc_bridged = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"

        console.print(f"\n[bold]Fetching USDC transfers from Polygonscan...[/bold]")
        console.print(f"[dim]Wallet: {wallet}[/dim]\n")

        # Fetch all USDC transfers
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://api.etherscan.io/v2/api",
                params={
                    "chainid": "137",
                    "module": "account",
                    "action": "tokentx",
                    "contractaddress": usdc_bridged,
                    "address": wallet,
                    "page": "1",
                    "offset": "1000",
                    "sort": "asc",
                    "apikey": polygonscan_api_key,
                },
            )
            data = resp.json()

        if data.get("status") != "1":
            console.print(f"[red]API Error:[/red] {data.get('message', 'Unknown error')}")
            return

        txs = data.get("result", [])
        console.print(f"Found [bold]{len(txs)}[/bold] USDC transfers\n")

        # Calculate daily balance changes
        daily_changes: dict[str, float] = defaultdict(float)
        for tx in txs:
            ts = int(tx["timeStamp"])
            date = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
            amount = int(tx["value"]) / 1e6

            if tx["to"].lower() == wallet:
                daily_changes[date] += amount  # incoming
            elif tx["from"].lower() == wallet:
                daily_changes[date] -= amount  # outgoing

        # Calculate cumulative balance for each day
        from rarb.data.repositories import PortfolioRepository

        balance = 0.0
        inserted = 0

        table = Table(title="Daily Balance History")
        table.add_column("Date")
        table.add_column("Change", justify="right")
        table.add_column("Balance", justify="right")
        table.add_column("Status")

        for date in sorted(daily_changes.keys()):
            change = daily_changes[date]
            balance += change

            # Create end-of-day timestamp
            timestamp = f"{date}T23:59:59"

            if dry_run:
                status = "[yellow]would insert[/yellow]"
            else:
                await PortfolioRepository.insert(
                    timestamp=timestamp,
                    polymarket_usdc=balance,
                    total_usd=balance,  # USDC only, no positions data
                    positions_value=0.0,
                )
                inserted += 1
                status = "[green]inserted[/green]"

            change_color = "green" if change >= 0 else "red"
            table.add_row(
                date,
                f"[{change_color}]{change:+.2f}[/{change_color}]",
                f"${balance:.2f}",
                status,
            )

        console.print(table)

        if dry_run:
            console.print(f"\n[yellow]Dry run:[/yellow] Would insert {len(daily_changes)} snapshots")
        else:
            console.print(f"\n[green]Success:[/green] Inserted {inserted} daily balance snapshots")

    asyncio.run(_backfill())


@cli.command()
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--port", type=int, help="Port to run on (default: from config)")
def dashboard(host: str, port: Optional[int]) -> None:
    """Run the web dashboard."""
    settings = get_settings()

    actual_port = port or settings.dashboard_port

    console.print(f"\n[bold]Starting rarb Dashboard[/bold]")
    console.print(f"[dim]URL:[/dim] http://{host}:{actual_port}")
    if settings.dashboard_password:
        console.print(f"[dim]Username:[/dim] {settings.dashboard_username}")
        console.print(f"[dim]Password:[/dim] {'*' * len(settings.dashboard_password)}")
    else:
        console.print(f"[dim]Auth:[/dim] Disabled (no password configured)")
    console.print()

    from rarb.dashboard import run_dashboard
    run_dashboard(host=host, port=actual_port)


def main() -> None:
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
