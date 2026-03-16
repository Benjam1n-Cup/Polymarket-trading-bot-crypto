#!/usr/bin/env python3
"""Migrate existing JSON/JSONL data to SQLite database.

This script reads data from the old JSON file-based storage and
inserts it into the new SQLite database.

Files migrated:
- scanner_stats.json -> scanner_stats table
- scanner_alerts.json -> alerts table
- orders.json -> executions table
- trades.jsonl -> trades table
- portfolio.jsonl -> portfolio_snapshots table
"""

import asyncio
import json
import shutil
from datetime import datetime
from pathlib import Path

# Add src to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rarb.data.database import init_async_db, get_async_connection


DATA_DIR = Path.home() / ".rarb"
BACKUP_DIR = DATA_DIR / "backup_json"


async def migrate_scanner_stats() -> int:
    """Migrate scanner_stats.json to database."""
    stats_file = DATA_DIR / "scanner_stats.json"
    if not stats_file.exists():
        print("  No scanner_stats.json found, skipping")
        return 0

    with open(stats_file) as f:
        stats = json.load(f)

    conn = await get_async_connection()
    await conn.execute("""
        INSERT OR REPLACE INTO scanner_stats (
            id, markets, price_updates, arbitrage_alerts,
            ws_connected, ws_connections, subscribed_tokens, last_update
        ) VALUES (1, ?, ?, ?, ?, ?, ?, ?)
    """, (
        stats.get("markets", 0),
        stats.get("price_updates", 0),
        stats.get("arbitrage_alerts", 0),
        1 if stats.get("ws_connected") else 0,
        json.dumps(stats.get("ws_connections")) if stats.get("ws_connections") else None,
        stats.get("subscribed_tokens", 0),
        stats.get("last_update"),
    ))
    await conn.commit()
    print("  Migrated scanner stats")
    return 1


async def migrate_alerts() -> int:
    """Migrate scanner_alerts.json to database."""
    alerts_file = DATA_DIR / "scanner_alerts.json"
    if not alerts_file.exists():
        print("  No scanner_alerts.json found, skipping")
        return 0

    with open(alerts_file) as f:
        alerts = json.load(f)

    if not alerts:
        print("  No alerts to migrate")
        return 0

    conn = await get_async_connection()
    count = 0
    for alert in alerts:
        await conn.execute("""
            INSERT INTO alerts (
                market, yes_ask, no_ask, combined, profit, timestamp,
                platform, days_until_resolution, resolution_date,
                first_seen, duration_secs
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            alert.get("market", ""),
            alert.get("yes_ask", 0),
            alert.get("no_ask", 0),
            alert.get("combined", 0),
            alert.get("profit", 0),
            alert.get("timestamp", ""),
            alert.get("platform", "polymarket"),
            alert.get("days_until_resolution"),
            alert.get("resolution_date"),
            alert.get("first_seen"),
            alert.get("duration_secs"),
        ))
        count += 1

    await conn.commit()
    print(f"  Migrated {count} alerts")
    return count


async def migrate_orders() -> int:
    """Migrate orders.json (recent_executions) to database."""
    orders_file = DATA_DIR / "orders.json"
    if not orders_file.exists():
        print("  No orders.json found, skipping")
        return 0

    with open(orders_file) as f:
        data = json.load(f)

    executions = data.get("recent_executions", [])
    if not executions:
        print("  No executions to migrate")
        return 0

    conn = await get_async_connection()
    count = 0
    for e in executions:
        yes_order = e.get("yes_order", {})
        no_order = e.get("no_order", {})

        await conn.execute("""
            INSERT INTO executions (
                timestamp, market, status,
                yes_order_id, yes_status, yes_price, yes_size, yes_filled_size,
                no_order_id, no_status, no_price, no_size, no_filled_size,
                total_cost, expected_profit
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            e.get("timestamp", ""),
            e.get("market", ""),
            e.get("status", ""),
            yes_order.get("order_id"),
            yes_order.get("status", ""),
            yes_order.get("price", 0),
            yes_order.get("size", 0),
            yes_order.get("filled_size", 0),
            no_order.get("order_id"),
            no_order.get("status", ""),
            no_order.get("price", 0),
            no_order.get("size", 0),
            no_order.get("filled_size", 0),
            e.get("total_cost", 0),
            e.get("expected_profit", 0),
        ))
        count += 1

    await conn.commit()
    print(f"  Migrated {count} executions")
    return count


async def migrate_trades() -> int:
    """Migrate trades.jsonl to database."""
    trades_file = DATA_DIR / "trades.jsonl"
    if not trades_file.exists():
        print("  No trades.jsonl found, skipping")
        return 0

    conn = await get_async_connection()
    count = 0

    with open(trades_file) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                trade = json.loads(line)
                await conn.execute("""
                    INSERT INTO trades (
                        timestamp, platform, market_id, market_name,
                        side, outcome, price, size, cost,
                        order_id, strategy, profit_expected, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    trade.get("timestamp", ""),
                    trade.get("platform", ""),
                    trade.get("market_id", ""),
                    trade.get("market_name", ""),
                    trade.get("side", ""),
                    trade.get("outcome", ""),
                    trade.get("price", 0),
                    trade.get("size", 0),
                    trade.get("cost", 0),
                    trade.get("order_id"),
                    trade.get("strategy", "single_market"),
                    trade.get("profit_expected"),
                    trade.get("notes"),
                ))
                count += 1
            except json.JSONDecodeError:
                print(f"  Warning: Could not parse line: {line[:50]}...")

    await conn.commit()
    print(f"  Migrated {count} trades")
    return count


async def migrate_portfolio() -> int:
    """Migrate portfolio.jsonl to database."""
    portfolio_file = DATA_DIR / "portfolio.jsonl"
    if not portfolio_file.exists():
        print("  No portfolio.jsonl found, skipping")
        return 0

    conn = await get_async_connection()
    count = 0

    with open(portfolio_file) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                snapshot = json.loads(line)
                await conn.execute("""
                    INSERT INTO portfolio_snapshots (
                        timestamp, polymarket_usdc, total_usd, positions_value
                    ) VALUES (?, ?, ?, ?)
                """, (
                    snapshot.get("timestamp", ""),
                    snapshot.get("polymarket_usdc", 0),
                    snapshot.get("total_usd", 0),
                    snapshot.get("positions_value", 0),
                ))
                count += 1
            except json.JSONDecodeError:
                print(f"  Warning: Could not parse line: {line[:50]}...")

    await conn.commit()
    print(f"  Migrated {count} portfolio snapshots")
    return count


def backup_files():
    """Backup original JSON files."""
    if not DATA_DIR.exists():
        print("No data directory found, nothing to backup")
        return

    BACKUP_DIR.mkdir(exist_ok=True)

    files_to_backup = [
        "scanner_stats.json",
        "scanner_alerts.json",
        "orders.json",
        "trades.jsonl",
        "portfolio.jsonl",
    ]

    backed_up = 0
    for filename in files_to_backup:
        src = DATA_DIR / filename
        if src.exists():
            dst = BACKUP_DIR / f"{filename}.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(src, dst)
            print(f"  Backed up {filename}")
            backed_up += 1

    print(f"Backed up {backed_up} files to {BACKUP_DIR}")


async def main():
    """Run the migration."""
    print("=" * 60)
    print("rarb Data Migration: JSON -> SQLite")
    print("=" * 60)

    if not DATA_DIR.exists():
        print(f"\nNo data directory found at {DATA_DIR}")
        print("Nothing to migrate.")
        return

    # Initialize database
    print("\n1. Initializing SQLite database...")
    await init_async_db()
    print(f"   Database: {DATA_DIR / 'rarb.db'}")

    # Backup existing files
    print("\n2. Backing up existing JSON files...")
    backup_files()

    # Run migrations
    print("\n3. Migrating data...")

    print("\n   Scanner Stats:")
    await migrate_scanner_stats()

    print("\n   Alerts:")
    await migrate_alerts()

    print("\n   Orders/Executions:")
    await migrate_orders()

    print("\n   Trades:")
    await migrate_trades()

    print("\n   Portfolio Snapshots:")
    await migrate_portfolio()

    print("\n" + "=" * 60)
    print("Migration complete!")
    print("=" * 60)
    print(f"\nDatabase created at: {DATA_DIR / 'rarb.db'}")
    print(f"Original files backed up to: {BACKUP_DIR}")
    print("\nYou can now run rarb with the new SQLite storage.")


if __name__ == "__main__":
    asyncio.run(main())
