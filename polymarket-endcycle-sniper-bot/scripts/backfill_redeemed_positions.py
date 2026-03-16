#!/usr/bin/env python3
"""
Backfill redeemed positions from Polymarket activity API.

This script fetches all activity (trades and redemptions) and populates
the closed_positions table with historical data.
"""

import asyncio
from datetime import datetime, timezone

import httpx

from rarb.config import get_settings
from rarb.data.database import init_db, get_db
from rarb.utils.logging import setup_logging, get_logger

log = get_logger(__name__)

DATA_API_URL = "https://data-api.polymarket.com"


async def fetch_all_activity(wallet_address: str) -> list[dict]:
    """Fetch all activity for a wallet."""
    all_activity = []
    offset = 0
    limit = 100

    async with httpx.AsyncClient() as client:
        while True:
            url = f"{DATA_API_URL}/activity?user={wallet_address}&limit={limit}&offset={offset}"
            resp = await client.get(url)

            if resp.status_code != 200:
                log.error("Failed to fetch activity", status=resp.status_code)
                break

            data = resp.json()
            if not data:
                break

            all_activity.extend(data)
            log.info(f"Fetched {len(data)} activities (total: {len(all_activity)})")

            if len(data) < limit:
                break

            offset += limit

    return all_activity


def process_activity(activity: list[dict]) -> list[dict]:
    """
    Process activity to create closed position records.

    Groups trades by conditionId and matches with redemptions.
    """
    # Group trades by conditionId
    trades_by_condition: dict[str, list[dict]] = {}
    redemptions_by_condition: dict[str, dict] = {}

    for item in activity:
        condition_id = item.get("conditionId", "")
        item_type = item.get("type", "")

        if item_type == "TRADE" and item.get("side") == "BUY":
            if condition_id not in trades_by_condition:
                trades_by_condition[condition_id] = []
            trades_by_condition[condition_id].append(item)
        elif item_type == "REDEEM":
            redemptions_by_condition[condition_id] = item

    # Create closed position records for redeemed positions
    closed_positions = []

    for condition_id, redemption in redemptions_by_condition.items():
        trades = trades_by_condition.get(condition_id, [])

        # Calculate totals from trades
        total_size = sum(t.get("size", 0) for t in trades)
        total_cost = sum(t.get("usdcSize", 0) for t in trades)
        avg_price = total_cost / total_size if total_size > 0 else 0

        # Get redemption value
        redemption_value = redemption.get("usdcSize", 0)
        redemption_size = redemption.get("size", 0)

        # Calculate P&L
        realized_pnl = redemption_value - total_cost

        # Determine status
        if redemption_value > 0:
            status = "WON"
        else:
            status = "LOST"

        # Get outcome from trades (redemption doesn't have it)
        outcome = ""
        if trades:
            outcome = trades[0].get("outcome", "")

        # Convert timestamp
        timestamp = datetime.fromtimestamp(
            redemption.get("timestamp", 0), tz=timezone.utc
        ).isoformat()

        closed_positions.append({
            "timestamp": timestamp,
            "market_title": redemption.get("title", ""),
            "outcome": outcome,
            "token_id": trades[0].get("asset", "") if trades else "",
            "condition_id": condition_id,
            "size": redemption_size or total_size,
            "avg_price": avg_price,
            "exit_price": 1.0 if status == "WON" else 0.0,
            "cost_basis": total_cost,
            "realized_value": redemption_value,
            "realized_pnl": realized_pnl,
            "status": status,
            "redeemed": True,
        })

    return closed_positions


def insert_positions(positions: list[dict]) -> int:
    """Insert positions into database."""
    inserted = 0

    with get_db() as conn:
        for pos in positions:
            # Check if already exists
            cursor = conn.execute(
                "SELECT 1 FROM closed_positions WHERE condition_id = ? LIMIT 1",
                (pos["condition_id"],),
            )
            if cursor.fetchone():
                log.debug(f"Skipping existing position: {pos['market_title'][:30]}")
                continue

            conn.execute(
                """
                INSERT INTO closed_positions (
                    timestamp, market_title, outcome, token_id, condition_id,
                    size, avg_price, exit_price, cost_basis, realized_value,
                    realized_pnl, status, redeemed
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pos["timestamp"],
                    pos["market_title"],
                    pos["outcome"],
                    pos["token_id"],
                    pos["condition_id"],
                    pos["size"],
                    pos["avg_price"],
                    pos["exit_price"],
                    pos["cost_basis"],
                    pos["realized_value"],
                    pos["realized_pnl"],
                    pos["status"],
                    1,  # redeemed = True
                ),
            )
            inserted += 1
            log.info(
                f"Inserted: {pos['market_title'][:40]}... "
                f"P&L: ${pos['realized_pnl']:.2f} ({pos['status']})"
            )

    return inserted


async def main():
    setup_logging("INFO")
    settings = get_settings()

    if not settings.wallet_address:
        log.error("No wallet address configured")
        return

    log.info(f"Backfilling redeemed positions for {settings.wallet_address}")

    # Initialize database
    init_db()

    # Fetch all activity
    activity = await fetch_all_activity(settings.wallet_address)
    log.info(f"Total activity fetched: {len(activity)}")

    # Process into closed positions
    positions = process_activity(activity)
    log.info(f"Found {len(positions)} redeemed positions")

    # Insert into database
    inserted = insert_positions(positions)
    log.info(f"Inserted {inserted} new positions")

    # Print summary
    total_pnl = sum(p["realized_pnl"] for p in positions)
    wins = sum(1 for p in positions if p["status"] == "WON")
    losses = sum(1 for p in positions if p["status"] == "LOST")

    log.info(f"Summary: {wins} wins, {losses} losses, Total P&L: ${total_pnl:.2f}")


if __name__ == "__main__":
    asyncio.run(main())
