from __future__ import annotations

import time

from .db import get_collection


def test_queries() -> None:
    collection = get_collection()

    print("=" * 70)
    print("QUERY TESTS")
    print("=" * 70)

    print("\n[TEST 1] Crashes near Times Square (500m)")
    start = time.time()
    results = list(
        collection.find(
            {
                "LOCATION": {
                    "$nearSphere": {
                        "$geometry": {"type": "Point", "coordinates": [-73.9855, 40.7580]},
                        "$maxDistance": 500,
                    }
                }
            }
        ).limit(5)
    )
    print(f"✅ Found {len(results)} in {(time.time() - start) * 1000:.2f}ms")

    print("\n[TEST 2] Crashes in Manhattan")
    start = time.time()
    count = collection.count_documents({"BOROUGH": "MANHATTAN"})
    print(f"✅ Found {count:,} in {(time.time() - start) * 1000:.2f}ms")

    print("\n[TEST 3] Recent crashes (2024)")
    start = time.time()
    count = collection.count_documents({"CRASH DATE": {"$regex": "^.*/2024$"}})
    print(f"✅ Found {count:,} in {(time.time() - start) * 1000:.2f}ms")
