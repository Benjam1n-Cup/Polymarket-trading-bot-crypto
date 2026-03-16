#!/usr/bin/env python3
"""Exit test position by selling tokens."""

import asyncio
from rarb.executor.async_clob import create_async_clob_client

# The token we bought during testing
TOKEN_ID = "104173557214744537570424345347209544585775842950109756851652855913015295701992"


async def main():
    client = await create_async_clob_client()
    if not client:
        print("Failed to create client")
        return

    try:
        # Try increasingly smaller amounts to find what we have
        for size in [100, 50, 20, 10, 5]:
            print(f"\nTrying to sell {size} tokens at $0.50...")
            try:
                result = await client.submit_order(
                    token_id=TOKEN_ID,
                    side="SELL",
                    price=0.50,
                    size=float(size),
                    neg_risk=False,
                )
                print(f"SUCCESS: {result}")
                break  # Exit loop on success
            except Exception as e:
                if "not enough balance" in str(e):
                    print(f"  Not enough balance for {size}")
                else:
                    print(f"  Error: {e}")
                    break

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
