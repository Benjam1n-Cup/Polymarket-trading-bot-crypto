#!/usr/bin/env python3
"""Sell a position on Polymarket."""

import asyncio
import sys
from decimal import Decimal

from rarb.config import get_settings
from rarb.executor.async_clob import AsyncClobClient
from rarb.utils.logging import setup_logging, get_logger

log = get_logger(__name__)


async def sell_position(token_id: str, size: float, price: float) -> None:
    """Sell tokens at specified price."""
    settings = get_settings()
    setup_logging(settings.log_level)

    if settings.dry_run:
        log.warning("DRY RUN mode - no actual trade will be executed")
        print(f"Would sell {size} tokens at ${price}")
        return

    # Build proxy URL if configured
    proxy_url = None
    if settings.socks5_proxy_host and settings.socks5_proxy_port:
        if settings.socks5_proxy_user and settings.socks5_proxy_pass:
            proxy_url = (
                f"socks5://{settings.socks5_proxy_user}:{settings.socks5_proxy_pass.get_secret_value()}"
                f"@{settings.socks5_proxy_host}:{settings.socks5_proxy_port}"
            )
        else:
            proxy_url = f"socks5://{settings.socks5_proxy_host}:{settings.socks5_proxy_port}"
        log.info(f"Using proxy: {settings.socks5_proxy_host}:{settings.socks5_proxy_port}")

    client = AsyncClobClient(
        private_key=settings.private_key.get_secret_value(),
        api_key=settings.poly_api_key,
        api_secret=settings.poly_api_secret.get_secret_value(),
        api_passphrase=settings.poly_api_passphrase.get_secret_value() if settings.poly_api_passphrase else "",
        proxy_url=proxy_url,
    )

    try:
        # Get neg_risk status
        neg_risk = await client.get_neg_risk(token_id)
        log.info(f"Token neg_risk status: {neg_risk}")

        # Submit sell order (SELL = opposite of BUY)
        # For selling YES tokens we bought, we use side="SELL"
        response = await client.submit_order(
            token_id=token_id,
            side="SELL",
            price=price,
            size=size,
            neg_risk=neg_risk,
            order_type="GTC",  # Good til cancelled
        )

        if response.get("success"):
            order_id = response.get("orderID")
            log.info(f"Sell order submitted: {order_id}")
            print(f"✓ Sell order submitted: {order_id}")
            print(f"  Selling {size} tokens at ${price}")
            print(f"  Expected proceeds: ${size * price:.2f}")
        else:
            error = response.get("errorMsg", "Unknown error")
            log.error(f"Sell order failed: {error}")
            print(f"✗ Sell order failed: {error}")

    finally:
        await client.close()


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python sell_position.py <token_id> <size> <price>")
        print("Example: python sell_position.py 1234...5678 100 0.007")
        sys.exit(1)

    token_id = sys.argv[1]
    size = float(sys.argv[2])
    price = float(sys.argv[3])

    print(f"Selling {size} tokens of {token_id[:20]}... at ${price}")
    asyncio.run(sell_position(token_id, size, price))
