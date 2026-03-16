#!/usr/bin/env python3
"""Cancel all orders and sell position using py_clob_client."""

import httpx
from rarb.config import get_settings
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, ApiCreds

settings = get_settings()

# Build proxy URL
proxy_url = None
if settings.socks5_proxy_host:
    proxy_url = (
        f"socks5://{settings.socks5_proxy_user}:{settings.socks5_proxy_pass.get_secret_value()}"
        f"@{settings.socks5_proxy_host}:{settings.socks5_proxy_port}"
    )
    print(f"Using proxy: {settings.socks5_proxy_host}")

token_id = "104173557214744537570424345347209544585775842950109756851652855913015295701992"

creds = ApiCreds(
    api_key=settings.poly_api_key,
    api_secret=settings.poly_api_secret.get_secret_value(),
    api_passphrase=settings.poly_api_passphrase.get_secret_value(),
)

# py_clob_client doesn't support socks5 proxy directly, so we'll use httpx transport
# For now, just proceed without proxy for this cleanup
client = ClobClient(
    "https://clob.polymarket.com",
    key=settings.private_key.get_secret_value(),
    chain_id=137,
    creds=creds,
)

print("Cancelling all orders...")
try:
    result = client.cancel_all()
    print(f"Cancel result: {result}")
except Exception as e:
    print(f"Cancel error: {e}")

# Check what we have
print("\nChecking open orders...")
try:
    orders = client.get_orders()
    print(f"Open orders: {orders}")
except Exception as e:
    print(f"Error checking orders: {e}")

# Try to sell what we have
print("\nPlacing SELL order at $0.50 (very low to ensure fill)...")
try:
    order_args = OrderArgs(
        token_id=token_id,
        price=0.50,  # Very low to ensure fill
        size=100.0,  # Sell all we might have
        side="SELL",
    )
    result = client.create_and_post_order(order_args)
    print(f"SELL result: {result}")
except Exception as e:
    print(f"SELL error: {e}")
