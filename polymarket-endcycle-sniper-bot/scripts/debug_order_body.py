#!/usr/bin/env python3
"""Debug the exact order body being sent."""

import json
from rarb.config import get_settings
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, ApiCreds
from py_clob_client.utilities import order_to_json

settings = get_settings()

token_id = "21742633143463906290569050155826241533067272736897614950488156847949938836455"

creds = ApiCreds(
    api_key=settings.poly_api_key,
    api_secret=settings.poly_api_secret.get_secret_value(),
    api_passphrase=settings.poly_api_passphrase.get_secret_value(),
)
client = ClobClient(
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
order = client.create_order(order_args)

# Build the exact body that would be sent
body = order_to_json(order, settings.poly_api_key, "GTC")
print("=== py_clob_client full POST body ===")
print(json.dumps(body, indent=2))
print("\n=== Serialized body (what's actually sent) ===")
print(json.dumps(body, separators=(",", ":"), ensure_ascii=False))
