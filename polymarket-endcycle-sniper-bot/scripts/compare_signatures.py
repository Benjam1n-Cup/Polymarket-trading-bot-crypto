#!/usr/bin/env python3
"""Compare signatures for identical order data."""

import json
from eth_account import Account
from eth_account.messages import encode_typed_data
from eth_utils import keccak
from poly_eip712_structs import make_domain, Address, EIP712Struct, Uint
from rarb.config import get_settings

settings = get_settings()
private_key = settings.private_key.get_secret_value()
account = Account.from_key(private_key)

# Use exact same data as py_clob_client
token_id = "104173557214744537570424345347209544585775842950109756851652855913015295701992"
CTF_EXCHANGE = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"

# Fixed test data for SELL order
salt = 12345
maker = account.address
price = 0.60
size = 5.0
maker_amount = 5000000  # size * 1e6
taker_amount = 3000000  # size * price * 1e6


# Method 1: poly_eip712_structs (py_clob_client)
class Order(EIP712Struct):
    salt = Uint(256)
    maker = Address()
    signer = Address()
    taker = Address()
    tokenId = Uint(256)
    makerAmount = Uint(256)
    takerAmount = Uint(256)
    expiration = Uint(256)
    nonce = Uint(256)
    feeRateBps = Uint(256)
    side = Uint(8)
    signatureType = Uint(8)


domain = make_domain(
    name="Polymarket CTF Exchange",
    version="1",
    chainId="137",
    verifyingContract=CTF_EXCHANGE,
)
order = Order(
    salt=salt,
    maker=maker,
    signer=maker,
    taker="0x0000000000000000000000000000000000000000",
    tokenId=int(token_id),
    makerAmount=maker_amount,
    takerAmount=taker_amount,
    expiration=0,
    nonce=0,
    feeRateBps=0,
    side=1,  # SELL
    signatureType=0,
)
signable = order.signable_bytes(domain=domain)
struct_hash = keccak(signable)
sig1 = Account._sign_hash(struct_hash, private_key)
print("=== poly_eip712_structs (py_clob_client) ===")
print(f"Struct hash: 0x{struct_hash.hex()}")
print(f"Signature: 0x{sig1.signature.hex()}")


# Method 2: eth_account encode_typed_data (my async_clob)
ORDER_DOMAIN = {
    "name": "Polymarket CTF Exchange",
    "version": "1",
    "chainId": 137,
    "verifyingContract": CTF_EXCHANGE,
}
ORDER_TYPES = {
    "Order": [
        {"name": "salt", "type": "uint256"},
        {"name": "maker", "type": "address"},
        {"name": "signer", "type": "address"},
        {"name": "taker", "type": "address"},
        {"name": "tokenId", "type": "uint256"},
        {"name": "makerAmount", "type": "uint256"},
        {"name": "takerAmount", "type": "uint256"},
        {"name": "expiration", "type": "uint256"},
        {"name": "nonce", "type": "uint256"},
        {"name": "feeRateBps", "type": "uint256"},
        {"name": "side", "type": "uint8"},
        {"name": "signatureType", "type": "uint8"},
    ]
}
order_data = {
    "salt": salt,
    "maker": maker,
    "signer": maker,
    "taker": "0x0000000000000000000000000000000000000000",
    "tokenId": int(token_id),
    "makerAmount": maker_amount,
    "takerAmount": taker_amount,
    "expiration": 0,
    "nonce": 0,
    "feeRateBps": 0,
    "side": 1,  # SELL
    "signatureType": 0,
}
eth_signable = encode_typed_data(ORDER_DOMAIN, ORDER_TYPES, order_data)
sig2 = account.sign_message(eth_signable)
print("\n=== eth_account encode_typed_data (async_clob) ===")
print(f"Message body: 0x{eth_signable.body.hex()}")
print(f"Signature: 0x{sig2.signature.hex()}")

print(f"\nSignatures match: {sig1.signature.hex() == sig2.signature.hex()}")
