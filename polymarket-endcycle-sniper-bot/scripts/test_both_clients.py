#!/usr/bin/env python3
"""Test order submission with both clients."""

import asyncio
import json
from rarb.executor.async_clob import create_async_clob_client
from rarb.config import get_settings
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, ApiCreds

settings = get_settings()

# Use a known liquid market - same as compare_orders.py
token_id = "104173557214744537570424345347209544585775842950109756851652855913015295701992"

# First test py_clob_client
print("=== Testing py_clob_client ===")
creds = ApiCreds(
    api_key=settings.poly_api_key,
    api_secret=settings.poly_api_secret.get_secret_value(),
    api_passphrase=settings.poly_api_passphrase.get_secret_value(),
)
sync_client = ClobClient(
    "https://clob.polymarket.com",
    key=settings.private_key.get_secret_value(),
    chain_id=137,
    creds=creds,
)

order_args = OrderArgs(
    token_id=token_id,
    price=0.01,
    size=1.0,
    side="BUY",
)

try:
    result = sync_client.create_and_post_order(order_args)
    print(f"SUCCESS: {result}")

    # Cancel it
    if hasattr(result, 'orderID') or 'orderID' in str(result):
        order_id = result.get('orderID') if isinstance(result, dict) else None
        if order_id:
            cancel = sync_client.cancel(order_id)
            print(f"Cancelled: {cancel}")
except Exception as e:
    print(f"py_clob_client ERROR: {e}")


# Now test async_clob
print("\n=== Testing async_clob ===")


async def test_async():
    client = await create_async_clob_client()
    if not client:
        print("Failed to create async client")
        return

    try:
        # Use neg_risk=False since this appears to be a regular market
        # Price * size must be >= $1 for marketable orders
        result = await client.submit_order(
            token_id=token_id,
            side="BUY",
            price=0.01,
            size=100.0,  # 0.01 * 100 = $1 minimum
            neg_risk=False,
        )
        print(f"SUCCESS: {result}")

        # Cancel it
        order_id = result.get('orderID')
        if order_id:
            cancel = await client.cancel_order(order_id)
            print(f"Cancelled: {cancel}")
    except Exception as e:
        print(f"async_clob ERROR: {e}")
    finally:
        await client.close()


asyncio.run(test_async())
