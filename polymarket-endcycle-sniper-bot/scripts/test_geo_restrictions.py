#!/usr/bin/env python3
"""
Test Polymarket API geo-restrictions.

Run this script from different locations (US vs EU) to determine
which endpoints are blocked.

Usage:
    python scripts/test_geo_restrictions.py
"""

import asyncio
import json
import os
import sys
from datetime import datetime

import aiohttp


# Test endpoints
GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"
CLOB_WS = "wss://ws-subscriptions-clob.polymarket.com/ws/market"

# Sample market for testing (high liquidity market)
TEST_CONDITION_ID = None  # Will be populated from markets list


async def get_public_ip():
    """Get the public IP address of this machine."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.ipify.org?format=json", timeout=10) as resp:
                data = await resp.json()
                return data.get("ip", "unknown")
    except Exception as e:
        return f"error: {e}"


async def test_gamma_markets():
    """Test Gamma API - market list (read-only)."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{GAMMA_API}/markets",
                params={"active": "true", "limit": "5"},
                timeout=10,
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {
                        "status": "OK",
                        "http_code": resp.status,
                        "markets_returned": len(data) if isinstance(data, list) else 0,
                    }
                elif resp.status == 403:
                    text = await resp.text()
                    return {"status": "BLOCKED", "http_code": resp.status, "response": text[:200]}
                else:
                    text = await resp.text()
                    return {"status": "ERROR", "http_code": resp.status, "response": text[:200]}
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}


async def test_clob_markets():
    """Test CLOB API - markets list (read-only)."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{CLOB_API}/markets",
                params={"limit": "5"},
                timeout=10,
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    markets = data if isinstance(data, list) else data.get("data", [])
                    return {
                        "status": "OK",
                        "http_code": resp.status,
                        "markets_returned": len(markets),
                    }
                elif resp.status == 403:
                    text = await resp.text()
                    return {"status": "BLOCKED", "http_code": resp.status, "response": text[:200]}
                else:
                    text = await resp.text()
                    return {"status": "ERROR", "http_code": resp.status, "response": text[:200]}
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}


async def test_clob_orderbook(token_id: str):
    """Test CLOB API - orderbook (read-only).

    Note: Many markets use neg-risk mechanism and don't have traditional orderbooks.
    A 404 means no orderbook exists (not a geo-block). A 403 would be a geo-block.
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{CLOB_API}/book",
                params={"token_id": token_id},
                timeout=10,
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {
                        "status": "OK",
                        "http_code": resp.status,
                        "bids": len(data.get("bids", [])),
                        "asks": len(data.get("asks", [])),
                    }
                elif resp.status == 403:
                    text = await resp.text()
                    return {"status": "BLOCKED", "http_code": resp.status, "response": text[:200]}
                elif resp.status == 404:
                    # 404 = no orderbook (not geo-blocked, just no orderbook for this market)
                    return {
                        "status": "OK (no orderbook - neg-risk market)",
                        "http_code": resp.status,
                        "note": "404 means endpoint accessible but no orderbook exists",
                    }
                else:
                    text = await resp.text()
                    return {"status": "ERROR", "http_code": resp.status, "response": text[:200]}
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}


async def test_clob_price(token_id: str):
    """Test CLOB API - price endpoint (read-only)."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{CLOB_API}/price",
                params={"token_id": token_id, "side": "BUY"},
                timeout=10,
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {
                        "status": "OK",
                        "http_code": resp.status,
                        "price": data.get("price"),
                    }
                elif resp.status == 403:
                    text = await resp.text()
                    return {"status": "BLOCKED", "http_code": resp.status, "response": text[:200]}
                elif resp.status == 404:
                    # 404 = no orderbook for this market (not geo-blocked)
                    return {
                        "status": "OK (no orderbook - neg-risk market)",
                        "http_code": resp.status,
                        "note": "404 means endpoint accessible but no orderbook exists",
                    }
                else:
                    text = await resp.text()
                    return {"status": "ERROR", "http_code": resp.status, "response": text[:200]}
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}


async def test_websocket():
    """Test CLOB WebSocket connection."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(
                CLOB_WS,
                timeout=10,
            ) as ws:
                # Try to receive initial message or send a ping
                try:
                    msg = await asyncio.wait_for(ws.receive(), timeout=5)
                    return {
                        "status": "OK",
                        "message_type": str(msg.type),
                        "connected": True,
                    }
                except asyncio.TimeoutError:
                    # Connection established but no message - still OK
                    return {
                        "status": "OK",
                        "message_type": "timeout (but connected)",
                        "connected": True,
                    }
    except aiohttp.WSServerHandshakeError as e:
        return {"status": "BLOCKED", "error": f"Handshake failed: {e.status}"}
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}


async def test_order_placement_unauthenticated():
    """Test CLOB API - order placement without auth (expect 401, not 403)."""
    try:
        async with aiohttp.ClientSession() as session:
            # Send a malformed order request - we expect 401 (unauthorized) not 403 (geo-blocked)
            async with session.post(
                f"{CLOB_API}/order",
                json={"test": "invalid"},
                timeout=10,
            ) as resp:
                text = await resp.text()
                if resp.status == 401:
                    return {
                        "status": "OK (401 = auth required, not geo-blocked)",
                        "http_code": resp.status,
                    }
                elif resp.status == 403:
                    return {
                        "status": "BLOCKED",
                        "http_code": resp.status,
                        "response": text[:200],
                    }
                else:
                    return {
                        "status": f"UNEXPECTED ({resp.status})",
                        "http_code": resp.status,
                        "response": text[:200],
                    }
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}


async def test_order_placement_authenticated():
    """Test CLOB API - order placement with auth (requires credentials)."""
    # Check if we have credentials
    api_key = os.environ.get("POLY_API_KEY")
    api_secret = os.environ.get("POLY_API_SECRET")
    api_passphrase = os.environ.get("POLY_API_PASSPHRASE")

    if not all([api_key, api_secret, api_passphrase]):
        return {
            "status": "SKIPPED",
            "reason": "No POLY_API_KEY/SECRET/PASSPHRASE in environment",
        }

    try:
        from py_clob_client.client import ClobClient

        private_key = os.environ.get("PRIVATE_KEY")
        wallet = os.environ.get("WALLET_ADDRESS")

        if not private_key or not wallet:
            return {
                "status": "SKIPPED",
                "reason": "No PRIVATE_KEY/WALLET_ADDRESS in environment",
            }

        # Create client
        creds = type("Creds", (), {
            "api_key": api_key,
            "api_secret": api_secret,
            "api_passphrase": api_passphrase,
        })()

        client = ClobClient(
            host=CLOB_API,
            key=private_key,
            chain_id=137,
            creds=creds,
            signature_type=0,
            funder=wallet,
        )

        # Try to get open orders (authenticated read - tests if auth works)
        try:
            orders = client.get_orders()
            return {
                "status": "OK",
                "message": "Authenticated API access works",
                "open_orders": len(orders) if orders else 0,
            }
        except Exception as e:
            error_str = str(e).lower()
            if "403" in error_str or "forbidden" in error_str or "geo" in error_str:
                return {
                    "status": "BLOCKED",
                    "error": str(e)[:200],
                }
            else:
                return {
                    "status": "ERROR",
                    "error": str(e)[:200],
                }

    except ImportError:
        return {
            "status": "SKIPPED",
            "reason": "py-clob-client not installed",
        }
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}


async def get_sample_token_id():
    """Get a sample token ID from an active market with orderbook."""
    try:
        async with aiohttp.ClientSession() as session:
            # Get active, non-closed markets from Gamma API
            async with session.get(
                f"{GAMMA_API}/markets",
                params={"active": "true", "closed": "false", "limit": "50"},
                timeout=10,
            ) as resp:
                if resp.status == 200:
                    markets = await resp.json()
                    # Find a market with clobTokenIds (means it has an orderbook)
                    for market in markets:
                        clob_token_ids = market.get("clobTokenIds")
                        if clob_token_ids and len(clob_token_ids) > 0:
                            token_id = clob_token_ids[0]
                            print(f"      Found token: {token_id[:20]}... ({market.get('question', 'N/A')[:30]}...)")
                            return token_id
    except Exception as e:
        print(f"      Warning: Failed to get token from Gamma: {e}")

    # Fallback - known active token ID (may become stale)
    print("      Warning: Using fallback token ID")
    return "104173557214744537570424345347209544585775842950109756851652855913015295701992"


async def main():
    """Run all geo-restriction tests."""
    print("=" * 60)
    print("POLYMARKET GEO-RESTRICTION TEST")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().isoformat()}")

    # Get public IP
    ip = await get_public_ip()
    print(f"Public IP: {ip}")
    print("=" * 60)

    results = {}

    # Test 1: Gamma API (markets list)
    print("\n[1/7] Testing Gamma API (markets list)...")
    results["gamma_markets"] = await test_gamma_markets()
    print(f"      Result: {results['gamma_markets']['status']}")

    # Test 2: CLOB API (markets list)
    print("\n[2/7] Testing CLOB API (markets list)...")
    results["clob_markets"] = await test_clob_markets()
    print(f"      Result: {results['clob_markets']['status']}")

    # Get a sample token ID for further tests
    token_id = await get_sample_token_id()
    print(f"\n      Using token_id: {token_id[:20]}...")

    # Test 3: CLOB API (orderbook)
    print("\n[3/7] Testing CLOB API (orderbook)...")
    results["clob_orderbook"] = await test_clob_orderbook(token_id)
    print(f"      Result: {results['clob_orderbook']['status']}")

    # Test 4: CLOB API (price)
    print("\n[4/7] Testing CLOB API (price)...")
    results["clob_price"] = await test_clob_price(token_id)
    print(f"      Result: {results['clob_price']['status']}")

    # Test 5: WebSocket connection
    print("\n[5/7] Testing WebSocket connection...")
    results["websocket"] = await test_websocket()
    print(f"      Result: {results['websocket']['status']}")

    # Test 6: Order placement (unauthenticated)
    print("\n[6/7] Testing order endpoint (unauthenticated)...")
    results["order_unauth"] = await test_order_placement_unauthenticated()
    print(f"      Result: {results['order_unauth']['status']}")

    # Test 7: Order placement (authenticated)
    print("\n[7/7] Testing authenticated API access...")
    results["order_auth"] = await test_order_placement_authenticated()
    print(f"      Result: {results['order_auth']['status']}")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    for test_name, result in results.items():
        status = result.get("status", "UNKNOWN")
        if "BLOCKED" in status:
            indicator = "❌ BLOCKED"
        elif "OK" in status:
            indicator = "✅ OK"
            if "neg-risk" in status:
                indicator += " (neg-risk)"
        elif "SKIPPED" in status:
            indicator = "⏭️  SKIPPED"
        else:
            indicator = "⚠️  ERROR"
        print(f"{test_name:25} {indicator}")

    print("\n" + "=" * 60)
    print("FULL RESULTS (JSON)")
    print("=" * 60)
    print(json.dumps(results, indent=2))

    # Save results to file
    output_file = f"/tmp/geo_test_{ip.replace('.', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w") as f:
        json.dump({
            "ip": ip,
            "timestamp": datetime.now().isoformat(),
            "results": results,
        }, f, indent=2)
    print(f"\nResults saved to: {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
