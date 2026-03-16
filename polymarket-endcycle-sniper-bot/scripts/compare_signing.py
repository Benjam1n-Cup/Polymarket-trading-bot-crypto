#!/usr/bin/env python3
"""Compare EIP-712 signing between eth_account and poly_eip712_structs."""

from eth_account import Account
from eth_account.messages import encode_typed_data
from eth_utils import keccak
from poly_eip712_structs import make_domain, Address, EIP712Struct, Uint


# Define order struct matching py_order_utils
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


# Test data
CTF_EXCHANGE = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
MAKER = "0xb05f647DB67bE5351Bc7e5F51B3825E0a8FF7434"
TOKEN_ID = 21742633143463906290569050155826241533067272736897614950488156847949938836455
SALT = 12345  # Fixed salt for comparison

order_data = {
    "salt": SALT,
    "maker": MAKER,
    "signer": MAKER,
    "taker": "0x0000000000000000000000000000000000000000",
    "tokenId": TOKEN_ID,
    "makerAmount": 10000,
    "takerAmount": 1000000,
    "expiration": 0,
    "nonce": 0,
    "feeRateBps": 0,
    "side": 0,  # BUY
    "signatureType": 0,  # EOA
}

# Method 1: poly_eip712_structs (what py_order_utils uses)
print("=== poly_eip712_structs approach ===")
domain = make_domain(
    name="Polymarket CTF Exchange",
    version="1",
    chainId="137",
    verifyingContract=CTF_EXCHANGE,
)
order = Order(
    salt=order_data["salt"],
    maker=order_data["maker"],
    signer=order_data["signer"],
    taker=order_data["taker"],
    tokenId=order_data["tokenId"],
    makerAmount=order_data["makerAmount"],
    takerAmount=order_data["takerAmount"],
    expiration=order_data["expiration"],
    nonce=order_data["nonce"],
    feeRateBps=order_data["feeRateBps"],
    side=order_data["side"],
    signatureType=order_data["signatureType"],
)
signable = order.signable_bytes(domain=domain)
struct_hash = "0x" + keccak(signable).hex()
print(f"Struct hash: {struct_hash}")

# Method 2: eth_account encode_typed_data (what I use)
print("\n=== eth_account encode_typed_data approach ===")
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
eth_signable = encode_typed_data(ORDER_DOMAIN, ORDER_TYPES, order_data)
print(f"eth_signable type: {type(eth_signable)}")
print(f"eth_signable body: {eth_signable.body.hex() if hasattr(eth_signable.body, 'hex') else eth_signable.body}")
print(f"eth_signable header: {eth_signable.header.hex() if hasattr(eth_signable.header, 'hex') else eth_signable.header}")

# Try to get hash via keccak of full message
full_message = b"\x19\x01" + domain.hash_struct() + order.hash_struct()
print(f"\nManually computed full hash: {keccak(full_message).hex()}")
print(f"eth_signable body hash:      {eth_signable.body.hex() if hasattr(eth_signable.body, 'hex') else 'N/A'}")

# Print the domain hashes
domain_sep = domain.hash_struct()
print(f"\npoly_eip712 domain hash: {domain_sep.hex()}")
print(f"poly_eip712 order hash:  {order.hash_struct().hex()}")

# Now test actual signing with a test key
TEST_KEY = "0x" + "11" * 32  # Deterministic test key
account = Account.from_key(TEST_KEY)
print(f"\nTest address: {account.address}")

# Method 1: How py_order_utils signs
struct_hash = "0x" + keccak(signable).hex()
sig1 = Account._sign_hash(struct_hash, TEST_KEY)
print(f"\npy_order_utils signature: 0x{sig1.signature.hex()}")

# Method 2: How eth_account sign_message signs
sig2 = account.sign_message(eth_signable)
print(f"eth_account signature:    0x{sig2.signature.hex()}")

print(f"\nSignatures match: {sig1.signature.hex() == sig2.signature.hex()}")
