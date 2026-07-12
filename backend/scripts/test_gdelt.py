#!/usr/bin/env python3
"""Test GDELT GEO API for bilateral tone data.

Run inside the backend container:
  docker compose exec backend python scripts/test_gdelt.py

Tests:
  1. GDELT connectivity (Russia → USA tone)
  2. _gdelt_name conversion
  3. Multiple target tone query
"""

import asyncio
import json
import sys
import os

sys.path.insert(0, "/app")

from app.services.gdelt import get_country_tone, _gdelt_name


async def test_connectivity():
    """Test GDELT GEO API connectivity — Russia's media about USA."""
    print("=" * 60)
    print("TEST 1: GDELT connectivity (Russia → USA)")
    print("=" * 60)

    results = await get_country_tone("Russia", ["United States"])
    usa_tone = results.get("United States", {})
    print(f"  Tone: {usa_tone.get('tone', 'N/A')}")
    print(f"  Article count: {usa_tone.get('count', 'N/A')}")
    print(f"  Trend: {usa_tone.get('trend', 'N/A')}")
    articles = usa_tone.get("articles", [])
    if articles:
        print(f"  Top article: {articles[0].get('title', 'N/A')[:80]}")
    else:
        print("  No articles returned (may be expected if GDELT has no recent data)")
    return True  # Even 0 articles is a valid response


async def test_gdelt_names():
    """Test _gdelt_name conversion."""
    print("\n" + "=" * 60)
    print("TEST 2: Country name → GDELT name conversion")
    print("=" * 60)
    test_cases = [
        ("Russia", "russia"),
        ("United States", "unitedstates"),
        ("United Kingdom", "unitedkingdom"),
        ("South Korea", "southkorea"),
        ("Czech Republic", "czechrepublic"),
        ("Ivory Coast", "ivorycoast"),
        ("UAE", "unitedarabemirates"),
        ("France", "france"),
        ("Germany", "germany"),
        ("Japan", "japan"),
    ]

    all_ok = True
    for name, expected in test_cases:
        result = _gdelt_name(name)
        status = "✅" if result == expected else "❌"
        if result != expected:
            all_ok = False
        print(f"  {status} '{name}' → '{result}' (expected: '{expected}')")

    return all_ok


async def test_multi_target():
    """Test tone query for multiple targets."""
    print("\n" + "=" * 60)
    print("TEST 3: Multi-target tone (USA media → [Russia, China, UK])")
    print("=" * 60)

    results = await get_country_tone(
        "United States",
        ["Russia", "China", "United Kingdom"],
    )

    for target, data in results.items():
        tone = data.get("tone", 0)
        count = data.get("count", 0)
        trend = data.get("trend", "unknown")
        color = "🟢" if tone > 0 else ("🔴" if tone < 0 else "⚪")
        print(f"  {color} {target}: tone={tone:+.1f}, articles={count}, trend={trend}")

    return True


async def main():
    print("GDELT GEO API Test Suite")
    print("Date: 2026-07-12")
    print()

    tests = [
        ("Connectivity", test_connectivity),
        ("Name Conversion", test_gdelt_names),
        ("Multi-Target", test_multi_target),
    ]

    passed = 0
    failed = 0

    for name, test_fn in tests:
        try:
            result = await test_fn()
            if result:
                passed += 1
                print(f"  ✅ PASS: {name}")
            else:
                failed += 1
                print(f"  ❌ FAIL: {name}")
        except Exception as e:
            failed += 1
            print(f"  ❌ ERROR: {name} — {e}")

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)}")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
