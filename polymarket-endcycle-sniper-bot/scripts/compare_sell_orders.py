#!/usr/bin/env python3
"""Compare SELL order structures between py_clob_client and async_clob."""

import json
import asyncio
from rarb.executor.async_clob import create_async_clob_client
from rarb.config import get_settings
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, ApiCreds

settings = get_settings()

token_id = "104173557214744537570424345347209544585775842950109756851652855913015295701992"

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

# Create SELL order with py_clob_client
order_args = OrderArgs(
    token_id=token_id,
    price=0.60,
    size=5.0,
    side="SELL",
)
sync_order = sync_client.create_order(order_args)
sync_dict = sync_order.dict()

print("=== py_clob_client SELL order ===")
print(json.dumps(sync_dict, indent=2))


async def get_async_order():
    client = await create_async_clob_client()
    signed = client.sign_order(
        token_id=token_id,
        side="SELL",
        price=0.60,
        size=5.0,
        neg_risk=False,
    )
    await client.close()
    return signed.to_dict()


async_dict = asyncio.run(get_async_order())
print("\n=== async_clob SELL order ===")
print(json.dumps(async_dict, indent=2))

print("\n=== Differences ===")
all_keys = set(list(sync_dict.keys()) + list(async_dict.keys()))
for key in sorted(all_keys):
    sync_val = sync_dict.get(key)
    async_val = async_dict.get(key)
    if sync_val != async_val:
        print(f"{key}:")
        print(f"  sync:  {sync_val}")
        print(f"  async: {async_val}")
