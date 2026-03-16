#!/usr/bin/env python3
"""Check if market uses neg_risk."""

from rarb.config import get_settings
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds

settings = get_settings()

token_id = "104173557214744537570424345347209544585775842950109756851652855913015295701992"

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

# Check the order builder's neg_risk detection
print("Checking market neg_risk status...")
market_info = client.get_order_book(token_id)
print(f"Order book: {market_info}")

# Check if there's neg_risk info available
try:
    neg_risk = client.get_neg_risk(token_id)
    print(f"neg_risk: {neg_risk}")
except Exception as e:
    print(f"get_neg_risk failed: {e}")

# Check what exchange the order builder uses
print("\nChecking order builder exchange...")
from py_clob_client.order_builder.builder import OrderBuilder
from py_clob_client.signer import Signer

signer = Signer(settings.private_key.get_secret_value(), 137)
print(f"Default exchange (neg_risk=False): 0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E")
print(f"NegRisk exchange (neg_risk=True):  0xC5d563A36AE78145C45a50134d48A1215220f80a")
