#!/usr/bin/env python3
"""Approve USDC.e spending for Polymarket exchange contracts."""

import os
import sys
from web3 import Web3

# Polygon mainnet
RPC_URL = "https://polygon-rpc.com"

# Contract addresses
USDC_E = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
CTF_EXCHANGE = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
NEG_RISK_EXCHANGE = "0xC5d563A36AE78145C45a50134d48A1215220f80a"
CONDITIONAL_TOKENS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
NEG_RISK_ADAPTER = "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296"  # Neg Risk CTF Adapter

# ERC20 ABI (just approve function)
ERC20_ABI = [
    {
        "inputs": [
            {"name": "spender", "type": "address"},
            {"name": "amount", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "owner", "type": "address"},
            {"name": "spender", "type": "address"}
        ],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    }
]

# ERC1155 ABI (for conditional tokens setApprovalForAll)
ERC1155_ABI = [
    {
        "inputs": [
            {"name": "operator", "type": "address"},
            {"name": "approved", "type": "bool"}
        ],
        "name": "setApprovalForAll",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "account", "type": "address"},
            {"name": "operator", "type": "address"}
        ],
        "name": "isApprovedForAll",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function"
    }
]

# Max uint256 for unlimited approval
MAX_UINT256 = 2**256 - 1


def main():
    private_key = os.environ.get("PRIVATE_KEY")
    if not private_key:
        print("Error: PRIVATE_KEY environment variable not set")
        sys.exit(1)

    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        print("Error: Could not connect to Polygon RPC")
        sys.exit(1)

    account = w3.eth.account.from_key(private_key)
    wallet = account.address
    print(f"Wallet: {wallet}")

    usdc = w3.eth.contract(address=Web3.to_checksum_address(USDC_E), abi=ERC20_ABI)
    ctf = w3.eth.contract(address=Web3.to_checksum_address(CONDITIONAL_TOKENS), abi=ERC1155_ABI)

    # Check current ERC20 allowances
    ctf_allowance = usdc.functions.allowance(wallet, CTF_EXCHANGE).call()
    neg_allowance = usdc.functions.allowance(wallet, NEG_RISK_EXCHANGE).call()
    cond_allowance = usdc.functions.allowance(wallet, CONDITIONAL_TOKENS).call()
    adapter_allowance = usdc.functions.allowance(wallet, NEG_RISK_ADAPTER).call()

    # Check ERC1155 approvals
    ctf_erc1155_approved = ctf.functions.isApprovedForAll(wallet, CTF_EXCHANGE).call()
    neg_erc1155_approved = ctf.functions.isApprovedForAll(wallet, NEG_RISK_EXCHANGE).call()

    print(f"\nCurrent ERC20 allowances (USDC.e):")
    print(f"  CTF Exchange: {ctf_allowance / 1e6:.2f} USDC")
    print(f"  Neg Risk Exchange: {neg_allowance / 1e6:.2f} USDC")
    print(f"  Conditional Tokens: {cond_allowance / 1e6:.2f} USDC")
    print(f"  Neg Risk Adapter: {adapter_allowance / 1e6:.2f} USDC")
    print(f"\nCurrent ERC1155 approvals (Conditional Tokens):")
    print(f"  CTF Exchange: {ctf_erc1155_approved}")
    print(f"  Neg Risk Exchange: {neg_erc1155_approved}")

    # Approve CTF Exchange if needed
    if ctf_allowance < MAX_UINT256 // 2:
        print(f"\nApproving CTF Exchange ({CTF_EXCHANGE})...")
        tx = usdc.functions.approve(CTF_EXCHANGE, MAX_UINT256).build_transaction({
            'from': wallet,
            'nonce': w3.eth.get_transaction_count(wallet),
            'gas': 100000,
            'gasPrice': w3.eth.gas_price,
            'chainId': 137,
        })
        signed = w3.eth.account.sign_transaction(tx, private_key)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        print(f"  TX: {tx_hash.hex()}")
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        print(f"  Status: {'Success' if receipt['status'] == 1 else 'Failed'}")
    else:
        print("\nCTF Exchange already approved")

    # Approve Neg Risk Exchange if needed
    if neg_allowance < MAX_UINT256 // 2:
        print(f"\nApproving Neg Risk Exchange ({NEG_RISK_EXCHANGE})...")
        tx = usdc.functions.approve(NEG_RISK_EXCHANGE, MAX_UINT256).build_transaction({
            'from': wallet,
            'nonce': w3.eth.get_transaction_count(wallet),
            'gas': 100000,
            'gasPrice': w3.eth.gas_price,
            'chainId': 137,
        })
        signed = w3.eth.account.sign_transaction(tx, private_key)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        print(f"  TX: {tx_hash.hex()}")
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        print(f"  Status: {'Success' if receipt['status'] == 1 else 'Failed'}")
    else:
        print("\nNeg Risk Exchange already approved")

    # Approve Conditional Tokens contract if needed
    if cond_allowance < MAX_UINT256 // 2:
        print(f"\nApproving Conditional Tokens ({CONDITIONAL_TOKENS})...")
        tx = usdc.functions.approve(CONDITIONAL_TOKENS, MAX_UINT256).build_transaction({
            'from': wallet,
            'nonce': w3.eth.get_transaction_count(wallet),
            'gas': 100000,
            'gasPrice': w3.eth.gas_price,
            'chainId': 137,
        })
        signed = w3.eth.account.sign_transaction(tx, private_key)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        print(f"  TX: {tx_hash.hex()}")
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        print(f"  Status: {'Success' if receipt['status'] == 1 else 'Failed'}")
    else:
        print("\nConditional Tokens already approved")

    # Approve Neg Risk Adapter if needed
    if adapter_allowance < MAX_UINT256 // 2:
        print(f"\nApproving Neg Risk Adapter ({NEG_RISK_ADAPTER})...")
        tx = usdc.functions.approve(NEG_RISK_ADAPTER, MAX_UINT256).build_transaction({
            'from': wallet,
            'nonce': w3.eth.get_transaction_count(wallet),
            'gas': 100000,
            'gasPrice': w3.eth.gas_price,
            'chainId': 137,
        })
        signed = w3.eth.account.sign_transaction(tx, private_key)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        print(f"  TX: {tx_hash.hex()}")
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        print(f"  Status: {'Success' if receipt['status'] == 1 else 'Failed'}")
    else:
        print("\nNeg Risk Adapter already approved")

    # Set ERC1155 approval for CTF Exchange if needed
    if not ctf_erc1155_approved:
        print(f"\nSetting ERC1155 approval for CTF Exchange...")
        tx = ctf.functions.setApprovalForAll(CTF_EXCHANGE, True).build_transaction({
            'from': wallet,
            'nonce': w3.eth.get_transaction_count(wallet),
            'gas': 100000,
            'gasPrice': w3.eth.gas_price,
            'chainId': 137,
        })
        signed = w3.eth.account.sign_transaction(tx, private_key)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        print(f"  TX: {tx_hash.hex()}")
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        print(f"  Status: {'Success' if receipt['status'] == 1 else 'Failed'}")
    else:
        print("\nCTF Exchange ERC1155 already approved")

    # Set ERC1155 approval for Neg Risk Exchange if needed
    if not neg_erc1155_approved:
        print(f"\nSetting ERC1155 approval for Neg Risk Exchange...")
        tx = ctf.functions.setApprovalForAll(NEG_RISK_EXCHANGE, True).build_transaction({
            'from': wallet,
            'nonce': w3.eth.get_transaction_count(wallet),
            'gas': 100000,
            'gasPrice': w3.eth.gas_price,
            'chainId': 137,
        })
        signed = w3.eth.account.sign_transaction(tx, private_key)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        print(f"  TX: {tx_hash.hex()}")
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        print(f"  Status: {'Success' if receipt['status'] == 1 else 'Failed'}")
    else:
        print("\nNeg Risk Exchange ERC1155 already approved")

    # Verify final allowances
    print("\n--- Final Status ---")
    ctf_allowance = usdc.functions.allowance(wallet, CTF_EXCHANGE).call()
    neg_allowance = usdc.functions.allowance(wallet, NEG_RISK_EXCHANGE).call()
    cond_allowance = usdc.functions.allowance(wallet, CONDITIONAL_TOKENS).call()
    adapter_allowance = usdc.functions.allowance(wallet, NEG_RISK_ADAPTER).call()
    ctf_erc1155_approved = ctf.functions.isApprovedForAll(wallet, CTF_EXCHANGE).call()
    neg_erc1155_approved = ctf.functions.isApprovedForAll(wallet, NEG_RISK_EXCHANGE).call()

    print("ERC20 Allowances (USDC.e):")
    print(f"  CTF Exchange: {'Unlimited' if ctf_allowance > 1e30 else f'{ctf_allowance / 1e6:.2f} USDC'}")
    print(f"  Neg Risk Exchange: {'Unlimited' if neg_allowance > 1e30 else f'{neg_allowance / 1e6:.2f} USDC'}")
    print(f"  Conditional Tokens: {'Unlimited' if cond_allowance > 1e30 else f'{cond_allowance / 1e6:.2f} USDC'}")
    print(f"  Neg Risk Adapter: {'Unlimited' if adapter_allowance > 1e30 else f'{adapter_allowance / 1e6:.2f} USDC'}")
    print("ERC1155 Approvals (Conditional Tokens):")
    print(f"  CTF Exchange: {ctf_erc1155_approved}")
    print(f"  Neg Risk Exchange: {neg_erc1155_approved}")
    print("\nDone! You can now trade on Polymarket.")


if __name__ == "__main__":
    main()
