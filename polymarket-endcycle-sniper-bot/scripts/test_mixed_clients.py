#!/usr/bin/env python3
"""Test using py_clob_client to create order, async_clob to submit."""

import json
import asyncio
from rarb.executor.async_clob import create_async_clob_client, SignedOrder
from rarb.config import get_settings
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, ApiCreds

settings = get_settings()

token_id = "104173557214744537570424345347209544585775842950109756851652855913015295701992"


async def main():
    # Create order using py_clob_client
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
    py_order = sync_client.create_order(order_args)
    py_dict = py_order.dict()
    print("py_clob_client order:")
    print(json.dumps(py_dict, indent=2))

    # Convert to our SignedOrder format
    side_int = 0 if py_dict["side"] == "BUY" else 1
    signed_order = SignedOrder(
        salt=py_dict["salt"],
        maker=py_dict["maker"],
        signer=py_dict["signer"],
        taker=py_dict["taker"],
        token_id=py_dict["tokenId"],
        maker_amount=int(py_dict["makerAmount"]),
        taker_amount=int(py_dict["takerAmount"]),
        expiration=int(py_dict["expiration"]),
        nonce=int(py_dict["nonce"]),
        fee_rate_bps=int(py_dict["feeRateBps"]),
        side=side_int,
        signature_type=py_dict["signatureType"],
        signature=py_dict["signature"],
    )

    # Submit using async client
    client = await create_async_clob_client()
    try:
        print("\nSubmitting py_clob_client order through async client...")
        result = await client.post_order(signed_order)
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await client.close()


asyncio.run(main())
