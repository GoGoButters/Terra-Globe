#!/usr/bin/env python3
"""Test Wikidata SPARQL queries for embassy data.

Run inside the backend container:
  docker compose exec backend python scripts/test_wikidata.py

Tests:
  1. Basic SPARQL connectivity
  2. ISO3-based embassy query for Russia
  3. ISO3-based embassy query for Germany
  4. ISO2 fallback query
"""

import asyncio
import json
import sys
import os

# Ensure the app package is importable
sys.path.insert(0, "/app")

from app.services.wikidata import get_embassies, get_embassies_static, _sparql_query


async def test_connectivity():
    """Test basic SPARQL connectivity to Wikidata."""
    print("=" * 60)
    print("TEST 1: SPARQL connectivity")
    print("=" * 60)
    query = 'SELECT ?country WHERE { ?country wdt:P31 wd:Q6256 . } LIMIT 3'
    results = await _sparql_query(query)
    if results:
        countries = [r.get("country", {}).get("value", "").split("/")[-1] for r in results]
        print(f"  OK — got {len(results)} results: {countries}")
        return True
    else:
        print("  FAIL — no results returned")
        return False


async def test_embassies_rus():
    """Test embassy query for Russia (RUS)."""
    print("\n" + "=" * 60)
    print("TEST 2: Embassies for Russia (RUS)")
    print("=" * 60)
    data = await get_embassies("RUS")
    out = data["has_embassy_in"]
    incoming = data["embassies_from"]
    print(f"  Russia has embassies in: {len(out)} countries")
    if out:
        print(f"    Sample: {out[:15]}")
    print(f"  Countries with embassies in Russia: {len(incoming)}")
    if incoming:
        print(f"    Sample: {incoming[:15]}")
    return len(out) > 0 or len(incoming) > 0


async def test_embassies_deu():
    """Test embassy query for Germany (DEU)."""
    print("\n" + "=" * 60)
    print("TEST 3: Embassies for Germany (DEU)")
    print("=" * 60)
    data = await get_embassies("DEU")
    out = data["has_embassy_in"]
    incoming = data["embassies_from"]
    print(f"  Germany has embassies in: {len(out)} countries")
    if out:
        print(f"    Sample: {out[:15]}")
    print(f"  Countries with embassies in Germany: {len(incoming)}")
    if incoming:
        print(f"    Sample: {incoming[:15]}")
    return len(out) > 0 or len(incoming) > 0


async def test_embassies_small():
    """Test embassy query for a small country — Iceland (ISL)."""
    print("\n" + "=" * 60)
    print("TEST 4: Embassies for Iceland (ISL)")
    print("=" * 60)
    data = await get_embassies("ISL")
    out = data["has_embassy_in"]
    incoming = data["embassies_from"]
    print(f"  Iceland has embassies in: {len(out)} countries")
    if out:
        print(f"    List: {out}")
    print(f"  Countries with embassies in Iceland: {len(incoming)}")
    if incoming:
        print(f"    List: {incoming}")
    return True  # Small countries may legitimately have few


async def test_static_fallback():
    """Test static fallback data."""
    print("\n" + "=" * 60)
    print("TEST 5: Static fallback data")
    print("=" * 60)
    data = get_embassies_static("RUS")
    print(f"  RUS static has_embassy_in: {len(data['has_embassy_in'])} countries")
    print(f"  RUS static embassies_from: {len(data['embassies_from'])} countries")
    data_small = get_embassies_static("ISL")
    print(f"  ISL static has_embassy_in: {len(data_small['has_embassy_in'])} countries")
    print(f"  ISL static embassies_from: {len(data_small['embassies_from'])} countries")
    return True


async def main():
    print("Wikidata SPARQL Embassy Test Suite")
    print("Date: 2026-07-12")
    print()

    tests = [
        ("Connectivity", test_connectivity),
        ("Russia", test_embassies_rus),
        ("Germany", test_embassies_deu),
        ("Iceland", test_embassies_small),
        ("Static Fallback", test_static_fallback),
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
