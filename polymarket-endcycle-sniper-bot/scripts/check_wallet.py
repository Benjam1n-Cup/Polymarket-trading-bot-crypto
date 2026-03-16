#!/usr/bin/env python3
"""Check wallet balance and allowances for Polymarket."""

import os
import sys
from web3 import Web3

RPC_URL = "https://polygon-rpc.com"
USDC_E = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
CTF_EXCHANGE = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
NEG_RISK_EXCHANGE = "0xC5d563A36AE78145C45a50134d48A1215220f80a"

ERC20_ABI = [
    {
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "owner", "type": "address"},
            {"name": "spender", "type": "address"},
        ],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]

w3 = Web3(Web3.HTTPProvider(RPC_URL))
wallet = os.environ.get("WALLET_ADDRESS")
if not wallet:
    print("Error: WALLET_ADDRESS environment variable not set")
    sys.exit(1)

usdc = w3.eth.contract(address=Web3.to_checksum_address(USDC_E), abi=ERC20_ABI)

balance = usdc.functions.balanceOf(wallet).call()
ctf_allowance = usdc.functions.allowance(wallet, CTF_EXCHANGE).call()
neg_allowance = usdc.functions.allowance(wallet, NEG_RISK_EXCHANGE).call()
matic = w3.eth.get_balance(wallet)

print(f"Wallet: {wallet}")
print(f"USDC.e Balance: ${balance / 1e6:.2f}")
print(f"MATIC Balance: {w3.from_wei(matic, 'ether'):.4f} MATIC")
print()
print("Allowances:")
if ctf_allowance > 1e30:
    print("  CTF Exchange: Unlimited")
else:
    print(f"  CTF Exchange: ${ctf_allowance / 1e6:.2f}")
if neg_allowance > 1e30:
    print("  Neg Risk Exchange: Unlimited")
else:
    print(f"  Neg Risk Exchange: ${neg_allowance / 1e6:.2f}")
