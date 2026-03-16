#!/usr/bin/env python3
"""Test async CLOB order submission to verify payload fixes."""

import asyncio
import json
from rarb.executor.async_clob import create_async_clob_client


async def test_order():
    """Test order signing and submission."""
    client = await create_async_clob_client()
    if not client:
        print("ERROR: Could not create async CLOB client")
        return

    # Use a liquid market token for testing
    # This is "Will Trump be president on January 31?" YES token
    token_id = "21742633143463906290569050155826241533067272736897614950488156847949938836455"

    try:
        # First just test signing (no network call)
        print("Testing order signing...")
        signed = client.sign_order(
            token_id=token_id,
            side="BUY",
            price=0.01,  # Very low price, won't fill
            size=1.0,
            neg_risk=True,  # This market uses neg risk
        )

        order_dict = signed.to_dict()

        # Build full body like py_clob_client
        full_body = {
            "order": order_dict,
            "owner": client.api_key,
            "orderType": "GTC",
        }
        print("\nFull POST body:")
        print(json.dumps(full_body, indent=2))
        print("\nSerialized body:")
        print(json.dumps(full_body, separators=(",", ":"), ensure_ascii=False))

        # Validate payload structure
        print("\nValidating payload structure...")
        errors = []

        # Check side is string
        if not isinstance(order_dict["side"], str):
            errors.append(f"side should be string, got {type(order_dict['side'])}")
        elif order_dict["side"] not in ["BUY", "SELL"]:
            errors.append(f"side should be 'BUY' or 'SELL', got {order_dict['side']}")

        # Check signature has 0x prefix
        if not order_dict["signature"].startswith("0x"):
            errors.append(f"signature should start with 0x, got {order_dict['signature'][:10]}...")

        # Check salt is integer
        if not isinstance(order_dict["salt"], int):
            errors.append(f"salt should be int, got {type(order_dict['salt'])}")

        # Check signatureType is integer
        if not isinstance(order_dict["signatureType"], int):
            errors.append(f"signatureType should be int, got {type(order_dict['signatureType'])}")

        # Check amounts are strings
        for field in ["makerAmount", "takerAmount", "expiration", "nonce", "feeRateBps"]:
            if not isinstance(order_dict[field], str):
                errors.append(f"{field} should be string, got {type(order_dict[field])}")

        if errors:
            print("VALIDATION ERRORS:")
            for err in errors:
                print(f"  - {err}")
            return

        print("All payload validations passed!")

        # Now test actual submission
        print("\nSubmitting order to API...")
        result = await client.post_order(signed)
        print(f"SUCCESS! Order ID: {result.get('orderID', result)}")

        # Cancel immediately
        order_id = result.get("orderID")
        if order_id:
            print(f"\nCancelling test order {order_id}...")
            cancel_result = await client.cancel_order(order_id)
            print(f"Cancel result: {cancel_result}")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(test_order())
