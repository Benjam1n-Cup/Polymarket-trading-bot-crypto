#!/usr/bin/env python3
"""Test order placement and cancellation on Polymarket."""

import os
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds, OrderArgs

host = "https://clob.polymarket.com"
chain_id = 137

creds = ApiCreds(
    api_key=os.environ["POLY_API_KEY"],
    api_secret=os.environ["POLY_API_SECRET"],
    api_passphrase=os.environ["POLY_API_PASSPHRASE"],
)

client = ClobClient(
    host=host,
    key=os.environ["PRIVATE_KEY"],
    chain_id=chain_id,
    creds=creds,
)

# Get a market to test with
print("Finding a test market...")
markets = client.get_sampling_markets(next_cursor="")
if markets and "data" in markets:
    test_market = markets["data"][0]
    question = test_market.get("question", "Unknown")
    print(f"Using market: {question[:60]}")
    tokens = test_market.get("tokens", [])
    if tokens:
        token_id = tokens[0].get("token_id")
        print(f"Token ID: {token_id[:20]}...")

        # Place a small order at a very low price (will not fill)
        print("\nPlacing test order: BUY 5 shares at $0.01...")
        try:
            order_args = OrderArgs(
                token_id=token_id,
                price=0.01,
                size=5.0,  # Minimum size is 5
                side="BUY",
            )
            result = client.create_and_post_order(order_args)
            print(f"Order result: {result}")

            # Cancel the order immediately
            if result:
                order_id = result.get("orderID") or result.get("id")
                if order_id:
                    print(f"\nCancelling test order {order_id}...")
                    cancel_result = client.cancel(order_id)
                    print(f"Cancel result: {cancel_result}")
                    print("\n✓ Test order placed and cancelled successfully!")
        except Exception as e:
            print(f"Order error: {e}")
else:
    print("Could not find test market")
